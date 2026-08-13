# QSIP Agent — Quant Signal Intelligence & Execution Platform

> Private repo: `https://github.com/justinm5/qsip_agent`

A real-time, event-driven quantitative research platform that ingests SEC filings, market data, financial news, earnings transcripts, and options flow; validates data quality; normalizes events into a single stream; and generates research-backed stock recommendations for non-technical investors. Recommendations combine Wall Street analyst ratings, price momentum, news sentiment, insider activity, earnings guidance, options flow, machine learning, and optional cross-checks from external quant research APIs.

Built to help everyday investors make safer, more informed commitments to stocks and indexes with zero AI API spend.

## Architecture

```
SEC EDGAR   Market Data   News/RSS   Earnings   Options
     |            |             |          |         |
     v            v             v          v         v
  SEC Svc    Market Svc   News Svc   Earnings Svc Options Svc
     |            |             |          |         |
     +------------+-------------+----------+---------+
                           |
                    Redpanda (Kafka)
                           |
              Data Validation Svc
        (dedupe, outliers, timestamps, archives)
                           |
                    validated-events
                           |
                   Feature Svc  ----> Feature Store
                           |
                   Signal Svc (SHAP explainability)
                           |
            +--------------+-----------+-------------+
            |              |           |             |
      Backtest Svc  Portfolio Svc  Paper Trading Svc
            |              |           |             |
      TimescaleDB <---- MinIO Replay Engine
            |
     API Gateway (JWT, RBAC, rate limit)
            |
     React Dashboard (simple stock search, research-backed recommendations, top picks)
```

## Tech Stack

**Backend / Distributed Systems**
- Go 1.23 (SEC ingestion, API gateway, gRPC/REST/SSE)
- Redpanda (Kafka-compatible streaming)
- Redis Stack (caching, pub/sub, rate limiting, time-series)
- TimescaleDB 2.x (PostgreSQL time-series, pgvector)
- MinIO (event replay archive)
- gRPC + REST + SSE

**Quantitative / ML Layer**
- Python 3.12
- Polars, Pandas, NumPy, PyArrow
- Scikit-learn, XGBoost, LightGBM, CatBoost
- SHAP (signal explainability)
- FinBERT / Sentence Transformers (local NLP)
- Ollama (local Llama 3 / Mistral for summarization)

**Broker / Execution**
- Alpaca Paper Trading API (optional)
- Simulated paper broker if no API keys provided

**Frontend**
- React 18 + TypeScript
- Vite
- TanStack Query
- Tailwind CSS
- Recharts

**Observability / DevOps**
- Prometheus + Grafana
- Jaeger (OpenTelemetry tracing)
- Docker Compose, Kubernetes manifests, Terraform
- GitHub Actions CI (lint, test, docker build, Trivy security scan)
- Locust load tests

## Signals

- **Insider Conviction** — large insider buys after price weakness
- **Executive Cluster Buying** — multiple insiders buying simultaneously
- **Volume Anomaly** — volume spikes outside normal regime
- **News Surprise** — sentiment divergence vs price move
- **Price Divergence** — high insider buying while price declines
- **Earnings Guidance** — raised/lowered guidance + management tone
- **Options Activity** — unusual call/put volume and call/put ratios
- **ML Alpha** — XGBoost/LightGBM predicted 20-day excess return

Every signal includes a SHAP explanation and can flow directly to paper trading.

## Research Results

Sample out-of-sample performance is stored in `research/signal_performance.json` and `research/results.md`.

| Signal | Signals | Avg 20D Return | Win Rate | Sharpe | Max DD |
|--------|---------|----------------|----------|--------|--------|
| insider_conviction | 4,218 | 3.8% | 61.2% | 1.42 | -19% |
| volume_anomaly | 8,124 | 2.1% | 55.3% | 0.91 | -24% |
| price_divergence | 2,156 | 4.6% | 63.4% | 1.58 | -22% |

ML Alpha top decile vs bottom decile spread (2024-2025): **10.6%**

Regenerate with real data:
```bash
python scripts/generate_research_results.py --start 2018-01-01 --end 2025-08-01
```

## Run Locally

```bash
cp .env.example .env
# edit .env with API keys (optional)

docker compose up -d

# Pull a local LLM for summarization (optional)
ollama pull llama3
```

Access points:
- Dashboard: http://localhost:3001
- API Gateway: http://localhost:8083
- Grafana: http://localhost:3000
- Redpanda Console: http://localhost:8080

## Paper Trading

Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.env` to use Alpaca paper. Without keys, the paper trading service simulates fills locally.

Dashboard shows:
- Live portfolio equity, cash, buying power
- Open positions and unrealized/realized PnL
- Recent trades

## Research

Jupyter notebooks live in `notebooks/`:
- `factor_research.ipynb`
- `alpha_decay.ipynb`
- `insider_analysis.ipynb`
- `feature_importance.ipynb`

## Testing

```bash
pytest tests -q
locust -f tests/locustfile.py --host http://localhost:8083
```

## Security

- JWT-based API authentication
- RBAC: admin / researcher / viewer
- Redis token-bucket rate limiting

## License

MIT
