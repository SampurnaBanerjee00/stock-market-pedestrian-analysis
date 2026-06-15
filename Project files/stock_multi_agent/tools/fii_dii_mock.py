"""
tools/fii_dii_mock.py
──────────────────────
Mock FII (Foreign Institutional Investor) and DII (Domestic Institutional
Investor) net buy/sell flows in crores INR.

⚠️  MOCK DATA – Real FII/DII data is published by NSE/BSE at end of day.
In production, scrape https://www.nseindia.com/market-data/fpi-monthly-data
or use a paid data vendor.

Positive = net buyers, Negative = net sellers.
"""
from __future__ import annotations
import hashlib
import random
import time
import logging

logger = logging.getLogger(__name__)

_CACHE: dict[str, tuple[dict, float]] = {}
CACHE_TTL = 1800  # 30 minutes


def get_fii_dii_flows(ticker: str) -> dict:
    """
    Returns estimated FII & DII flows in crores INR (mock).
    """
    now = time.time()
    if ticker in _CACHE:
        data, ts = _CACHE[ticker]
        if now - ts < CACHE_TTL:
            return data

    day_bucket = int(now // 86400)
    seed = int(hashlib.md5(f"fiidii{ticker}{day_bucket}".encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    fii_flow = round(rng.uniform(-3000, 5000), 2)   # crores
    dii_flow = round(rng.uniform(-2000, 4000), 2)   # crores

    # Correlated: when FIIs sell heavily, DIIs often absorb
    if fii_flow < -1500:
        dii_flow = abs(dii_flow) * rng.uniform(0.8, 1.5)

    data = {
        "ticker": ticker,
        "fii_net_crore": fii_flow,
        "dii_net_crore": dii_flow,
        "total_institutional_flow_crore": round(fii_flow + dii_flow, 2),
        "fii_action": "BUYING" if fii_flow > 0 else "SELLING",
        "dii_action": "BUYING" if dii_flow > 0 else "SELLING",
        "is_mock": True,
        "note": (
            "Mock data – real FII/DII flows available on NSE website post market hours."
        ),
    }

    _CACHE[ticker] = (data, now)
    logger.info(
        "Mock FII/DII for %s: FII=%.0f Cr, DII=%.0f Cr",
        ticker, fii_flow, dii_flow,
    )
    return data
