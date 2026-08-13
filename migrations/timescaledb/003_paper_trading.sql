-- Paper trading tables
CREATE TABLE IF NOT EXISTS paper_orders (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT UNIQUE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,              -- buy, sell
    qty DOUBLE PRECISION,
    order_type TEXT,                 -- market, limit
    limit_price DOUBLE PRECISION,
    status TEXT,                     -- pending, filled, cancelled
    filled_qty DOUBLE PRECISION DEFAULT 0,
    filled_avg_price DOUBLE PRECISION,
    broker TEXT,
    strategy TEXT,
    signal_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_paper_orders_ticker ON paper_orders (ticker, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_orders_status ON paper_orders (status, created_at DESC);

CREATE TABLE IF NOT EXISTS paper_positions (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    avg_entry_price DOUBLE PRECISION,
    market_price DOUBLE PRECISION,
    market_value DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    realized_pnl DOUBLE PRECISION,
    side TEXT,                       -- long, short
    strategy TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_positions_ticker ON paper_positions (ticker, strategy);

CREATE TABLE IF NOT EXISTS paper_trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id TEXT UNIQUE,
    order_id TEXT,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    qty DOUBLE PRECISION,
    price DOUBLE PRECISION,
    total_value DOUBLE PRECISION,
    strategy TEXT,
    signal_id TEXT,
    executed_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_paper_trades_ticker ON paper_trades (ticker, executed_at DESC);

CREATE TABLE IF NOT EXISTS paper_account (
    id BIGSERIAL PRIMARY KEY,
    strategy TEXT UNIQUE,
    cash DOUBLE PRECISION,
    equity DOUBLE PRECISION,
    buying_power DOUBLE PRECISION,
    day_trading_buying_power DOUBLE PRECISION,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
