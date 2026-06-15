# 🇮🇳 NSE Multi-Agent Stock Analysis System

An autonomous multi-agent system for **Indian stock market (NSE/BSE)** analysis. Accepts TradingView webhooks and manual triggers, runs 5 specialised AI agents in parallel, and outputs BUY/SELL/HOLD signals with price targets, stop-loss, and risk scores.

---

## Architecture

```
WebhookEvent / Scheduler
         │
         ▼
 ┌─────────────────────┐
 │   OrchestratorAgent │  ◄── Master brain
 └──────┬──────────────┘
        │  ThreadPoolExecutor (parallel)
   ┌────┼──────────────────────────┐
   ▼    ▼                          ▼
NewsSentiment  Fundamentals    Technical
  Agent          Agent           Agent
   │    │                          │
   └────┴──────────────────────────┘
                   │
                   ▼
         PredictionRisk Agent
         (rule-based + LLM)
                   │
                   ▼
           Output Agent
     (JSON file + Discord)
```

### Agents

| Agent | Role |
|---|---|
| **OrchestratorAgent** | Receives events, dispatches sub-agents in parallel, assembles final result |
| **NewsSentimentAgent** | Fetches NewsAPI articles, scores sentiment via keyword analysis + mock social |
| **FundamentalsAgent** | Pulls P/E, Market Cap, ROE, Debt/Equity via yfinance; mock FII/DII flows |
| **TechnicalAgent** | RSI, MACD, Bollinger Bands, SMAs, Volume ratio via pandas-ta |
| **PredictionRiskAgent** | Synthesises all data → BUY/SELL/HOLD + price target + VaR + stop-loss |
| **OutputAgent** | Saves `outputs/latest_signal.json`, sends Discord embed |

---

## Quick Start

### 1. Clone & Setup Virtual Environment

```bash
git clone <repo>
cd stock_multi_agent

# Python 3.10 venv (you've already created this)
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
NEWS_API_KEY=your_key_here          # Free at https://newsapi.org
OPENAI_API_KEY=sk-...               # Optional – for LLM reasoning step
DISCORD_WEBHOOK_URL=https://...     # Optional – Discord notification
USE_REDIS=True                      # Set False for demo without Redis
WATCHLIST=RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS
```

### 3. Install Redis (Required if USE_REDIS=True)

#### Ubuntu / WSL
```bash
sudo apt update && sudo apt install redis-server -y
sudo systemctl enable redis-server
redis-server --daemonize yes
redis-cli ping   # should return PONG
```

#### macOS (Homebrew)
```bash
brew install redis
brew services start redis
redis-cli ping
```

#### Windows
Use WSL (recommended) or download from:
https://github.com/microsoftarchive/redis/releases

### 4. Start Services

Open **3 terminals** in your virtualenv:

**Terminal 1 – FastAPI**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 – Celery Worker** (skip if USE_REDIS=False)
```bash
celery -A celery_worker worker --loglevel=info --concurrency=2
```

**Terminal 3 – Optional: Standalone Scheduler** (already embedded in FastAPI)
```bash
python scheduler.py
```

---

## Running WITHOUT Redis (Demo Mode)

Set `USE_REDIS=False` in `.env`.

Only start FastAPI — a background thread handles tasks:
```bash
uvicorn main:app --reload
```

> ⚠️ **Limitations of fallback mode:**
> - State lost on restart
> - No multi-worker support
> - No crash recovery
> - For demo / development only

---

## API Reference

### Trigger Analysis via Webhook

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "RELIANCE.NS",
    "event_type": "earnings_reminder",
    "price": 2950.0,
    "timestamp": "2025-05-15T09:30:00Z"
  }'
