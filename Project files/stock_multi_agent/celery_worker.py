"""
celery_worker.py
─────────────────
Celery application + tasks.
If USE_REDIS=False, provides a threading-based fallback runner (demo only).

Start with:
    celery -A celery_worker worker --loglevel=info --concurrency=2
"""
from __future__ import annotations
import logging
import threading

from config import USE_REDIS, CELERY_BROKER_URL, CELERY_RESULT_BACKEND

logger = logging.getLogger(__name__)

# ─── Celery setup (only when Redis is available) ──────────────────────────────
if USE_REDIS:
    from celery import Celery

    celery_app = Celery(
        "stock_multi_agent",
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
    )

    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Asia/Kolkata",
        enable_utc=True,
        task_acks_late=True,              # Crash safety: ack after completion
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        result_expires=86400,             # 24h
    )

    @celery_app.task(bind=True, name="run_analysis", max_retries=2, default_retry_delay=10)
    def run_analysis_task(self, ticker: str, event_type: str = "manual", extra: dict = None):
        """Celery task: run the full multi-agent pipeline for a ticker."""
        from agents.orchestrator import OrchestratorAgent
        try:
            agent = OrchestratorAgent()
            result = agent.run(ticker=ticker, event_type=event_type)
            return result
        except Exception as exc:
            logger.error("Celery task failed for %s: %s", ticker, exc, exc_info=True)
            raise self.retry(exc=exc)

else:
    # ── In-memory fallback (demo only) ────────────────────────────────────
    logger.warning(
        "USE_REDIS=False → using in-memory fallback queue. "
        "NOT suitable for production. No crash recovery."
    )

    # Dummy stand-in so imports don't break
    celery_app = None  # type: ignore

    def run_analysis_task(ticker: str, event_type: str = "manual", extra: dict = None):
        """Synchronous version used in fallback mode – called by the background thread."""
        from agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        return agent.run(ticker=ticker, event_type=event_type)


def start_fallback_worker():
    """
    Starts a daemon thread that drains the in-memory queue.
    Called from main.py when USE_REDIS=False.
    """
    if USE_REDIS:
        return  # Redis mode: Celery handles this

    from state.task_store import task_store

    def _worker_loop():
        from concurrent.futures import ThreadPoolExecutor
        logger.info("In-memory fallback worker started.")
        
        # Process up to 3 scans in parallel
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="FallbackTask") as executor:
            while True:
                task_id = task_store.next_task_id(block=True, timeout=1.0)
                if task_id is None:
                    continue
                
                rec = task_store.get(task_id)
                if not rec: continue

                def _do_work(tid=task_id, payload=rec.payload):
                    task_store.update(tid, status="running")
                    try:
                        res = run_analysis_task(
                            ticker=payload.get("ticker"),
                            event_type=payload.get("event_type", "manual"),
                        )
                        task_store.update(tid, status="done", result=res)
                    except Exception as e:
                        task_store.update(tid, status="failed", error=str(e))
                        logger.error("Fallback task %s failed: %s", tid, e)

                executor.submit(_do_work)

    t = threading.Thread(target=_worker_loop, daemon=True, name="FallbackWorker")
    t.start()
    logger.info("Fallback worker thread started (thread id=%s)", t.ident)
