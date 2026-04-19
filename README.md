# SimpleQuant

> **Internally complex. Externally simple.**
> A full-stack quantitative trading platform where the interface is built for a child, but the engine runs like a quant desk.

---

## Architecture

```
SimpleQuant/
├── backend/
│   ├── config.py              ← All constants (no magic numbers)
│   ├── main.py                ← FastAPI app + all routes
│   ├── data_engine/           ← Live (yFinance) + dummy GBM data
│   ├── feature_engine/        ← Stats, TA, ARIMA, GARCH, Monte Carlo, ML
│   ├── decision_engine/       ← Weighted signal aggregation → BUY/SELL/HOLD
│   ├── risk_engine/           ← Kelly, ATR stops, VaR, drawdown
│   ├── execution_engine/      ← Paper trading simulator
│   └── tests/                 ← Pytest smoke tests
├── frontend/
│   └── src/
│       ├── App.jsx            ← Home + detail screens
│       ├── components/        ← ActionButton, PriceChart, SignalBreakdown…
│       ├── hooks/useAnalysis  ← Data fetching hook
│       └── utils/             ← API client, formatters
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── requirements.txt
```

---

## Setup (under 10 steps)

### Option A — Local (recommended for development)

**Prerequisites:** Python 3.11+, Node.js 20+

```bash
# 1. Clone
git clone https://github.com/rishabhdoshi09/practice-numbers.git
cd practice-numbers

# 2. Python environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Start backend (works fully offline — dummy data is built-in)
uvicorn backend.main:app --reload --port 8000

# 5. Install frontend dependencies
cd frontend && npm install

# 6. Start frontend
npm start
```

Open `http://localhost:3000` — done.

### Option B — Docker

```bash
# 7. Build and start everything
docker-compose up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Running tests

```bash
# From repo root (with venv active)
pytest backend/tests/ -v
```

---

## How it works

Every time you select a stock, the backend runs this pipeline in sequence:

```
Market Data  →  Feature Engine  →  Decision Engine  →  Risk Engine
    ↓                ↓                    ↓                  ↓
OHLCV/News    8 signal modules      BUY/SELL/HOLD      Stop loss
              (ARIMA, GARCH,        + confidence %     Position size
               ML, Monte Carlo,     + risk level       VaR 95/99
               RSI, MACD, GBM,
               Sentiment)
```

### Signal modules (Feature Engine)

| Module | Method | Output |
|---|---|---|
| Trend | SMA/EMA crossover + slope | [-1, +1] |
| Momentum | RSI + MACD histogram | [-1, +1] |
| ARIMA | ARIMA(2,1,2) 5-day forecast | [-1, +1] |
| Volatility | GARCH(1,1) conditional vol | [-1, +1] |
| GBM | Geometric Brownian Motion 5-day | [-1, +1] |
| ML | Logistic Regression + Random Forest ensemble | [-1, +1] |
| Sentiment | Keyword-scored news headlines | [-1, +1] |
| Mean Reversion | Z-score of price vs 20d MA | [-1, +1] |

All signals are weighted (see `config.SIGNAL_WEIGHTS`) and aggregated into one final score. Score > 0.15 → **BUY**, score < -0.15 → **SELL**, otherwise **HOLD**.

### Risk Engine

- **Position sizing:** Half-Kelly criterion (capped at 20% of portfolio)
- **Stop loss:** Entry price − 2×ATR (Average True Range)
- **VaR:** Historical simulation at 95% and 99% confidence
- **Max drawdown:** Alerts and halts trading at configurable threshold (default 15%)

### Execution Engine (Paper Trading)

- Order fills at last price ± 0.05% slippage + 0.03% commission
- Tracks P&L, win rate, Sharpe ratio
- Phase 2 (roadmap): Zerodha Kite Connect live trading

---

## Sample output — BUY decision

```json
{
  "symbol": "RELIANCE.NS",
  "price": 2873.45,
  "decision": {
    "action": "BUY",
    "confidence": 71.4,
    "risk_level": "MEDIUM",
    "final_score": 0.247,
    "signals_agree": 75.0,
    "signal_breakdown": {
      "trend":       { "raw_signal":  0.62, "weight": 0.20, "contribution":  0.124 },
      "momentum":    { "raw_signal":  0.38, "weight": 0.15, "contribution":  0.057 },
      "arima":       { "raw_signal":  0.44, "weight": 0.15, "contribution":  0.066 },
      "volatility":  { "raw_signal": -0.18, "weight": 0.10, "contribution": -0.018 },
      "gbm":         { "raw_signal":  0.31, "weight": 0.05, "contribution":  0.016 },
      "ml":          { "raw_signal":  0.52, "weight": 0.20, "contribution":  0.104 },
      "sentiment":   { "raw_signal":  0.65, "weight": 0.10, "contribution":  0.065 },
      "mean_revert": { "raw_signal": -0.27, "weight": 0.05, "contribution": -0.014 }
    }
  },
  "risk": {
    "stop_loss": { "price": 2784.10, "distance_pct": 3.106 },
    "position_sizing": { "recommended_pct": 6.25, "recommended_inr": 62500 },
    "var": { "var_95_pct": 2.143, "var_99_pct": 3.218 }
  }
}
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/symbols` | Supported tickers |
| GET | `/decision?symbol=X` | Decision only (home screen) |
| GET | `/analyse?symbol=X` | Full analysis pipeline |
| GET | `/chart?symbol=X&days=60` | OHLCV chart data |
| GET | `/risk?symbol=X` | Risk metrics |
| GET | `/orderbook?symbol=X` | Simulated order book |
| POST | `/order` | Paper trade execution |
| GET | `/portfolio` | Portfolio summary + Sharpe |
| GET | `/trades` | Trade log |
| GET | `/monte-carlo?symbol=X` | MC fan chart |
| GET | `/portfolio/optimize?symbols=X,Y,Z` | Markowitz optimisation |

Interactive docs: `http://localhost:8000/docs`

---

## Non-negotiables (all met)

- [x] Home screen has exactly three choices: **BUY**, **SELL**, **WAIT**
- [x] Math is real — every signal computed from OHLCV/news data
- [x] Every risk metric is calculated, not assumed
- [x] Works offline (dummy GBM data, no API keys required)
- [x] UI is effortless; all complexity lives in the backend

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Tailwind CSS + Recharts |
| Backend | Python 3.11 + FastAPI |
| ML / Quant | scikit-learn, statsmodels, arch (GARCH), scipy, pandas, numpy |
| Data | yFinance (live) + custom GBM simulator (offline) |
| Deployment | Docker + docker-compose |
| Broker (Phase 2) | Zerodha Kite Connect |

---

*SimpleQuant — A system where a child presses one button, and behind that button is a quant fund.*
