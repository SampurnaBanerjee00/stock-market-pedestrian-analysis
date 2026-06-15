"""
tools/sentiment_mock.py
───────────────────────
Mock social media sentiment for NSE stocks.
In production, replace with Twitter/X API, Reddit PRAW, or a
dedicated NLP sentiment service.

Returns a score in [-1.0, +1.0]:
  +1.0 = extremely bullish social sentiment
  -1.0 = extremely bearish social sentiment
"""
from __future__ import annotations
import hashlib
import random
import time
import logging

logger = logging.getLogger(__name__)

# Seed per-ticker so the value is semi-stable within a session
_CACHE: dict[str, tuple[float, float]] = {}   # ticker → (score, timestamp)
CACHE_TTL = 600  # seconds


def get_social_sentiment(ticker: str) -> dict:
    """
    Return mock social sentiment for the given ticker.
    Uses a time-seeded random so values drift slowly.
    """
    now = time.time()
    if ticker in _CACHE:
        score, ts = _CACHE[ticker]
        if now - ts < CACHE_TTL:
            logger.debug("Sentiment cache hit for %s: %.3f", ticker, score)
            return {"ticker": ticker, "social_sentiment": score, "source": "mock_cache"}

    # Seed based on ticker + current hour for slow drift
    hour_bucket = int(now // 3600)
    seed = int(hashlib.md5(f"{ticker}{hour_bucket}".encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    score = round(rng.uniform(-0.5, 0.5), 3)

    _CACHE[ticker] = (score, now)
    logger.info("Mock social sentiment for %s: %.3f", ticker, score)
    return {"ticker": ticker, "social_sentiment": score, "source": "mock"}
