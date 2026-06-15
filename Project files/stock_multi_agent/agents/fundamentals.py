"""
agents/fundamentals.py
───────────────────────
Fetches fundamental data for NSE stocks via yfinance.
FII/DII flows are mock (real data requires NSE API or paid vendor).
"""
from __future__ import annotations
import logging

from agents.base import BaseAgent
from tools.yfinance_wrapper import get_ticker_info, get_earnings_dates
from tools.fii_dii_mock import get_fii_dii_flows

logger = logging.getLogger(__name__)

INR_TO_CR = 1e7   # 1 crore = 10,000,000


def _to_cr(val) -> float | None:
    """Convert raw INR value to crores, or return None."""
    try:
        return round(float(val) / INR_TO_CR, 2)
    except (TypeError, ValueError):
        return None


# Simple in-memory cache for static company info (Description, Sector, etc.)
INFO_CACHE: dict[str, dict] = {}

class FundamentalsAgent(BaseAgent):
    name = "FundamentalsAgent"

    def run(self, ticker: str, **kwargs) -> dict:
        self.logger.info("Running for ticker=%s", ticker)

        if ticker in INFO_CACHE:
            self.logger.info("Using cached info for %s", ticker)
            info = INFO_CACHE[ticker]
        else:
            try:
                info = get_ticker_info(ticker)
                # Cache only the static parts to save memory
                INFO_CACHE[ticker] = info
            except Exception as e:
                self.logger.warning("Could not fetch yfinance info for %s: %s", ticker, e)
                info = {}

        # ── Key metrics ──────────────────────────────────────────────────
        def _f(key) -> float | None:
            try:
                v = info.get(key)
                return round(float(v), 4) if v is not None else None
            except (TypeError, ValueError):
                return None

        pe = _f("trailingPE") or _f("forwardPE")
        pb = _f("priceToBook")
        market_cap_raw = info.get("marketCap")
        market_cap_cr = _to_cr(market_cap_raw)
        debt_equity = _f("debtToEquity")
        roe = _f("returnOnEquity")
        if roe is not None:
            roe = round(roe * 100, 2)  # convert to %

        company_name = info.get("longName") or info.get("shortName") or ticker
        sector = info.get("sector") or "Unknown"
        industry = info.get("industry") or "Unknown"
        description = info.get("longBusinessSummary") or "No description available."

        # ── Earnings date ────────────────────────────────────────────────
        earnings_date = get_earnings_dates(ticker)

        # ── FII/DII flows (mock) ─────────────────────────────────────────
        flows = get_fii_dii_flows(ticker)

        result = {
            "ticker": ticker,
            "company_name": company_name,
            "sector": sector,
            "industry": industry,
            "description": description,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "market_cap_cr": market_cap_cr,
            "debt_equity": debt_equity,
            "roe": roe,
            "earnings_date": earnings_date,
            "fii_dii_flow": {
                "fii_net_crore": flows["fii_net_crore"],
                "dii_net_crore": flows["dii_net_crore"],
                "total_crore": flows["total_institutional_flow_crore"],
                "fii_action": flows["fii_action"],
                "dii_action": flows["dii_action"],
            },
            "is_mock": True,
        }

        self.logger.info(
            "Fundamentals %s: P/E=%.1f  MarketCap=%.0f Cr  FII=%s",
            ticker,
            pe or 0,
            market_cap_cr or 0,
            flows["fii_action"],
        )
        return result
