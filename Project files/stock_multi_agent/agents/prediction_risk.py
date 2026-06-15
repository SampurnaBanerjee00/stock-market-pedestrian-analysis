"""
agents/prediction_risk.py
──────────────────────────
Synthesises all agent outputs → BUY/SELL/HOLD signal with:
  - Confidence score
  - 1-week price target (INR)
  - Stop-loss level
  - Risk score
  - 1-day Value at Risk (VaR) %
  - Reasoning chain

LLM reflection via OpenAI GPT-3.5-turbo if OPENAI_API_KEY is set.
Falls back to rule-based logic otherwise.
"""
from __future__ import annotations
import logging
import math

from agents.base import BaseAgent
from config import OPENAI_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)


def _rule_based_signal(
    sentiment: float,
    rsi: float | None,
    macd_bullish: bool,
    trend: str,
    pe: float | None,
    fii_action: str,
    day_change_pct: float,
) -> tuple[str, float, list[str]]:
    """
    Returns (signal, confidence, reasoning_chain).
    Simple rule engine — used when OpenAI key is absent.
    """
    chain: list[str] = []
    score = 0.0  # positive → bullish

    # Sentiment
    if sentiment > 0.3:
        score += 2
        chain.append(f"Positive news sentiment ({sentiment:.2f}) → bullish bias")
    elif sentiment < -0.3:
        score -= 2
        chain.append(f"Negative news sentiment ({sentiment:.2f}) → bearish bias")
    else:
        chain.append(f"Neutral sentiment ({sentiment:.2f})")

    # RSI
    if rsi is not None:
        if rsi < 35:
            score += 2
            chain.append(f"RSI={rsi:.1f} oversold – potential reversal upward")
        elif rsi > 70:
            score -= 2
            chain.append(f"RSI={rsi:.1f} overbought – potential pullback risk")
        elif 40 <= rsi <= 60:
            score += 0.5
            chain.append(f"RSI={rsi:.1f} in healthy range")

    # MACD
    if macd_bullish:
        score += 1.5
        chain.append("MACD bullish crossover – upward momentum")
    else:
        score -= 1
        chain.append("MACD bearish – weakening momentum")

    # Trend
    if trend == "BULLISH":
        score += 2
        chain.append("Price above SMA20 > SMA50 – confirmed uptrend")
    elif trend == "BEARISH":
        score -= 2
        chain.append("Price below SMA20 < SMA50 – confirmed downtrend")

    # FII action
    if fii_action == "BUYING":
        score += 1
        chain.append("FIIs net buyers – institutional support")
    else:
        score -= 0.5
        chain.append("FIIs net sellers – institutional caution")

    # PE sanity (for Indian large-caps, <25 is value, >50 is expensive)
    if pe is not None:
        if pe < 20:
            score += 0.5
            chain.append(f"P/E={pe:.1f} – undervalued vs market average")
        elif pe > 50:
            score -= 1
            chain.append(f"P/E={pe:.1f} – expensive; limited upside priced in")

    # Determine nuanced dynamic signal
    if score >= 6:
        signal = "STRONG BUY"
        confidence = min(0.6 + score / 15, 0.98)
    elif score >= 3:
        signal = "BUY"
        confidence = min(0.5 + score / 20, 0.90)
    elif score >= 1:
        signal = "ACCUMULATE"
        confidence = 0.55 + (score / 30)
    elif score <= -6:
        signal = "STRONG SELL"
        confidence = min(0.6 + abs(score) / 15, 0.98)
    elif score <= -3:
        signal = "SELL"
        confidence = min(0.5 + abs(score) / 20, 0.90)
    elif score <= -1:
        signal = "REDUCE"
        confidence = 0.55 + (abs(score) / 30)
    else:
        signal = "NEUTRAL"
        # Confidence reflects how "centered" the neutral score is
        confidence = 0.5 + (abs(score) / 10) 
        confidence = min(confidence, 0.60)

    chain.append(
        f"Dynamic engine score={score:.1f} → {signal} (confidence={confidence:.2%})"
    )
    return signal, round(confidence, 2), chain


def _llm_reflection(prompt: str) -> str | None:
    """Call LLM (Groq or OpenAI) for narrative reasoning."""
    try:
        import openai  # type: ignore
        
        if GROQ_API_KEY:
            client = openai.OpenAI(
                api_key=GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1"
            )
            model = "llama3-70b-8192"
        elif OPENAI_API_KEY:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            model = "gpt-3.5-turbo"
        else:
            return None

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior Indian equity research analyst. "
                        "Given structured data, write a crisp 3-sentence investment thesis. "
                        "Focus on NSE-listed companies. Be factual, concise, and specific."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("LLM reflection failed: %s", e)
        return None


