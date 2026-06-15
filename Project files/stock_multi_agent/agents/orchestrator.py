"""
agents/orchestrator.py
──────────────────────
Master agent that:
1. Receives a ticker + event payload.
2. Runs News, Fundamentals, Technical agents in parallel (ThreadPoolExecutor).
3. Passes results to PredictionRiskAgent.
4. Calls OutputAgent to save/dispatch.
5. Returns the complete FinalSignal dict.
"""
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from typing import Any

from agents.base import BaseAgent
from agents.news_sentiment import NewsSentimentAgent
from agents.fundamentals import FundamentalsAgent
from agents.technical import TechnicalAgent
from agents.prediction_risk import PredictionRiskAgent
from agents.output import OutputAgent

logger = logging.getLogger(__name__)

AGENT_TIMEOUT = 20  # Stable & Reliable timeout


class OrchestratorAgent(BaseAgent):
    name = "OrchestratorAgent"

    def __init__(self):
        super().__init__()
        self.news_agent = NewsSentimentAgent()
        self.fundamentals_agent = FundamentalsAgent()
        self.technical_agent = TechnicalAgent()
        self.prediction_agent = PredictionRiskAgent()
        self.output_agent = OutputAgent()

    def run(self, ticker: str, event_type: str = "manual", **kwargs) -> dict[str, Any]:
        self.logger.info(
            "Orchestrator: Task started for %s (event=%s)", ticker, event_type
        )

        # ── Step 1: Run research agents in parallel ───────────────────────
        news_result: dict = {}
        fundamentals_result: dict = {}
        technical_result: dict = {}
        errors: dict[str, str] = {}

        tasks = {
            "news": (self.news_agent.run, {"ticker": ticker}),
            "fundamentals": (self.fundamentals_agent.run, {"ticker": ticker}),
            "technical": (self.technical_agent.run, {"ticker": ticker}),
        }

        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="agent") as executor:
            future_map = {
                executor.submit(fn, **kw): name
                for name, (fn, kw) in tasks.items()
            }

            for future in as_completed(future_map, timeout=AGENT_TIMEOUT):
                name = future_map[future]
                try:
                    result = future.result(timeout=5)
                    if name == "news":
                        news_result = result
                    elif name == "fundamentals":
                        fundamentals_result = result
                    elif name == "technical":
                        technical_result = result
                    self.logger.info("Agent '%s' completed for %s", name, ticker)
                except FuturesTimeout:
                    errors[name] = "timeout"
                    self.logger.error("Agent '%s' timed out for %s", name, ticker)
                except Exception as e:
                    errors[name] = str(e)
                    self.logger.error(
                        "Agent '%s' failed for %s: %s", name, ticker, e, exc_info=True
                    )

        # ── Step 2: Prediction & Risk ─────────────────────────────────────
        try:
            prediction_result = self.prediction_agent.run(
                ticker=ticker,
                news_result=news_result,
                fundamentals_result=fundamentals_result,
                technical_result=technical_result,
            )
        except Exception as e:
            self.logger.error("PredictionRiskAgent failed: %s", e, exc_info=True)
            prediction_result = {
                "ticker": ticker,
                "signal": "HOLD",
                "confidence": 0.4,
                "price_target": technical_result.get("current_price", 0),
                "stop_loss": technical_result.get("current_price", 0) * 0.95,
                "risk_score": 0.8,
                "var_1d_pct": 3.0,
                "reasoning": f"Prediction failed: {e}",
                "reasoning_chain": [f"ERROR: {e}"],
            }
            errors["prediction"] = str(e)

        # ── Step 3: Assemble final signal ─────────────────────────────────
        final_signal: dict[str, Any] = {
            "ticker": ticker,
            "event_type": event_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "news": news_result,
            "fundamentals": fundamentals_result,
            "technical": technical_result,
            "prediction": prediction_result,
            "agent_errors": errors,
        }

        # ── Step 4: Output ────────────────────────────────────────────────
        try:
            # 5. Final Reporting
            output_result = self.output_agent.run(ticker=ticker, final_signal=final_signal)
            final_signal["output"] = output_result
        except Exception as e:
            self.logger.error("OutputAgent failed: %s", e, exc_info=True)
            final_signal["output"] = {"error": str(e)}

        self.logger.info(
            "Orchestrator: Completed %s → %s (confidence=%.2f)",
            ticker,
            prediction_result.get("signal"),
            prediction_result.get("confidence", 0),
        )
        return final_signal
