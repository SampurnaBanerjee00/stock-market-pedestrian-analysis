"""
scheduler.py
─────────────
APScheduler-based periodic watchlist scanner.
Runs every SCAN_INTERVAL_MINUTES during NSE market hours (IST 09:15–15:30).
Also runs a morning pre-market scan at 09:00 IST.

Start standalone:
    python scheduler.py

Or it's started automatically inside main.py on FastAPI startup.
"""
from __future__ import annotations
import logging
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import WATCHLIST, SCAN_INTERVAL_MINUTES, MARKET_TZ

logger = logging.getLogger(__name__)

_tz = pytz.timezone(MARKET_TZ)


def _is_market_hours() -> bool:
    """Return True if current IST time is within NSE trading hours."""
    now_ist = datetime.now(_tz)
    # Monday=0 … Friday=4
    if now_ist.weekday() > 4:
        return False
    market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now_ist <= market_close


def _enqueue(ticker: str, event_type: str):
    """Route the scan to Celery or in-memory queue depending on USE_REDIS."""
    from config import USE_REDIS

    if USE_REDIS:
        from celery_worker import run_analysis_task
        task = run_analysis_task.apply_async(
            kwargs={"ticker": ticker, "event_type": event_type}
        )
        logger.info("Scheduled scan queued via Celery: ticker=%s  task_id=%s", ticker, task.id)
    else:
        from state.task_store import task_store
        task_id = task_store.enqueue({"ticker": ticker, "event_type": event_type})
        logger.info("Scheduled scan queued (fallback): ticker=%s  task_id=%s", ticker, task_id)


def _run_watchlist_scan():
    """Scan all tickers in the watchlist (called by scheduler)."""
    if not _is_market_hours():
        logger.debug("Outside market hours – skipping scheduled scan.")
        return

    logger.info("Running scheduled watchlist scan for %d stocks", len(WATCHLIST))
    for ticker in WATCHLIST:
        try:
            _enqueue(ticker, event_type="scheduled_scan")
        except Exception as e:
            logger.error("Failed to enqueue %s during scan: %s", ticker, e)


def _run_premarket_scan():
    """Morning pre-market data fetch (runs at 09:00 IST weekdays)."""
    now_ist = datetime.now(_tz)
    if now_ist.weekday() > 4:
        return
    logger.info("Running pre-market scan for %d stocks", len(WATCHLIST))
    for ticker in WATCHLIST:
        try:
            _enqueue(ticker, event_type="premarket_scan")
        except Exception as e:
            logger.error("Failed to enqueue pre-market scan for %s: %s", ticker, e)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=_tz)

    # ── Intra-day scan every N minutes ────────────────────────────────────
    scheduler.add_job(
        _run_watchlist_scan,
        trigger=IntervalTrigger(minutes=SCAN_INTERVAL_MINUTES, timezone=_tz),
        id="watchlist_scan",
        name=f"Watchlist scan every {SCAN_INTERVAL_MINUTES}min",
        replace_existing=True,
    )

    # ── Morning pre-market scan at 09:00 IST weekdays ─────────────────────
    scheduler.add_job(
        _run_premarket_scan,
        trigger=CronTrigger(hour=9, minute=0, day_of_week="mon-fri", timezone=_tz),
        id="premarket_scan",
        name="Pre-market scan (09:00 IST)",
        replace_existing=True,
    )

    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