```

Response:
```json
{"task_id": "550e8400-e29b-41d4-a716-446655440000", "status": "queued"}
```

### Check Task Status

```bash
curl http://localhost:8000/status/550e8400-e29b-41d4-a716-446655440000
```

### Manual Single-Stock Scan

```bash
curl -X POST http://localhost:8000/scan/TCS
```

### Get Latest Signal

```bash
curl http://localhost:8000/signals/latest
```

### Health Check

```bash
curl http://localhost:8000/health
```

---

## Example Output Signal

```json
{
  "ticker": "RELIANCE.NS",
  "event_type": "earnings_reminder",
  "generated_at": "2025-05-15T09:35:22.123456+00:00",
  "prediction": {
    "signal": "BUY",
    "confidence": 0.74,
    "price_target": 3108.50,
    "stop_loss": 2806.25,
    "risk_score": 0.31,
    "var_1d_pct": 1.85,
    "reasoning": "BUY signal for RELIANCE.NS: RSI=42.1 oversold – potential reversal; MACD bullish crossover; FIIs net buyers",
    "reasoning_chain": [...]
  },
  "technical": {
    "rsi": 42.1,
    "macd_bullish": true,
    "trend": "BULLISH",
    ...
  }
}
```

---

## NSE Ticker Format

Use Yahoo Finance NSE format: append `.NS` for NSE, `.BO` for BSE.

| Company | Ticker |
|---|---|
| Reliance Industries | `RELIANCE.NS` |
| TCS | `TCS.NS` |
| Infosys | `INFY.NS` |
| HDFC Bank | `HDFCBANK.NS` |
| ICICI Bank | `ICICIBANK.NS` |
| Wipro | `WIPRO.NS` |
| SBI | `SBIN.NS` |
| Bharti Airtel | `BHARTIARTL.NS` |
| Kotak Bank | `KOTAKBANK.NS` |
| Bajaj Finance | `BAJFINANCE.NS` |

---

## TradingView Webhook Setup

In TradingView Alert → Webhook URL:
```
http://YOUR_SERVER_IP:8000/webhook
```

Webhook message body:
```json
{
  "ticker": "{{ticker}}",
  "event_type": "{{strategy.order.action}}",
  "price": {{close}},
  "timestamp": "{{time}}"
}
```

Note: TradingView uses plain tickers (e.g. `RELIANCE`). The system auto-appends `.NS`.

---

## Scheduler

The APScheduler runs automatically inside FastAPI:
- **Every 30 minutes** (configurable via `SCAN_INTERVAL_MINUTES`) during NSE hours (09:15–15:30 IST, Mon–Fri)
- **09:00 IST** pre-market scan on weekdays

---

## Data Sources

| Data | Source | Notes |
|---|---|---|
| Price / OHLCV | yfinance | Free, no API key needed |
| Fundamentals | yfinance | Free |
| News | NewsAPI | Free tier: 100 req/day |
| Social Sentiment | Mock | Replace with Twitter/Reddit API |
| FII/DII Flows | Mock | Real data: NSE website EOD |
| LLM Reasoning | OpenAI GPT-3.5 | Optional; falls back to rules |

---

## Project Structure

```
stock_multi_agent/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── config.py              # Centralised config from .env
├── main.py                # FastAPI app
├── celery_worker.py       # Celery tasks + fallback worker
├── scheduler.py           # APScheduler periodic scans
├── agents/
│   ├── base.py
│   ├── orchestrator.py    ← Master agent
│   ├── news_sentiment.py
│   ├── fundamentals.py
│   ├── technical.py
│   ├── prediction_risk.py
│   └── output.py
├── tools/
│   ├── yfinance_wrapper.py
│   ├── indicators.py
│   ├── news_client.py
│   ├── sentiment_mock.py
│   └── fii_dii_mock.py
├── models/
│   └── schemas.py
├── state/
│   └── task_store.py      # In-memory fallback queue
└── outputs/               # Generated signals stored here
```

---

## Disclaimer

> This software is for **educational and research purposes only**. It does not constitute financial advice. Past performance of signals does not guarantee future results. Always conduct your own due diligence before making investment decisions. FII/DII flows shown are **mock data**.
