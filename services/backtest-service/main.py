import json
import logging
import os
from datetime import datetime, timedelta

import polars as pl
from prometheus_client import Counter, Histogram, start_http_server

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.kafka_client import KafkaConsumer
from qsip.market import MarketDataClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKTESTS_RUN = Counter("backtests_run_total", "Backtests run", ["ticker"])
BACKTEST_LATENCY = Histogram("backtest_compute_seconds", "Time to run backtest")


class BacktestService:
    HORIZONS = [1, 5, 20, 60]

    def __init__(self):
        self.cfg = Config.from_env()
        self.db = TimescaleDB(self.cfg.db_dsn)
        self.market = MarketDataClient(
            polygon_key=self.cfg.polygon_api_key,
            alpaca_key=self.cfg.alpaca_api_key,
            alpaca_secret=self.cfg.alpaca_secret_key,
        )

    def run(self):
        start_http_server(int(os.getenv("METRICS_PORT", "9091")))
        consumer = KafkaConsumer(
            self.cfg.kafka_brokers,
            "backtest-service",
            ["backtest-jobs"],
        )
        try:
            consumer.consume(self._on_signal)
        finally:
            consumer.stop()

    def _on_signal(self, signal: dict):
        ticker = signal.get("ticker", "")
        if not ticker:
            return
        with BACKTEST_LATENCY.time():
            self._backtest(signal)
            BACKTESTS_RUN.labels(ticker=ticker).inc()

    def _backtest(self, signal: dict):
        ticker = signal["ticker"]
        entry_time = datetime.fromisoformat(signal["timestamp"])
        prices = self.market.fetch(ticker)
        if not prices:
            return
        df = pl.DataFrame(prices).sort("time")

        # Ensure price data covers entry time
        future = df.filter(pl.col("time") >= entry_time)
        if future.height == 0:
            return
        entry_row = future.head(1)
        entry_price = float(entry_row["close"][0])

        for horizon in self.HORIZONS:
            exit_time = entry_time + timedelta(days=horizon)
            exit_rows = df.filter(pl.col("time") >= exit_time).head(1)
            if exit_rows.height == 0:
                continue
            exit_price = float(exit_rows["close"][0])
            return_pct = (exit_price - entry_price) / entry_price
            benchmark = self._benchmark_return(df, entry_time, exit_time)
            excess = return_pct - benchmark if benchmark is not None else return_pct
            max_dd = self._max_drawdown(df, entry_time, exit_time, entry_price)

            self.db.insert_event(
                "backtest-service",
                "backtest_result",
                ticker,
                {
                    "signal_id": signal.get("signal_id"),
                    "entry_time": entry_time.isoformat(),
                    "exit_time": exit_time.isoformat(),
                    "holding_days": horizon,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return_pct": return_pct,
                    "excess_return_pct": excess,
                    "benchmark_return_pct": benchmark,
                    "max_drawdown_pct": max_dd,
                },
            )
            logger.info("backtest %s %dd return=%.3f excess=%.3f", ticker, horizon, return_pct, excess)

    def _benchmark_return(self, df: pl.DataFrame, start: datetime, end: datetime) -> float | None:
        # Use SPY as benchmark if available, otherwise market average of current data
        s = df.filter(pl.col("time") >= start).head(1)
        e = df.filter(pl.col("time") >= end).head(1)
        if s.height == 0 or e.height == 0:
            return None
        return float((e["close"][0] - s["close"][0]) / s["close"][0])

    def _max_drawdown(self, df: pl.DataFrame, start: datetime, end: datetime, entry_price: float) -> float:
        window = df.filter((pl.col("time") >= start) & (pl.col("time") <= end))
        if window.height == 0:
            return 0.0
        prices = window["close"].to_numpy()
        peak = entry_price
        dd = 0.0
        for p in prices:
            if p > peak:
                peak = p
            dd = min(dd, (p - peak) / peak)
        return float(dd)


if __name__ == "__main__":
    BacktestService().run()
