-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

-- Events stream: normalized canonical event store
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL,
    event_id UUID NOT NULL DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,           -- sec, market, news, feature, signal, backtest
    event_type TEXT NOT NULL,       -- form4, 13d, 8k, price, volume, news_article, signal, etc.
    ticker TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    metadata JSONB,
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('events', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');

CREATE INDEX IF NOT EXISTS idx_events_source ON events (source, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_ticker ON events (ticker, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_payload_gin ON events USING GIN (payload);

-- Market data: OHLCV ticks
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    vwap DOUBLE PRECISION,
    source TEXT
);
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_data_time_ticker ON market_data (time, ticker);

-- SEC filings
CREATE TABLE IF NOT EXISTS sec_filings (
    id BIGSERIAL PRIMARY KEY,
    accession_number TEXT UNIQUE,
    form_type TEXT NOT NULL,        -- 4, 3, 5, 13D, 13G, 8-K
    ticker TEXT,
    cik TEXT,
    filed_at TIMESTAMPTZ,
    reported_at TIMESTAMPTZ,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sec_filings_ticker ON sec_filings (ticker, filed_at DESC);
CREATE INDEX IF NOT EXISTS idx_sec_filings_form ON sec_filings (form_type, filed_at DESC);

-- Signals
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL,
    signal_id UUID NOT NULL DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    direction TEXT,                 -- long, short
    score DOUBLE PRECISION,         -- 0-1 or z-score
    features JSONB,
    ml_score DOUBLE PRECISION,
    metadata JSONB,
    PRIMARY KEY (id, timestamp)
);
SELECT create_hypertable('signals', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals (ticker, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals (signal_type, timestamp DESC);

-- Backtest results
CREATE TABLE IF NOT EXISTS backtest_results (
    id BIGSERIAL PRIMARY KEY,
    signal_id UUID,
    ticker TEXT,
    entry_time TIMESTAMPTZ,
    exit_time TIMESTAMPTZ,
    holding_days INT,
    entry_price DOUBLE PRECISION,
    exit_price DOUBLE PRECISION,
    return_pct DOUBLE PRECISION,
    excess_return_pct DOUBLE PRECISION,
    benchmark_return_pct DOUBLE PRECISION,
    max_drawdown_pct DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_backtest_results_ticker ON backtest_results (ticker, entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_results_signal ON backtest_results (signal_id);

-- Feature vectors for ML training
CREATE TABLE IF NOT EXISTS feature_vectors (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker TEXT NOT NULL,
    feature_version TEXT,
    features JSONB NOT NULL,
    target_return_20d DOUBLE PRECISION,
    target_return_60d DOUBLE PRECISION,
    PRIMARY KEY (id, timestamp)
);
SELECT create_hypertable('feature_vectors', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_feature_vectors_ticker ON feature_vectors (ticker, timestamp DESC);

-- News articles
CREATE TABLE IF NOT EXISTS news_articles (
    id BIGSERIAL PRIMARY KEY,
    url TEXT UNIQUE,
    title TEXT,
    source TEXT,
    published_at TIMESTAMPTZ,
    ticker TEXT,
    content TEXT,
    sentiment_score DOUBLE PRECISION,
    sentiment_label TEXT,
    embedding VECTOR(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_news_articles_ticker ON news_articles (ticker, published_at DESC);


