# stock-market-pedestrian-analysis

# 🇮🇳 NSE Multi-Agent Stock Analysis System

An autonomous multi-agent system for **Indian stock market (NSE/BSE)** analysis. The platform accepts TradingView webhooks and manual triggers, runs multiple specialized AI agents in parallel, and generates BUY/SELL/HOLD signals with price targets, stop-loss levels, confidence scores, and risk assessments.

---

## Architecture

```text
WebhookEvent / Scheduler
         │
         ▼
 ┌─────────────────────┐
 │   OrchestratorAgent │
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

| Agent               | Role                                                                       |
| ------------------- | -------------------------------------------------------------------------- |
| OrchestratorAgent   | Receives events, dispatches sub-agents in parallel, assembles final result |
| NewsSentimentAgent  | Fetches news articles and evaluates market sentiment                       |
| FundamentalsAgent   | Analyzes valuation metrics, profitability, and financial health            |
| TechnicalAgent      | Computes RSI, MACD, Bollinger Bands, SMAs, and volume indicators           |
| PredictionRiskAgent | Generates BUY/SELL/HOLD recommendation with risk assessment                |
| OutputAgent         | Stores signals and sends notifications                                     |

---

## Features

* Multi-agent architecture for modular stock analysis
* Parallel execution for improved performance
* Technical analysis using popular indicators
* Fundamental analysis based on financial metrics
* News sentiment evaluation
* Risk scoring and confidence estimation
* TradingView webhook integration
* Automated market scans through scheduling
* REST API built with FastAPI
* JSON signal generation and Discord notifications

---

## Quick Start

### 1. Clone & Setup Virtual Environment

```bash
git clone <repo>
cd stock_multi_agent

source venv/bin/activate
# Windows:
# venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
NEWS_API_KEY=your_key_here
OPENAI_API_KEY=sk-...
DISCORD_WEBHOOK_URL=https://...
USE_REDIS=True
WATCHLIST=RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS
```

### 3. Install Redis

#### Ubuntu / WSL

```bash
sudo apt update
sudo apt install redis-server -y
sudo systemctl enable redis-server
redis-server --daemonize yes
redis-cli ping
```

#### macOS

```bash
brew install redis
brew services start redis
redis-cli ping
```

#### Windows

Use WSL or install Redis-compatible alternatives.

### 4. Start Services

#### Terminal 1 – FastAPI

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Terminal 2 – Celery Worker

```bash
celery -A celery_worker worker --loglevel=info --concurrency=2
```

#### Terminal 3 – Scheduler (Optional)

```bash
python scheduler.py
```

---

## Running Without Redis

Set:

```env
USE_REDIS=False
```

Run only:

```bash
uvicorn main:app --reload
```

Limitations:

* State is not persisted after restart
* No multi-worker support
* No crash recovery
* Intended for development and testing

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
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

### Check Task Status

```bash
curl http://localhost:8000/status/{task_id}
```

### Manual Scan

```bash
curl -X POST http://localhost:8000/scan/TCS
```

### Latest Signal

```bash
curl http://localhost:8000/signals/latest
```

### Health Check

```bash
curl http://localhost:8000/health
```

---

## Example Output

```json
{
  "ticker": "RELIANCE.NS",
  "prediction": {
    "signal": "BUY",
    "confidence": 0.74,
    "price_target": 3108.50,
    "stop_loss": 2806.25,
    "risk_score": 0.31,
    "var_1d_pct": 1.85
  }
}
```

---

## NSE Ticker Format

| Company             | Ticker        |
| ------------------- | ------------- |
| Reliance Industries | RELIANCE.NS   |
| TCS                 | TCS.NS        |
| Infosys             | INFY.NS       |
| HDFC Bank           | HDFCBANK.NS   |
| ICICI Bank          | ICICIBANK.NS  |
| Wipro               | WIPRO.NS      |
| SBI                 | SBIN.NS       |
| Bharti Airtel       | BHARTIARTL.NS |
| Kotak Bank          | KOTAKBANK.NS  |
| Bajaj Finance       | BAJFINANCE.NS |

---

## TradingView Integration

Webhook URL:

```text
http://YOUR_SERVER_IP:8000/webhook
```

Message Body:

```json
{
  "ticker": "{{ticker}}",
  "event_type": "{{strategy.order.action}}",
  "price": {{close}},
  "timestamp": "{{time}}"
}
```

TradingView tickers are automatically converted to NSE format by appending `.NS`.

---

## Scheduler

Automated scans run:

* Every 30 minutes during NSE trading hours
* Pre-market scan at 09:00 IST
* Weekdays only

Configuration can be adjusted through environment variables.

---

## Data Sources

| Data Type     | Source                          |
| ------------- | ------------------------------- |
| Price / OHLCV | yfinance                        |
| Fundamentals  | yfinance                        |
| News          | NewsAPI                         |
| Sentiment     | News + custom sentiment scoring |
| FII/DII Flows | Mock implementation             |
| AI Reasoning  | OpenAI API (optional)           |

---

## Project Structure

```text
stock_multi_agent/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── config.py
├── main.py
├── celery_worker.py
├── scheduler.py
├── agents/
│   ├── base.py
│   ├── orchestrator.py
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
│   └── task_store.py
└── outputs/
```

---

## Disclaimer

This project is intended for educational, research, and software development purposes. The generated signals should not be considered financial advice. Market conditions can change rapidly, and users should conduct their own research before making investment decisions.
