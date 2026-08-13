# QSIP Agent Notes

## Project Layout
- `services/`: Go and Python microservices
- `python/qsip/`: Shared Python library used by all Python services
- `frontend/`: React + TypeScript dashboard
- `migrations/timescaledb/`: Database initialization scripts
- `infrastructure/`: Docker, K8s, Terraform configs
- `scripts/`: One-off scripts including model training and research report generation
- `tests/`: Python unit/integration/e2e tests
- `notebooks/`: Research notebooks for factor/alpha/SHAP analysis
- `research/`: Backtest performance results and reports

## Architecture Flow
Data sources (SEC EDGAR, Market, News/RSS, Earnings, Options) publish to `raw-events`.
`data-validation-service` validates/deduplicates them and writes `validated-events` (and archives to MinIO).
`feature-service` consumes `validated-events`, computes features, stores them in the Feature Store, and emits `feature-events`.
`signal-service` generates rule-based + ML signals with SHAP explanations, writes `signal-events`.
`backtest-service`, `portfolio-service`, and `paper-trading-service` consume `signal-events` for performance attribution and execution.
`api-gateway` exposes REST/SSE endpoints with JWT + rate limiting.

## Build / Run
- One-command: `.\\start.ps1` (Windows) or `./start.sh` (Linux/macOS)
- Infrastructure only: `docker compose up -d redpanda timescaledb redis minio`
- All services: `docker compose up -d`
- Frontend dev: `cd frontend && npm install && npm run dev`
- ML training: `python scripts/train_model.py --model xgboost --output /models/xgb_model.pkl`
- Research results: `python scripts/generate_research_results.py`
- Tests: `pytest tests -q`
- Load tests: `locust -f tests/locustfile.py`

## Important Notes
- Go services do not include `go.sum` files; run `go mod tidy` inside each Go service after cloning.
- Python services share code from `python/qsip` and are built from repo root context.
- TimescaleDB migrations run automatically from `migrations/timescaledb/`.
- Add API keys to `.env` before starting optional market/news/earnings/options/paper services.
- SEC EDGAR requires a proper `SEC_USER_AGENT` to avoid rate limiting.
- JWT secret should be changed in production via `JWT_SECRET`.
- Paper trading defaults to simulated fills unless Alpaca keys are provided.
- Recommendation API (`GET /api/v1/stocks/{ticker}/recommendation`, `GET /api/v1/stocks/trending`) combines Finnhub analyst ratings, price momentum, news sentiment, insider activity, earnings guidance, options flow, and the latest ML signal. Set `FINNHUB_KEY` for external data.
- Optional cross-reference: set `RESEARCH_API_URL` and `RESEARCH_API_KEY` to merge signals from an external quant research API. The endpoint should be `GET {RESEARCH_API_URL}/{ticker}` and return JSON with `score` (-1..1), `recommendation`, `summary`, and optional `factors`.
