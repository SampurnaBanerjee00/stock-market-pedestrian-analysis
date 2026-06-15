"""
agents/base.py
──────────────
Abstract base class for all agents.
"""
from __future__ import annotations
import logging
import time
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """All agents inherit from this class."""

    name: str = "BaseAgent"

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def run(self, ticker: str, **kwargs) -> dict[str, Any]:
        """Execute the agent's task and return a structured result dict."""
        ...

    def _timed_run(self, ticker: str, **kwargs) -> dict[str, Any]:
        """Wraps run() with timing and error handling."""
        start = time.perf_counter()
        try:
            result = self.run(ticker, **kwargs)
            elapsed = time.perf_counter() - start
            self.logger.info("%s completed for %s in %.2fs", self.name, ticker, elapsed)
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            self.logger.error(
                "%s failed for %s after %.2fs: %s",
                self.name, ticker, elapsed, e,
                exc_info=True,
            )
            raise
