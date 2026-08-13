from __future__ import annotations

import contextlib
import json
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row


class TimescaleDB:
    def __init__(self, dsn: str):
        self.dsn = dsn

    @contextlib.contextmanager
    def cursor(self, row_factory=dict_row):
        conn = psycopg.connect(self.dsn, autocommit=True, row_factory=row_factory)
        try:
            yield conn.cursor()
        finally:
            conn.close()

    def insert_event(
        self,
        source: str,
        event_type: str,
        ticker: str | None,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (source, event_type, ticker, timestamp, payload, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    source,
                    event_type,
                    ticker,
                    timestamp or datetime.utcnow(),
                    json.dumps(payload),
                    json.dumps(metadata) if metadata else None,
                ),
            )

    def insert_market_data(self, ticker: str, data: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO market_data (time, ticker, open, high, low, close, volume, vwap, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, ticker) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    vwap = EXCLUDED.vwap,
                    source = EXCLUDED.source
                """,
                (
                    data["time"],
                    ticker,
                    data.get("open"),
                    data.get("high"),
                    data.get("low"),
                    data.get("close"),
                    data.get("volume"),
                    data.get("vwap"),
                    data.get("source", "unknown"),
                ),
            )

    def insert_signal(self, signal: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO signals (timestamp, ticker, signal_type, direction, score, features, ml_score, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    signal.get("timestamp", datetime.utcnow()),
                    signal["ticker"],
                    signal["signal_type"],
                    signal.get("direction"),
                    signal.get("score"),
                    json.dumps(signal.get("features", {})),
                    signal.get("ml_score"),
                    json.dumps(signal.get("metadata", {})),
                ),
            )

    def insert_signal_explanation(self, explanation: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO signal_explanations (signal_id, ticker, timestamp, shap_values, top_features, summary)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (signal_id) DO UPDATE SET
                    shap_values = EXCLUDED.shap_values,
                    top_features = EXCLUDED.top_features,
                    summary = EXCLUDED.summary
                """,
                (
                    explanation["signal_id"],
                    explanation["ticker"],
                    explanation.get("timestamp", datetime.utcnow()),
                    json.dumps(explanation.get("shap_values", {})),
                    json.dumps(explanation.get("top_features", [])),
                    explanation.get("summary"),
                ),
            )

    def get_signal_explanation(self, signal_id: str) -> dict[str, Any] | None:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM signal_explanations WHERE signal_id = %s", (signal_id,))
            return cur.fetchone()

    def insert_data_quality_issue(self, issue: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data_quality_issues (source, event_type, ticker, issue_type, severity, event_id, payload, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    issue["source"],
                    issue["event_type"],
                    issue.get("ticker"),
                    issue["issue_type"],
                    issue["severity"],
                    issue.get("event_id"),
                    json.dumps(issue.get("payload", {})),
                    issue.get("reason"),
                ),
            )

    def store_feature_vector(self, ticker: str, feature_version: str, features: dict[str, Any], is_training: bool = False) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feature_store (timestamp, ticker, feature_version, features, is_training)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (datetime.utcnow(), ticker, feature_version, json.dumps(features), is_training),
            )

    def get_latest_feature_vector(self, ticker: str, feature_version: str = "v1") -> dict[str, Any] | None:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM feature_store
                WHERE ticker = %s AND feature_version = %s
                ORDER BY timestamp DESC LIMIT 1
                """,
                (ticker, feature_version),
            )
            return cur.fetchone()

    def get_training_features(self, feature_version: str = "v1", limit: int = 100_000) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM feature_store
                WHERE feature_version = %s AND is_training = TRUE
                ORDER BY timestamp ASC
                LIMIT %s
                """,
                (feature_version, limit),
            )
            return cur.fetchall()

    def insert_earnings_transcript(self, transcript: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO earnings_transcripts
                (ticker, fiscal_quarter, fiscal_year, call_date, transcript_text, sentiment_score,
                 guidance_change, management_optimism_score, risk_discussion_score, source, url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, fiscal_quarter, fiscal_year, call_date) DO UPDATE SET
                    transcript_text = EXCLUDED.transcript_text,
                    sentiment_score = EXCLUDED.sentiment_score
                """,
                (
                    transcript["ticker"],
                    transcript.get("fiscal_quarter"),
                    transcript.get("fiscal_year"),
                    transcript.get("call_date"),
                    transcript.get("transcript_text"),
                    transcript.get("sentiment_score"),
                    transcript.get("guidance_change"),
                    transcript.get("management_optimism_score"),
                    transcript.get("risk_discussion_score"),
                    transcript.get("source"),
                    transcript.get("url"),
                ),
            )

    def insert_options_flow(self, row: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO options_flow
                (timestamp, ticker, option_type, strike, expiration, volume, open_interest, premium, source, activity_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row.get("timestamp", datetime.utcnow()),
                    row["ticker"],
                    row.get("option_type"),
                    row.get("strike"),
                    row.get("expiration"),
                    row.get("volume"),
                    row.get("open_interest"),
                    row.get("premium"),
                    row.get("source"),
                    row.get("activity_score"),
                ),
            )

    def insert_portfolio_snapshot(self, snapshot: dict[str, Any]) -> int | None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO portfolio_snapshots
                (timestamp, strategy, nav, cash, total_value, return_1d, return_1w, return_1m,
                 sharpe, sortino, max_drawdown, alpha, beta, metrics)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    snapshot.get("timestamp", datetime.utcnow()),
                    snapshot["strategy"],
                    snapshot.get("nav"),
                    snapshot.get("cash"),
                    snapshot.get("total_value"),
                    snapshot.get("return_1d"),
                    snapshot.get("return_1w"),
                    snapshot.get("return_1m"),
                    snapshot.get("sharpe"),
                    snapshot.get("sortino"),
                    snapshot.get("max_drawdown"),
                    snapshot.get("alpha"),
                    snapshot.get("beta"),
                    json.dumps(snapshot.get("metrics", {})),
                ),
            )
            result = cur.fetchone()
            return result["id"] if result else None

    def insert_portfolio_holdings(self, snapshot_id: int, strategy: str, holdings: list[dict[str, Any]]) -> None:
        with self.cursor() as cur:
            for h in holdings:
                cur.execute(
                    """
                    INSERT INTO portfolio_holdings
                    (snapshot_id, timestamp, strategy, ticker, shares, weight, entry_price, market_price, pnl)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        snapshot_id,
                        h.get("timestamp", datetime.utcnow()),
                        strategy,
                        h["ticker"],
                        h.get("shares"),
                        h.get("weight"),
                        h.get("entry_price"),
                        h.get("market_price"),
                        h.get("pnl"),
                    ),
                )

    def get_market_data(self, ticker: str, days: int = 252) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT time, open, high, low, close, volume
                FROM market_data
                WHERE ticker = %s AND time > NOW() - make_interval(days => %s)
                ORDER BY time ASC
                """,
                (ticker, days),
            )
            return cur.fetchall()

    def get_latest_events(self, source: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            if source:
                cur.execute(
                    "SELECT * FROM events WHERE source = %s ORDER BY timestamp DESC LIMIT %s",
                    (source, limit),
                )
            else:
                cur.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT %s", (limit,))
            return cur.fetchall()

    def get_signals(self, ticker: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            if ticker:
                cur.execute(
                    "SELECT * FROM signals WHERE ticker = %s ORDER BY timestamp DESC LIMIT %s",
                    (ticker, limit),
                )
            else:
                cur.execute("SELECT * FROM signals ORDER BY timestamp DESC LIMIT %s", (limit,))
            return cur.fetchall()

    def get_backtests(self, ticker: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            if ticker:
                cur.execute(
                    "SELECT * FROM backtest_results WHERE ticker = %s ORDER BY entry_time DESC LIMIT %s",
                    (ticker, limit),
                )
            else:
                cur.execute("SELECT * FROM backtest_results ORDER BY entry_time DESC LIMIT %s", (limit,))
            return cur.fetchall()

    def get_portfolio_snapshots(self, strategy: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(
                "SELECT * FROM portfolio_snapshots WHERE strategy = %s ORDER BY timestamp DESC LIMIT %s",
                (strategy, limit),
            )
            return cur.fetchall()

    def insert_paper_order(self, order: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_orders (order_id, ticker, side, qty, order_type, limit_price, status, filled_qty, filled_avg_price, broker, strategy, signal_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    filled_qty = EXCLUDED.filled_qty,
                    filled_avg_price = EXCLUDED.filled_avg_price,
                    updated_at = NOW()
                """,
                (
                    order["order_id"],
                    order["ticker"],
                    order["side"],
                    order.get("qty"),
                    order.get("order_type", "market"),
                    order.get("limit_price"),
                    order.get("status", "pending"),
                    order.get("filled_qty", 0),
                    order.get("filled_avg_price"),
                    order.get("broker", "alpaca"),
                    order.get("strategy", "default"),
                    order.get("signal_id"),
                ),
            )

    def upsert_paper_position(self, pos: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_positions (ticker, qty, avg_entry_price, market_price, market_value, unrealized_pnl, realized_pnl, side, strategy, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (ticker, strategy) DO UPDATE SET
                    qty = EXCLUDED.qty,
                    avg_entry_price = EXCLUDED.avg_entry_price,
                    market_price = EXCLUDED.market_price,
                    market_value = EXCLUDED.market_value,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    realized_pnl = EXCLUDED.realized_pnl,
                    updated_at = NOW()
                """,
                (
                    pos["ticker"],
                    pos["qty"],
                    pos.get("avg_entry_price"),
                    pos.get("market_price"),
                    pos.get("market_value"),
                    pos.get("unrealized_pnl"),
                    pos.get("realized_pnl", 0),
                    pos.get("side", "long"),
                    pos.get("strategy", "default"),
                ),
            )

    def insert_paper_trade(self, trade: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_trades (trade_id, order_id, ticker, side, qty, price, total_value, strategy, signal_id, executed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_id) DO NOTHING
                """,
                (
                    trade["trade_id"],
                    trade.get("order_id"),
                    trade["ticker"],
                    trade["side"],
                    trade.get("qty"),
                    trade.get("price"),
                    trade.get("total_value"),
                    trade.get("strategy", "default"),
                    trade.get("signal_id"),
                    trade.get("executed_at", datetime.utcnow()),
                ),
            )

    def upsert_paper_account(self, account: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_account (strategy, cash, equity, buying_power, day_trading_buying_power, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (strategy) DO UPDATE SET
                    cash = EXCLUDED.cash,
                    equity = EXCLUDED.equity,
                    buying_power = EXCLUDED.buying_power,
                    day_trading_buying_power = EXCLUDED.day_trading_buying_power,
                    updated_at = NOW()
                """,
                (
                    account.get("strategy", "default"),
                    account.get("cash"),
                    account.get("equity"),
                    account.get("buying_power"),
                    account.get("day_trading_buying_power"),
                ),
            )

    def get_paper_positions(self, strategy: str = "default") -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM paper_positions WHERE strategy = %s", (strategy,))
            return cur.fetchall()

    def get_paper_orders(self, status: str | None = None, strategy: str = "default", limit: int = 100) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT * FROM paper_orders WHERE strategy = %s AND status = %s ORDER BY created_at DESC LIMIT %s",
                    (strategy, status, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM paper_orders WHERE strategy = %s ORDER BY created_at DESC LIMIT %s",
                    (strategy, limit),
                )
            return cur.fetchall()

    def get_paper_trades(self, strategy: str = "default", limit: int = 100) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(
                "SELECT * FROM paper_trades WHERE strategy = %s ORDER BY executed_at DESC LIMIT %s",
                (strategy, limit),
            )
            return cur.fetchall()

    def get_paper_account(self, strategy: str = "default") -> dict[str, Any] | None:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM paper_account WHERE strategy = %s", (strategy,))
            return cur.fetchone()

    def insert_archive_metadata(self, meta: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event_archives (archive_id, source, event_type, date_from, date_to, object_path, record_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (archive_id) DO UPDATE SET
                    object_path = EXCLUDED.object_path,
                    record_count = EXCLUDED.record_count
                """,
                (
                    meta["archive_id"],
                    meta.get("source"),
                    meta.get("event_type"),
                    meta.get("date_from"),
                    meta.get("date_to"),
                    meta.get("object_path"),
                    meta.get("record_count"),
                ),
            )
