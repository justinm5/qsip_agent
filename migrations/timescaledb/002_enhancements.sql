-- Data quality issues
CREATE TABLE IF NOT EXISTS data_quality_issues (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    ticker TEXT,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL,         -- critical, warning, info
    event_id TEXT,
    payload JSONB,
    reason TEXT,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dq_ticker ON data_quality_issues (ticker, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_dq_issue ON data_quality_issues (issue_type, severity, detected_at DESC);

-- Signal explanations (SHAP / attribution)
CREATE TABLE IF NOT EXISTS signal_explanations (
    id BIGSERIAL PRIMARY KEY,
    signal_id UUID NOT NULL,
    ticker TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shap_values JSONB NOT NULL,
    top_features JSONB NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_explanations_signal ON signal_explanations (signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_explanations_ticker ON signal_explanations (ticker, timestamp DESC);

-- Feature store registry
CREATE TABLE IF NOT EXISTS feature_store (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker TEXT NOT NULL,
    feature_version TEXT NOT NULL DEFAULT 'v1',
    features JSONB NOT NULL,
    is_training BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (id, timestamp)
);
SELECT create_hypertable('feature_store', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_feature_store_ticker_version ON feature_store (ticker, feature_version, timestamp DESC);

-- Portfolio snapshots
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    strategy TEXT NOT NULL,
    nav DOUBLE PRECISION,
    cash DOUBLE PRECISION,
    total_value DOUBLE PRECISION,
    return_1d DOUBLE PRECISION,
    return_1w DOUBLE PRECISION,
    return_1m DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    sortino DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    alpha DOUBLE PRECISION,
    beta DOUBLE PRECISION,
    metrics JSONB,
    PRIMARY KEY (id, timestamp)
);
SELECT create_hypertable('portfolio_snapshots', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');
CREATE INDEX IF NOT EXISTS idx_portfolio_strategy ON portfolio_snapshots (strategy, timestamp DESC);

-- Portfolio holdings
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    strategy TEXT NOT NULL,
    ticker TEXT NOT NULL,
    shares DOUBLE PRECISION,
    weight DOUBLE PRECISION,
    entry_price DOUBLE PRECISION,
    market_price DOUBLE PRECISION,
    pnl DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_portfolio_holdings ON portfolio_holdings (strategy, timestamp DESC);

-- Earnings transcripts
CREATE TABLE IF NOT EXISTS earnings_transcripts (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    fiscal_quarter TEXT,
    fiscal_year TEXT,
    call_date TIMESTAMPTZ,
    transcript_text TEXT,
    sentiment_score DOUBLE PRECISION,
    guidance_change TEXT,
    management_optimism_score DOUBLE PRECISION,
    risk_discussion_score DOUBLE PRECISION,
    source TEXT,
    url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_earnings_ticker ON earnings_transcripts (ticker, call_date DESC);

-- Options flow
CREATE TABLE IF NOT EXISTS options_flow (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker TEXT NOT NULL,
    option_type TEXT,               -- call, put
    strike DOUBLE PRECISION,
    expiration TIMESTAMPTZ,
    volume BIGINT,
    open_interest BIGINT,
    premium DOUBLE PRECISION,
    source TEXT,
    activity_score DOUBLE PRECISION,
    PRIMARY KEY (id, timestamp)
);
SELECT create_hypertable('options_flow', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');
CREATE INDEX IF NOT EXISTS idx_options_flow_ticker ON options_flow (ticker, timestamp DESC);

-- Event archive metadata (MinIO)
CREATE TABLE IF NOT EXISTS event_archives (
    id BIGSERIAL PRIMARY KEY,
    archive_id TEXT UNIQUE,
    source TEXT,
    event_type TEXT,
    date_from TIMESTAMPTZ,
    date_to TIMESTAMPTZ,
    object_path TEXT,
    record_count BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_event_archives ON event_archives (source, event_type, date_from);
