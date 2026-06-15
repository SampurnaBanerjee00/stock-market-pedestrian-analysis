"""
main.py – FastAPI application
─────────────────────────────
Endpoints:
  POST /webhook            – Accepts TradingView / custom payloads
  GET  /status/{task_id}   – Poll task status
  GET  /health             – Health check
  GET  /watchlist          – Current watchlist
  POST /scan/{ticker}      – Manually trigger a single ticker scan

Run:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import USE_REDIS, WATCHLIST, LOG_LEVEL
from models.schemas import WebhookPayload, TaskResponse, TaskStatusResponse

# ─── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    )
)
logger = structlog.get_logger(__name__)

BASE_DIR = Path(__file__).parent


# ─── App lifespan ─────────────────────────────────────────────────────────────
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler

    # Start fallback worker thread if not using Redis
    if not USE_REDIS:
        from celery_worker import start_fallback_worker
        start_fallback_worker()
        logger.info("In-memory fallback worker started.")
    else:
        logger.info("Using Celery + Redis for task queue.")

    # Start APScheduler
    from scheduler import create_scheduler
    _scheduler = create_scheduler()
    _scheduler.start()
    logger.info("APScheduler started with %d jobs.", len(_scheduler.get_jobs()))

    yield  # ← App runs here

    if _scheduler:
        _scheduler.shutdown(wait=False)
    logger.info("Shutdown complete.")


# ─── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="NSE Multi-Agent Stock System",
    description=(
        "Autonomous multi-agent stock analysis for Indian (NSE/BSE) markets. "
        "Supports TradingView webhooks, manual triggers, and scheduled scans."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _enqueue_task(ticker: str, event_type: str, extra: dict | None = None) -> str:
    """Routes task to Celery or in-memory queue. Returns task_id."""
    if USE_REDIS:
        from celery_worker import run_analysis_task
        result = run_analysis_task.apply_async(
            kwargs={"ticker": ticker, "event_type": event_type, "extra": extra or {}}
        )
        return result.id
    else:
        from state.task_store import task_store
        return task_store.enqueue(
            {"ticker": ticker, "event_type": event_type, "extra": extra or {}}
        )


def _get_task_status(task_id: str) -> dict[str, Any]:
    if USE_REDIS:
        from celery.result import AsyncResult
        from celery_worker import celery_app
        result = AsyncResult(task_id, app=celery_app)
        status_map = {
            "PENDING": "queued",
            "STARTED": "running",
            "SUCCESS": "done",
            "FAILURE": "failed",
            "RETRY": "running",
        }
        status = status_map.get(result.state, result.state.lower())
        return {
            "task_id": task_id,
            "status": status,
            "result": result.result if result.successful() else None,
            "error": str(result.result) if result.failed() else None,
        }
    else:
        from state.task_store import task_store
        rec = task_store.get(task_id)
        if not rec:
            return {"task_id": task_id, "status": "not_found"}
        return {
            "task_id": task_id,
            "status": rec.status,
            "result": rec.result,
            "error": rec.error,
            "created_at": rec.created_at,
            "updated_at": rec.updated_at,
        }


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.get("/health", tags=["system"])
async def health():
    """Health check endpoint."""
    redis_ok = False
    if USE_REDIS:
        try:
            import redis as redis_lib
            r = redis_lib.from_url("redis://localhost:6379/0", socket_connect_timeout=2)
            r.ping()
            redis_ok = True
        except Exception:
            pass

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "celery+redis" if USE_REDIS else "in-memory-fallback",
        "redis_connected": redis_ok if USE_REDIS else "N/A",
        "scheduler_running": _scheduler.running if _scheduler else False,
        "watchlist": WATCHLIST,
    }


@app.get("/watchlist", tags=["system"])
async def get_watchlist():
    """Returns the current watchlist."""
    return {"watchlist": WATCHLIST, "count": len(WATCHLIST)}


@app.post("/webhook", response_model=TaskResponse, status_code=202, tags=["analysis"])
async def webhook(payload: WebhookPayload):
    """
    Accept a webhook event (TradingView / custom) and queue analysis.

    Example payload:
    ```json
    {
      "ticker": "RELIANCE.NS",
      "event_type": "price_above_ma",
      "price": 2950.0,
      "timestamp": "2025-05-15T09:30:00Z"
    }
    ```
    """
    ticker = payload.ticker.upper().strip()
    if not ticker.endswith((".NS", ".BO")):
        ticker += ".NS"  # Default to NSE

    task_id = _enqueue_task(
        ticker=ticker,
        event_type=payload.event_type,
        extra={"price": payload.price, "timestamp": payload.timestamp},
    )

    logger.info(
        "Webhook received: ticker=%s  event=%s  task_id=%s",
        ticker, payload.event_type, task_id,
    )
    return TaskResponse(task_id=task_id, status="queued")


@app.get("/status/{task_id}", response_model=TaskStatusResponse, tags=["analysis"])
async def get_status(task_id: str):
    """Poll the status of an analysis task."""
    data = _get_task_status(task_id)
    if data.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return TaskStatusResponse(**data)


@app.get("/scan/{ticker}", response_model=TaskResponse, status_code=202, tags=["analysis"])
@app.post("/scan/{ticker}", response_model=TaskResponse, status_code=202, tags=["analysis"])
async def manual_scan(ticker: str):
    """
    Manually trigger a full analysis for a ticker.
    Ticker should be in NSE format (e.g. RELIANCE.NS) or plain (RELIANCE).
    """
    ticker = ticker.upper().strip()
    if not ticker.endswith((".NS", ".BO")):
        ticker += ".NS"

    task_id = _enqueue_task(ticker=ticker, event_type="manual_scan")
    logger.info("Manual scan triggered: ticker=%s  task_id=%s", ticker, task_id)
    return TaskResponse(task_id=task_id, status="queued")


@app.get("/api/price/{ticker}", tags=["analysis"])
async def get_live_price(ticker: str):
    """Fetch the most accurate present stock price + 1D history for the chart."""
    import yfinance as yf
    from tools.yfinance_wrapper import _nse_ticker
    try:
        t = _nse_ticker(ticker)
        yf_obj = yf.Ticker(t)
        
        # Get live info
        price = yf_obj.fast_info['last_price']
        prev = yf_obj.fast_info['regular_market_previous_close']
        change_pct = ((price - prev) / prev * 100) if prev else 0
        
        # Get 1D history for chart
        hist = yf_obj.history(period="1d", interval="15m")
        history_points = []
        for dt, row in hist.iterrows():
            history_points.append({"time": dt.strftime("%H:%M"), "close": round(row['Close'], 2)})
            
        return {
            "ticker": ticker, 
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "history": history_points,
            "time": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Price/History fetch failed for {ticker}: {e}")
    return JSONResponse(status_code=404, content={"detail": "Price unavailable"})


@app.get("/api/indices", tags=["market"])
async def get_market_indices():
    """Fetch live Nifty 50 and Sensex indices."""
    import yfinance as yf
    try:
        nifty = yf.Ticker("^NSEI").fast_info
        sensex = yf.Ticker("^BSESN").fast_info
        
        def _fmt(info):
            price = info['last_price']
            prev = info['regular_market_previous_close']
            change = price - prev
            pct = (change / prev * 100) if prev else 0
            return {
                "price": round(price, 2),
                "change": round(change, 2),
                "pct": round(pct, 2)
            }
            
        return {
            "nifty": _fmt(nifty),
            "sensex": _fmt(sensex)
        }
    except Exception:
        pass
    return JSONResponse(status_code=404, content={"detail": "Indices unavailable"})
@app.get("/signals/latest", tags=["analysis"])
async def get_latest_signal():
    """Return the most recently generated signal from disk."""
    import json
    from config import OUTPUTS_DIR
    path = OUTPUTS_DIR / "latest_signal.json"
    if not path.exists():
        return JSONResponse(status_code=404, content={"detail": "No signal generated yet."})
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/reset", tags=["analysis"])
async def reset_analysis():
    """Clear all stored analysis results."""
    import shutil
    from config import OUTPUTS_DIR
    try:
        # Clear the directory
        if OUTPUTS_DIR.exists():
            shutil.rmtree(OUTPUTS_DIR)
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Analysis history reset.")
        return {"message": "Pipelines reset successfully."}
    except Exception as e:
        logger.error("Failed to reset pipelines: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def serve_dashboard():
    """Serve the modern AI dashboard."""
    static_path = BASE_DIR / "static" / "index.html"
    if not static_path.exists():
        return """
        <html>
            <body style='background:#121212;color:white;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'>
                <h1>Dashboard coming soon... refresh in 10 seconds</h1>
            </body>
        </html>
        """
    with open(static_path, "r", encoding="utf-8") as f:
        return f.read()
