"""
tools/indicators.py
───────────────────
Compute RSI, MACD, Bollinger Bands, SMAs using pandas-ta.
"""
from __future__ import annotations
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _safe_float(val) -> Optional[float]:
    try:
        v = float(val)
        return round(v, 4) if v == v else None  # NaN check
    except (TypeError, ValueError):
        return None


def compute_indicators(df: pd.DataFrame) -> dict:
    """
    Accept an OHLCV DataFrame and return computed indicator dict.
    Requires columns: Open, High, Low, Close, Volume
    """
    try:
        import pandas_ta_classic as ta  # noqa: PLC0415
    except ImportError:
        logger.error("pandas-ta-classic not installed. Run: pip install pandas-ta-classic")
        return {}

    # Flatten MultiIndex columns if present (yfinance sometimes returns them)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.copy()

    # ── RSI (14) ─────────────────────────────────────────────────────────
    rsi_series = ta.rsi(df["Close"], length=14)
    rsi = _safe_float(rsi_series.iloc[-1]) if rsi_series is not None else None

    # ── MACD (12, 26, 9) ─────────────────────────────────────────────────
    macd_df = ta.macd(df["Close"])
    macd_val, macd_signal_val, macd_bullish = None, None, False
    if macd_df is not None and not macd_df.empty:
        macd_val = _safe_float(macd_df.iloc[-1, 0])        # MACD_12_26_9
        macd_signal_val = _safe_float(macd_df.iloc[-1, 2]) # MACDs_12_26_9
        if macd_val is not None and macd_signal_val is not None:
            macd_bullish = macd_val > macd_signal_val

    # ── SMAs ─────────────────────────────────────────────────────────────
    sma20 = _safe_float(ta.sma(df["Close"], length=20).iloc[-1])
    sma50_s = ta.sma(df["Close"], length=50)
    sma50 = _safe_float(sma50_s.iloc[-1]) if sma50_s is not None and len(sma50_s) >= 50 else None
    sma200_s = ta.sma(df["Close"], length=200)
    sma200 = _safe_float(sma200_s.iloc[-1]) if sma200_s is not None and len(sma200_s) >= 200 else None

    # ── Bollinger Bands (20, 2) ───────────────────────────────────────────
    bb_df = ta.bbands(df["Close"], length=20, std=2)
    bb_upper, bb_lower = None, None
    if bb_df is not None and not bb_df.empty:
        bb_upper = _safe_float(bb_df.iloc[-1][bb_df.columns[2]])  # BBU
        bb_lower = _safe_float(bb_df.iloc[-1][bb_df.columns[0]])  # BBL

    # ── Volume ratio ──────────────────────────────────────────────────────
    vol_avg = df["Volume"].rolling(20).mean().iloc[-1]
    vol_ratio = _safe_float(df["Volume"].iloc[-1] / vol_avg) if vol_avg and vol_avg > 0 else None

    # ── Current price and change ─────────────────────────────────────────
    # Ensure we have data and drop NaNs for the latest price
    clean_close = df["Close"].dropna()
    if clean_close.empty:
        return {}

    current_price = _safe_float(clean_close.iloc[-1])
    prev_close = _safe_float(clean_close.iloc[-2]) if len(clean_close) > 1 else current_price
    day_change_pct = 0.0
    if current_price and prev_close and prev_close != 0:
        day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

    # ── Price history for sparkline (last 20 points) ─────────────────────
    price_history = [round(float(x), 2) for x in clean_close.tail(20).tolist()]

    # ── Real Risk Metrics (Volatility & VaR) ─────────────────────────────
    # Calculate daily returns
    returns = clean_close.pct_change().dropna()
    
    # 1. Risk Score (Annualized Volatility)
    # 20-day rolling std * sqrt(252 days)
    volatility = 0.0
    if len(returns) >= 10:
        volatility = round(float(returns.tail(20).std() * (252 ** 0.5)), 3)
    
    # 2. 1D Value at Risk (Historical 95% confidence)
    var_1d = 0.0
    if len(returns) >= 20:
        # 5th percentile of returns
        var_1d = round(abs(float(returns.tail(100).quantile(0.05))) * 100, 2)

    # ── Trend determination ───────────────────────────────────────────────
    trend = "NEUTRAL"
    if current_price and sma20 and sma50:
        if current_price > sma20 > sma50:
            trend = "BULLISH"
        elif current_price < sma20 < sma50:
            trend = "BEARISH"

    return {
        "current_price": current_price,
        "prev_close": prev_close,
        "day_change_pct": day_change_pct,
        "price_history": price_history,
        "volatility": volatility,
        "var_1d_pct": var_1d,
        "rsi": rsi,
        "macd": macd_val,
        "macd_signal": macd_signal_val,
        "macd_bullish": macd_bullish,
        "sma_20": sma20,
        "sma_50": sma50,
        "sma_200": sma200,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "volume_avg_ratio": vol_ratio,
        "trend": trend,
    }
