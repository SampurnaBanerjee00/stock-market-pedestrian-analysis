"""
agents/output.py
─────────────────
Formats the final signal, saves to disk, and optionally sends to Discord.
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

from agents.base import BaseAgent
from config import DISCORD_WEBHOOK_URL, OUTPUTS_DIR

logger = logging.getLogger(__name__)


def _signal_emoji(signal: str) -> str:
    return {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(signal, "⚪")


def _risk_bar(risk: float) -> str:
    filled = round(risk * 10)
    return "█" * filled + "░" * (10 - filled)


class OutputAgent(BaseAgent):
    name = "OutputAgent"

    def run(self, ticker: str, final_signal: dict, **kwargs) -> dict:
        self.logger.info("Running for ticker=%s", ticker)

        pred = final_signal.get("prediction", {})
        tech = final_signal.get("technical", {})
        fund = final_signal.get("fundamentals", {})
        news = final_signal.get("news", {})

        signal = pred.get("signal", "HOLD")
        confidence = pred.get("confidence", 0.0)
        price_target = pred.get("price_target", 0.0)
        stop_loss = pred.get("stop_loss", 0.0)
        risk_score = pred.get("risk_score", 0.5)
        var_1d = pred.get("var_1d_pct", 0.0)
        reasoning = pred.get("reasoning", "")

        current_price = tech.get("current_price", 0.0)
        rsi = tech.get("rsi", 0.0)
        trend = tech.get("trend", "NEUTRAL")

        sentiment = news.get("sentiment_score", 0.0)
        fii_action = (fund.get("fii_dii_flow") or {}).get("fii_action", "?")

        # ── Save JSON ─────────────────────────────────────────────────────
        output_path = OUTPUTS_DIR / "latest_signal.json"
        ticker_path = OUTPUTS_DIR / f"{ticker.replace('.', '_')}_signal.json"

        for path in (output_path, ticker_path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(final_signal, f, indent=2, default=str)
        self.logger.info("Signal saved to %s", output_path)

        # ── Discord webhook ───────────────────────────────────────────────
        discord_sent = False
        if DISCORD_WEBHOOK_URL:
            discord_sent = _send_discord(
                ticker=ticker,
                signal=signal,
                confidence=confidence,
                current_price=current_price,
                price_target=price_target,
                stop_loss=stop_loss,
                risk_score=risk_score,
                var_1d=var_1d,
                rsi=rsi,
                trend=trend,
                sentiment=sentiment,
                fii_action=fii_action,
                reasoning=reasoning,
            )

        return {
            "ticker": ticker,
            "signal": signal,
            "saved_to": str(output_path),
            "discord_sent": discord_sent,
        }


def _send_discord(
    ticker: str,
    signal: str,
    confidence: float,
    current_price: float,
    price_target: float,
    stop_loss: float,
    risk_score: float,
    var_1d: float,
    rsi: float,
    trend: str,
    sentiment: float,
    fii_action: str,
    reasoning: str,
) -> bool:
    emoji = _signal_emoji(signal)
    risk_bar = _risk_bar(risk_score)
    pnl_pct = 0.0
    if current_price is not None and price_target is not None and current_price != 0:
        pnl_pct = ((price_target - current_price) / current_price * 100)

    embed = {
        "title": f"{emoji} {ticker} — **{signal}** Signal",
        "color": {"BUY": 0x00C853, "SELL": 0xD50000, "HOLD": 0xFFD600}.get(signal, 0x757575),
        "description": f"> {reasoning[:300]}",
        "fields": [
            {"name": "📈 Current Price", "value": f"₹{current_price:,.2f}" if current_price is not None else "N/A", "inline": True},
            {"name": "🎯 Target", "value": f"₹{price_target:,.2f} ({pnl_pct:+.1f}%)" if price_target is not None else "N/A", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"₹{stop_loss:,.2f}" if stop_loss is not None else "N/A", "inline": True},
            {"name": "💪 Confidence", "value": f"{confidence:.0%}" if confidence is not None else "0%", "inline": True},
            {"name": "⚠️ Risk Score", "value": f"{risk_bar} {risk_score:.2f}" if risk_score is not None else "N/A", "inline": True},
            {"name": "📉 1-Day VaR", "value": f"{var_1d:.2f}%" if var_1d is not None else "N/A", "inline": True},
            {"name": "📊 RSI", "value": f"{rsi:.1f}" if rsi is not None else "N/A", "inline": True},
            {"name": "📈 Trend", "value": trend or "NEUTRAL", "inline": True},
            {"name": "🗞️ Sentiment", "value": f"{sentiment:+.2f}" if sentiment is not None else "0.00", "inline": True},
            {"name": "🏦 FII Flow", "value": fii_action or "UNKNOWN", "inline": True},
        ],
        "footer": {"text": f"NSE Signal • {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}"},
        "thumbnail": {"url": "https://nseindia.com/favicon.ico"},
    }

    payload = {"embeds": [embed]}
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Discord webhook sent for %s", ticker)
        return True
    except Exception as e:
        logger.warning("Discord webhook failed: %s", e)
        return False
