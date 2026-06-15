"""
tools/yfinance_wrapper.py
─────────────────────────
Thin wrapper around yfinance with retry logic.
Handles NSE ticker format (e.g. RELIANCE.NS, TCS.NS).
"""
from __future__ import annotations
import logging
from typing import Optional

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


def _nse_ticker(ticker: str) -> str:
    """Ensure ticker has .NS suffix for NSE stocks and map common names."""
    ticker = ticker.upper().strip()
    
    # Common name mappings
    mappings = {
        "INFOSYS": "INFY",
        "HDFC": "HDFCBANK",
        "KOTAK": "KOTAKBANK",
        "BAJAJ": "BAJFINANCE",
        "ADANI": "ADANIENT"
    }
    
    if ticker in mappings:
        ticker = mappings[ticker]

    if not ticker.endswith((".NS", ".BO")):
        ticker += ".NS"
    return ticker


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=1, max=4),
    retry=retry_if_exception_type(Exception),
    reraise=False,
)
def get_ticker_info(ticker: str) -> dict:
    """Return yfinance .info dict with faster timeouts."""
    t = _nse_ticker(ticker)
    yf_obj = yf.Ticker(t)
    
    # Pre-fetch fast_info which is almost instant
    fast = yf_obj.fast_info
    
    try:
        # This is the slow part. We wrap it.
        info = yf_obj.info or {}
    except Exception:
        info = {}

    # Supplement with fast_info if needed
    if not info:
        info = {
            "longName": t,
            "currentPrice": fast.get("last_price"),
            "marketCap": fast.get("market_cap"),
            "sector": "N/A",
            "industry": "N/A",
            "longBusinessSummary": "Information fetching timed out. Please try again."
        }
    return info


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_price_history(
    ticker: str,
    period: str = "3mo",
    interval: str = "1d",
) -> pd.DataFrame:
    """Return OHLCV DataFrame for the given period."""
    t = _nse_ticker(ticker)
    logger.debug("Fetching history for %s  period=%s  interval=%s", t, period, interval)
    df = yf.download(t, period=period, interval=interval, progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No price data returned for {t}")
    return df


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_earnings_dates(ticker: str) -> Optional[str]:
    """Return next earnings date as ISO string, or None."""
    try:
        t = _nse_ticker(ticker)
        yf_obj = yf.Ticker(t)
        cal = yf_obj.calendar
        if cal is not None and not cal.empty:
            # calendar is a DataFrame; earnings date in index
            if "Earnings Date" in cal.index:
                val = cal.loc["Earnings Date"].iloc[0]
                return str(val)
    except Exception as e:
        logger.warning("Could not fetch earnings date for %s: %s", ticker, e)
    return None