def _compute_var(price_history_returns: list[float], confidence: float = 0.95) -> float:
    """
    Historical VaR at given confidence level.
    Returns positive percentage (e.g. 2.5 means 2.5% potential 1-day loss).
    """
    if not price_history_returns:
        return 2.0  # default fallback
    sorted_returns = sorted(price_history_returns)
    idx = int((1 - confidence) * len(sorted_returns))
    var = abs(sorted_returns[max(idx, 0)])
    return round(var * 100, 2)


class PredictionRiskAgent(BaseAgent):
    name = "PredictionRiskAgent"

    def run(
        self,
        ticker: str,
        news_result: dict | None = None,
        fundamentals_result: dict | None = None,
        technical_result: dict | None = None,
        **kwargs,
    ) -> dict:
        self.logger.info("Running for ticker=%s", ticker)

        news = news_result or {}
        fund = fundamentals_result or {}
        tech = technical_result or {}

        sentiment = news.get("sentiment_score", 0.0)
        rsi = tech.get("rsi")
        macd_bullish = tech.get("macd_bullish", False)
        trend = tech.get("trend", "NEUTRAL")
        pe = fund.get("pe_ratio")
        fii_action = (fund.get("fii_dii_flow") or {}).get("fii_action", "SELLING")
        current_price = tech.get("current_price") or 100.0
        day_change_pct = tech.get("day_change_pct") or 0.0

        # ── Signal + reasoning chain ──────────────────────────────────────
        signal, confidence, chain = _rule_based_signal(
            sentiment=sentiment,
            rsi=rsi,
            macd_bullish=macd_bullish,
            trend=trend,
            pe=pe,
            fii_action=fii_action,
            day_change_pct=day_change_pct,
        )

        # ── Smart Price Targets (using Bollinger Bands & Volatility) ──────
        bb_upper = tech.get("bb_upper")
        bb_lower = tech.get("bb_lower")
        
        if "BUY" in signal or signal == "ACCUMULATE":
            # Target is the upper band or at least 4% upside
            price_target = round(max(bb_upper or 0, current_price * 1.04), 2)
            # Stop loss is the lower band or at most 3% downside
            stop_loss = round(min(bb_lower or current_price * 0.97, current_price * 0.97), 2)
        elif "SELL" in signal or signal == "REDUCE":
            price_target = round(min(bb_lower or 0, current_price * 0.96), 2)
            stop_loss = round(max(bb_upper or current_price * 1.03, current_price * 1.03), 2)
        else:
            price_target = round(current_price * 1.02, 2)
            stop_loss = round(current_price * 0.98, 2)

        # ── Real Risk Metrics from TechnicalAgent ─────────────────────────
        risk_score = tech.get("volatility") or 0.0
        var_1d_pct = tech.get("var_1d_pct") or 0.0

        # ── LLM reflection ────────────────────────────────────────────────
        llm_reasoning: str | None = None
        if GROQ_API_KEY or OPENAI_API_KEY:
            prompt = (
                f"Stock: {ticker}\n"
                f"Signal: {signal} (confidence {confidence:.0%})\n"
                f"Price: ₹{current_price:.2f}, Target: ₹{price_target:.2f}, Stop-loss: ₹{stop_loss:.2f}\n"
                f"RSI: {rsi}, Trend: {trend}, MACD bullish: {macd_bullish}\n"
                f"Sentiment: {sentiment:.2f}, FII: {fii_action}\n"
                f"P/E: {pe}, Risk score: {risk_score}\n"
                "Write a 3-sentence investment thesis for an Indian retail investor."
            )
            llm_reasoning = _llm_reflection(prompt)
            if llm_reasoning:
                chain.append(f"LLM reflection: {llm_reasoning}")
                self.logger.info("LLM reasoning obtained for %s", ticker)

        reasoning = llm_reasoning or (
            f"{signal} signal for {ticker}: "
            + "; ".join(chain[-3:])
        )

        result = {
            "ticker": ticker,
            "signal": signal,
            "confidence": confidence,
            "price_target": price_target,
            "stop_loss": stop_loss,
            "risk_score": risk_score,
            "var_1d_pct": var_1d_pct,
            "reasoning": reasoning,
            "reasoning_chain": chain,
        }

        self.logger.info(
            "Prediction %s: %s  confidence=%.2f  target=%.2f  stop=%.2f  risk=%.2f",
            ticker, signal, confidence, price_target, stop_loss, risk_score,
        )
        return result
