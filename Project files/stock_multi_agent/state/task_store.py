"""
state/task_store.py
───────────────────
Simple in-memory task store used when USE_REDIS=False.

⚠️  DEMO-ONLY LIMITATIONS:
    - State is lost on process restart.
    - Not safe for multi-process / multi-worker deployments.
    - No persistence or crash recovery.
    Use Redis + Celery in production.
"""
from __future__ import annotations
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


class TaskRecord:
    def __init__(self, task_id: str, payload: dict):
        self.task_id = task_id
        self.payload = payload
        self.status = "queued"
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at


class InMemoryTaskStore:
    """Thread-safe in-memory store + queue for background tasks."""

    def __init__(self):
        self._store: dict[str, TaskRecord] = {}
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()

    def enqueue(self, payload: dict) -> str:
        task_id = str(uuid.uuid4())
        record = TaskRecord(task_id, payload)
        with self._lock:
            self._store[task_id] = record
        self._queue.put(task_id)
        return task_id

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._store.get(task_id)

    def update(
        self,
        task_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ):
        with self._lock:
            rec = self._store.get(task_id)
            if rec:
                rec.status = status
                rec.result = result
                rec.error = error
                rec.updated_at = datetime.now(timezone.utc).isoformat()

    def next_task_id(self, block: bool = True, timeout: float = 1.0) -> Optional[str]:
        try:
            return self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None


# Singleton
task_store = InMemoryTaskStore()
