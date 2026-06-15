"""
agents/news_sentiment.py
────────────────────────
Fetches news + social sentiment and computes a composite score.
Now includes AI-powered Narrative Synthesis.
"""
from __future__ import annotations
import re
import logging
import openai
from typing import Any

from agents.base import BaseAgent
from tools.news_client import fetch_news
from tools.sentiment_mock import get_social_sentiment
from config import OPENAI_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)

# Very simple keyword-based sentiment (no external NLP dependency)
POSITIVE_WORDS = {
    "beat", "surpass", "growth", "profit", "surge", "up", "gain", "positive",
    "strong", "bullish", "buy", "upgrade", "record", "expand", "win", "boost",
    "outperform", "rally", "rise", "higher", "increase", "robust", "dividend",
    "buy-back", "buyback", "acquisition", "merger", "order", "contract",
}
NEGATIVE_WORDS = {
    "miss", "fall", "loss", "drop", "down", "decline", "weak", "bearish", "sell",
    "downgrade", "cut", "risk", "slump", "concern", "negative", "lower", "reduce",
    "fraud", "probe", "penalty", "default", "debt", "layoff", "slowdown",
}

def _keyword_sentiment(text: str) -> float:
    """Returns [-1, +1] based on keyword counts."""
    words = set(re.findall(r"\b\w+\b", text.lower()))
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)

def _generate_narrative(ticker: str, headlines: list[str], sentiment: float) -> str:
    """Generate a crisp news summary via LLM or Heuristics."""
    if not headlines:
        return "The news landscape for this asset is currently quiet."

    prompt = f"Summarize the market narrative for {ticker} based on these headlines: {'; '.join(headlines)}. Sentiment score is {sentiment}."
    
    try:
        if GROQ_API_KEY:
            client = openai.OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
            model = "llama3-70b-8192"
        elif OPENAI_API_KEY:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            model = "gpt-3.5-turbo"
        else:
            # Fallback Heuristic
            label = "bullish" if sentiment > 0.1 else ("bearish" if sentiment < -0.1 else "mixed")
            return f"Market news for {ticker} shows a {label} narrative. Primary themes include {headlines[0] if headlines else 'ongoing operations'}. Investors are monitoring current volatility."

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional financial journalist. Write a 2-3 sentence summary of the news landscape for the given stock. Be concise and professional."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.4
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Narrative generation failed: %s", e)
        return f"News flow indicates {('positive' if sentiment > 0 else 'cautious')} sentiment. Key focus: {headlines[0]}."

class NewsSentimentAgent(BaseAgent):
    name = "NewsSentimentAgent"

    def run(self, ticker: str, **kwargs) -> dict:
        self.logger.info("Running for ticker=%s", ticker)

        # ── News ─────────────────────────────────────────────────────────
        news_data = fetch_news(ticker, max_articles=8)
        headlines = news_data.get("headlines", [])

        # Score each headline and average
        headline_scores = [_keyword_sentiment(h) for h in headlines]
        news_sentiment = (
            round(sum(headline_scores) / len(headline_scores), 3)
            if headline_scores else 0.0
        )

        # ── Social ────────────────────────────────────────────────────────
        social_data = get_social_sentiment(ticker)
        social_score = social_data.get("social_sentiment", 0.0)

        # ── Composite: 70% news, 30% social ──────────────────────────────
        composite = round(0.70 * news_sentiment + 0.30 * social_score, 3)

        # ── Narrative Synthesis ──────────────────────────────────────────
        summary = _generate_narrative(ticker, headlines, composite)

        result = {
            "ticker": ticker,
            "articles_fetched": len(headlines),
            "sentiment_score": composite,
            "news_sentiment": news_sentiment,
            "social_sentiment": social_score,
            "summary": summary,
            "top_headlines": headlines[:5],
            "top_articles": news_data.get("articles", [])[:3],
            "news_source": news_data.get("source", "unknown"),
        }
        self.logger.info(
            "Sentiment for %s: composite=%.3f (summary=%s)",
            ticker, composite, summary[:50] + "..."
        )
        return result
