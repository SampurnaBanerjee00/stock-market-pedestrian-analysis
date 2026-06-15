"""
agents/technical.py
────────────────────
Fetches OHLCV data and computes technical indicators for NSE stocks.
"""
from __future__ import annotations
import logging

from agents.base import BaseAgent
from tools.yfinance_wrapper import get_price_history
from tools.indicators import compute_indicators

logger = logging.getLogger(__name__)


class TechnicalAgent(BaseAgent):
    name = "TechnicalAgent"

    def run(self, ticker: str, **kwargs) -> dict:
        self.logger.info("Running for ticker=%s", ticker)

        # Stable Mode: Fetch 3 months of daily data (Reliable)
        df = get_price_history(ticker, period="3mo", interval="1d")

        indicators = compute_indicators(df)

        result = {
            "ticker": ticker,
            **indicators,
        }

        self.logger.info(
            "Technical %s: price=%.2f  RSI=%.1f  MACD_bullish=%s  trend=%s",
            ticker,
            indicators.get("current_price") or 0,
            indicators.get("rsi") or 0,
            indicators.get("macd_bullish"),
            indicators.get("trend"),
        )
        return result
