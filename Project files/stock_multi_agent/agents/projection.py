"""
ProjectionAgent – Autonomous Time-Series Growth Forecasting
────────────────────────────────────────────────────────────
Calculates price targets and investment simulations for 5D, 10D, and 30D horizons.
"""
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class ProjectionAgent:
    def __init__(self):
        self.name = "ProjectionAgent"

    def run(self, ticker: str, technical_data: Dict[str, Any], sentiment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decomposes technical trends and sentiment to project future price targets.
        """
        logger.info("%s: Calculating growth projections for %s", self.name, ticker)
        
        try:
            current_price = technical_data.get("latest_price", 0)
            rsi = technical_data.get("indicators", {}).get("RSI", 50)
            sma_20 = technical_data.get("indicators", {}).get("SMA_20", current_price)
            sentiment_score = sentiment_data.get("sentiment_score", 0) # -1 to 1
            
            # Momentum Factor Calculation
            # If RSI > 60 and Sentiment > 0.2, high momentum.
            # If RSI < 40 and Sentiment < -0.2, bearish momentum.
            momentum = 0
            if rsi > 60: momentum += 0.02
            if rsi < 40: momentum -= 0.02
            if current_price > sma_20: momentum += 0.01
            else: momentum -= 0.01
            
            # Sentiment weighting (Longer term impact)
            momentum += (sentiment_score * 0.03)

            # Projections based on daily compound logic
            def calculate_target(days: int, bias: float) -> float:
                # Basic drift + momentum
                return current_price * (1 + (bias * (days / 5)))

            projections = {
                "5d": {
                    "target": round(calculate_target(5, momentum), 2),
                    "expected_gain_pct": round(momentum * 100, 2)
                },
                "10d": {
                    "target": round(calculate_target(10, momentum * 0.8), 2), # Decay factor
                    "expected_gain_pct": round(momentum * 0.8 * 2 * 100, 2)
                },
                "30d": {
                    "target": round(calculate_target(30, momentum * 0.5), 2), # Long term stability
                    "expected_gain_pct": round(momentum * 0.5 * 6 * 100, 2)
                }
            }

            # Investment Simulation (₹100,000 Base)
            base_amt = 100000
            simulation = {
                "initial": base_amt,
                "after_5d": round(base_amt * (1 + (projections["5d"]["expected_gain_pct"] / 100)), 0),
                "after_10d": round(base_amt * (1 + (projections["10d"]["expected_gain_pct"] / 100)), 0),
                "after_30d": round(base_amt * (1 + (projections["30d"]["expected_gain_pct"] / 100)), 0)
            }

            return {
                "ticker": ticker,
                "projections": projections,
                "simulation": simulation,
                "thesis": f"Based on RSI of {rsi:.2f} and a sentiment score of {sentiment_score:.2f}, the asset shows a {'bullish' if momentum > 0 else 'bearish'} trajectory."
            }
            
        except Exception as e:
            logger.error("Projection Error: %s", e)
            return {"error": str(e)}
