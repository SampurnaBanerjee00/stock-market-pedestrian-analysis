"""
models/schemas.py – Pydantic models for requests, responses, and agent outputs.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Webhook Payload ─────────────────────────────────────────────────────────
class WebhookPayload(BaseModel):
    ticker: str = Field(..., examples=["RELIANCE.NS"])
    event_type: str = Field(..., examples=["price_above_ma", "earnings_reminder"])
    price: Optional[float] = Field(None, examples=[2500.0])
    timestamp: Optional[str] = Field(None, examples=["2025-05-15T14:00:00Z"])
    extra: Optional[dict[str, Any]] = None


# ─── Task response ────────────────────────────────────────────────────────────
class TaskResponse(BaseModel):
    task_id: str
    status: str  # queued | running | done | failed


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ─── Agent result schemas ─────────────────────────────────────────────────────
class NewsSentimentResult(BaseModel):
    ticker: str
    articles_fetched: int
    sentiment_score: float          # -1.0 to +1.0
    top_headlines: list[str]
    social_sentiment: float         # mock


class FundamentalsResult(BaseModel):
    ticker: str
    company_name: str
    sector: str
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    market_cap_cr: Optional[float]  # crores INR
    debt_equity: Optional[float]
    roe: Optional[float]
    earnings_date: Optional[str]
    fii_dii_flow: dict[str, float]  # mock flows in crores
    is_mock: bool = True


class TechnicalResult(BaseModel):
    ticker: str
    current_price: float
    prev_close: float
    day_change_pct: float
    rsi: Optional[float]
    macd: Optional[float]
    macd_signal: Optional[float]
    macd_bullish: bool
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    bb_upper: Optional[float]
    bb_lower: Optional[float]
    volume_avg_ratio: Optional[float]   # current vol / 20d avg vol
    trend: str                          # BULLISH | BEARISH | NEUTRAL


class PredictionRiskResult(BaseModel):
    ticker: str
    signal: str                  # BUY | SELL | HOLD
    confidence: float            # 0.0–1.0
    price_target: float          # 1-week target (INR)
    stop_loss: float
    risk_score: float            # 0.0–1.0 (higher = riskier)
    var_1d_pct: float            # 1-day Value at Risk %
    reasoning: str
    reasoning_chain: list[str]


class FinalSignal(BaseModel):
    ticker: str
    event_type: str
    generated_at: str
    news: NewsSentimentResult
    fundamentals: FundamentalsResult
    technical: TechnicalResult
    prediction: PredictionRiskResult
