import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import polars as pl
from prometheus_client import Counter, Histogram, start_http_server

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.feature_store import FeatureStore
from qsip.features import build_feature_vector, compute_filing_features, compute_news_features, compute_price_features
from qsip.kafka_client import KafkaConsumer, KafkaProducer
from qsip.market import MarketDataClient
from qsip.redis_client import RedisClient
from qsip.signals import attach_targets
from qsip.validation import DataValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FEATURES_PROCESSED = Counter("feature_vectors_processed_total", "Feature vectors computed", ["ticker"])
FEATURE_LATENCY = Histogram("feature_compute_seconds", "Time to compute a feature vector")


class FeatureService:
    def __init__(self):
        self.cfg = Config.from_env()
        self.db = TimescaleDB(self.cfg.db_dsn)
        self.redis = RedisClient(self.cfg.redis_addr)
        self.producer = KafkaProducer(self.cfg.kafka_brokers)
        self.market = MarketDataClient(
            polygon_key=self.cfg.polygon_api_key,
            alpaca_key=self.cfg.alpaca_api_key,
            alpaca_secret=self.cfg.alpaca_secret_key,
        )
        self.store = FeatureStore(self.db, version="v1")
        self.validator = DataValidator(self.db, self.redis)
        self.tickers = set()
        self.lock = threading.Lock()

    def run(self):
        start_http_server(int(os.getenv("METRICS_PORT", "9091")))
        threading.Thread(target=self._consume, daemon=True).start()
        while True:
            self._recompute_all()
            time.sleep(60)

    def _consume(self):
        consumer = KafkaConsumer(
            self.cfg.kafka_brokers,
            "feature-service",
            ["validated-events", "market-events"],
        )
        try:
            consumer.consume(self._on_message)
        finally:
            consumer.stop()

    def _on_message(self, msg: dict):
        try:
            etype = msg.get("event_type", "")
            ticker = msg.get("ticker", "")
            if ticker:
                with self.lock:
                    self.tickers.add(ticker)
            if etype in ("ohlcv", "price") and ticker:
                self._handle_market_event(ticker, msg.get("payload", {}))
            if etype in ("4", "3", "5", "8-k", "13d", "13g"):
                self.db.insert_event("sec", etype, ticker, msg.get("payload", {}), msg.get("metadata"))
            if etype == "news_article":
                self.db.insert_event("news", etype, ticker, msg.get("payload", {}), msg.get("metadata"))
        except Exception as e:
            logger.exception("message handler error: %s", e)

    def _handle_market_event(self, ticker: str, payload: dict):
        data = payload.get("data", [])
        if not data:
            return
        try:
            df = pl.DataFrame(data)
            df, issues = self.validator.validate_price_frame(df)
            for issue in issues:
                issue["ticker"] = ticker
                self.db.insert_data_quality_issue(issue)
            for row in df.to_dicts():
                row["source"] = payload.get("source", "unknown")
                self.db.insert_market_data(ticker, row)
        except Exception as e:
            logger.error("market event parse failed: %s", e)

    def _recompute_all(self):
        with self.lock:
            tickers = list(self.tickers)
        for ticker in tickers:
            try:
                self._compute_for_ticker(ticker)
            except Exception as e:
                logger.error("feature compute failed for %s: %s", ticker, e)

    def _compute_for_ticker(self, ticker: str):
        with FEATURE_LATENCY.time():
            rows = self.market.fetch(ticker)
            if not rows:
                logger.warning("no market data for %s", ticker)
                return
            for row in rows:
                self.db.insert_market_data(ticker, row)

            df = pl.DataFrame(rows)
            df, issues = self.validator.validate_price_frame(df)
            for issue in issues:
                issue["ticker"] = ticker
                self.db.insert_data_quality_issue(issue)

            price_features = compute_price_features(df)
            if not price_features:
                return

            cutoff = datetime.utcnow() - timedelta(days=30)
            with self.db.cursor() as cur:
                cur.execute("SELECT * FROM sec_filings WHERE ticker = %s AND filed_at > %s", (ticker, cutoff))
                filings = cur.fetchall()
                cur.execute("SELECT * FROM news_articles WHERE ticker = %s AND published_at > %s", (ticker, datetime.utcnow() - timedelta(days=1)))
                articles = cur.fetchall()
                cur.execute("SELECT * FROM earnings_transcripts WHERE ticker = %s ORDER BY call_date DESC LIMIT 1", (ticker,))
                earnings = cur.fetchone()
                cur.execute("SELECT * FROM options_flow WHERE ticker = %s ORDER BY timestamp DESC LIMIT 10", (ticker,))
                options = cur.fetchall()

            filing_features = compute_filing_features(filings)
            news_features = compute_news_features(articles)
            earn_features = self._earnings_features(earnings)
            opt_features = self._options_features(options)
            vector = build_feature_vector(ticker, price_features, filing_features, news_features)
            vector.update(earn_features)
            vector.update(opt_features)

            # Compute training target from forward returns
            target_20 = attach_targets(df, datetime.utcnow(), 20)

            # Feature store: save for training/inference parity
            self.store.save(ticker, vector, is_training=False)
            with self.db.cursor() as cur:
                cur.execute(
                    "INSERT INTO feature_vectors (timestamp, ticker, feature_version, features, target_return_20d) VALUES (%s, %s, %s, %s, %s)",
                    (datetime.utcnow(), ticker, "v1", json.dumps(vector), target_20),
                )

            self.redis.cache_feature(ticker, vector)
            self.producer.send("feature-events", ticker, vector)
            FEATURES_PROCESSED.labels(ticker=ticker).inc()
            logger.info("computed features for %s score=%.3f", ticker, vector.get("volume_ratio", 0))

    def _earnings_features(self, earnings: dict[str, Any] | None) -> dict[str, float]:
        if not earnings:
            return {"earnings_sentiment": 0.0, "guidance_change": 0.0, "risk_score": 0.0}
        guidance_map = {"raised": 1.0, "lowered": -1.0, "unchanged": 0.0}
        return {
            "earnings_sentiment": float(earnings.get("sentiment_score", 0) or 0),
            "guidance_change": float(guidance_map.get(earnings.get("guidance_change", "unchanged"), 0.0)),
            "risk_score": float(earnings.get("risk_discussion_score", 0) or 0),
        }

    def _options_features(self, options: list[dict[str, Any]]) -> dict[str, float]:
        if not options:
            return {"options_activity_score": 0.0, "call_put_ratio": 1.0}
        calls = [o for o in options if o.get("option_type") == "call"]
        puts = [o for o in options if o.get("option_type") == "put"]
        call_vol = sum(o.get("volume", 0) for o in calls)
        put_vol = sum(o.get("volume", 0) for o in puts)
        score = max(o.get("activity_score", 0) for o in options)
        return {
            "options_activity_score": float(score),
            "call_put_ratio": float(call_vol / put_vol) if put_vol > 0 else float(call_vol),
        }


if __name__ == "__main__":
    FeatureService().run()
