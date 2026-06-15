"""
config.py – Central configuration loaded from .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / os.getenv("OUTPUTS_DIR", "outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── API Keys ────────────────────────────────────────────────────────────────
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

# ─── Queue / Redis ────────────────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
USE_REDIS: bool = os.getenv("USE_REDIS", "True").lower() in ("true", "1", "yes")

# ─── Market ───────────────────────────────────────────────────────────────────
MARKET: str = os.getenv("MARKET", "NSE")

# Default watchlist – NSE tickers in yfinance format (suffix .NS)
_raw_watchlist = os.getenv(
    "WATCHLIST",
    "RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS,ICICIBANK.NS,WIPRO.NS,HINDUNILVR.NS,SBIN.NS,BHARTIARTL.NS,ADANIENT.NS,KOTAKBANK.NS,LT.NS,BAJFINANCE.NS,MARUTI.NS,ZOMATO.NS",
)
WATCHLIST: list[str] = [t.strip() for t in _raw_watchlist.split(",") if t.strip()]

# ─── Scheduler ────────────────────────────────────────────────────────────────
SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ─── NSE Market Hours (IST) ───────────────────────────────────────────────────
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30
MARKET_TZ = "Asia/Kolkata"

# ─── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
