"""
tools/news_client.py
────────────────────
Fetches news articles for a stock using NewsAPI.
Falls back to mock headlines if NEWS_API_KEY is not set.
"""
from __future__ import annotations
import logging
import random
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from config import NEWS_API_KEY

logger = logging.getLogger(__name__)

# Indian stock company name mappings (ticker → search term)
TICKER_TO_COMPANY = {
    "RELIANCE.NS": "Reliance Industries",
    "TCS.NS": "Tata Consultancy Services",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "WIPRO.NS": "Wipro",
    "AXISBANK.NS": "Axis Bank",
    "SBIN.NS": "State Bank of India",
    "BHARTIARTL.NS": "Bharti Airtel",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "LT.NS": "Larsen and Toubro",
    "BAJFINANCE.NS": "Bajaj Finance",
    "MARUTI.NS": "Maruti Suzuki",
    "TITAN.NS": "Titan Company",
}

MOCK_HEADLINES = [
    "{company} reports strong quarterly results beating analyst estimates",
    "{company} announces expansion into new business segments",
    "Analysts maintain BUY rating on {company} with revised target",
    "{company} Q4 earnings beat Street estimates; PAT up 18% YoY",
    "FIIs increase stake in {company} amid bullish market sentiment",
    "{company} management guides higher revenue growth for FY26",
    "RBI policy boost: {company} expected to benefit from rate cuts",
    "{company} wins large government contract worth ₹5,000 crore",
]


def _company_name(ticker: str) -> str:
    return TICKER_TO_COMPANY.get(ticker.upper(), ticker.replace(".NS", "").replace(".BO", ""))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=False,
)
def _fetch_from_newsapi(query: str, page_size: int = 5) -> list[dict]:
    from newsapi import NewsApiClient  # type: ignore
    client = NewsApiClient(api_key=NEWS_API_KEY)
    response = client.get_everything(
        q=query,
        language="en",
        sort_by="relevancy",
        page_size=page_size,
    )
    return response.get("articles", [])


def fetch_news(ticker: str, max_articles: int = 5) -> dict:
    """
    Returns:
        {
            "articles": [...],
            "headlines": ["...", ...],
            "source": "newsapi" | "mock"
        }
    """
    company = _company_name(ticker)

    if NEWS_API_KEY:
        try:
            articles = _fetch_from_newsapi(company, page_size=max_articles)
            headlines = [a.get("title", "") for a in articles if a.get("title")]
            logger.info("NewsAPI: fetched %d articles for %s", len(articles), ticker)
            return {
                "articles": articles,
                "headlines": headlines,
                "source": "newsapi",
            }
        except Exception as e:
            logger.warning("NewsAPI failed for %s: %s – falling back to mock", ticker, e)

    # ── Mock fallback ──────────────────────────────────────────────────────
    headlines = [
        random.choice(MOCK_HEADLINES).format(company=company)
        for _ in range(max_articles)
    ]
    logger.info("Mock news: generated %d headlines for %s", len(headlines), ticker)
    return {
        "articles": [],
        "headlines": headlines,
        "source": "mock",
    }
