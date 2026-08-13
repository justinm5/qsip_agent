import json
import logging
import os
import threading
import time
from datetime import datetime

from prometheus_client import Counter, Histogram, start_http_server

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.explainability import explain_signal
from qsip.feature_store import FeatureStore
from qsip.kafka_client import KafkaConsumer, KafkaProducer
from qsip.redis_client import RedisClient
from qsip.signals import SignalEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SIGNALS_GENERATED = Counter("signals_generated_total", "Signals generated", ["ticker", "type"])
SIGNAL_LATENCY = Histogram("signal_compute_seconds", "Time to compute signals")

FEATURE_KEYS = [
    "return_1d", "return_5d", "return_20d", "return_60d",
    "volatility_20d", "volume_ratio", "rsi_14", "macd", "macd_signal",
    "bb_position", "zscore_20d",
    "insider_buys_30d", "insider_sells_30d", "insider_buy_ratio",
    "insider_buy_dollars_30d", "insider_sell_dollars_30d", "insider_net_dollars_30d",
    "news_sentiment_mean", "news_sentiment_std", "news_count_24h",
    "earnings_sentiment", "guidance_change", "risk_score",
    "options_activity_score", "call_put_ratio",
]


class SignalService:
    def __init__(self):
        self.cfg = Config.from_env()
        self.db = TimescaleDB(self.cfg.db_dsn)
        self.redis = RedisClient(self.cfg.redis_addr)
        self.producer = KafkaProducer(self.cfg.kafka_brokers)
        self.engine = SignalEngine(model_path=self.cfg.model_path, feature_keys=FEATURE_KEYS)
        self.store = FeatureStore(self.db, version="v1")

    def run(self):
        start_http_server(int(os.getenv("METRICS_PORT", "9091")))
        threading.Thread(target=self._consume, daemon=True).start()
        while True:
            time.sleep(10)

    def _consume(self):
        consumer = KafkaConsumer(
            self.cfg.kafka_brokers,
            "signal-service",
            ["feature-events"],
        )
        try:
            consumer.consume(self._on_feature)
        finally:
            consumer.stop()

    def _on_feature(self, msg: dict):
        ticker = msg.get("ticker", "")
        if not ticker:
            return
        with SIGNAL_LATENCY.time():
            signals = self.engine.generate(ticker, msg)
            for signal in signals:
                signal["timestamp"] = datetime.utcnow().isoformat()

                # SHAP explainability
                explanation = explain_signal(self.engine.model, signal.get("features", {}), FEATURE_KEYS)
                signal["metadata"] = signal.get("metadata", {})
                signal["metadata"]["explanation"] = explanation

                self.db.insert_signal(signal)
                self.db.insert_signal_explanation({
                    "signal_id": signal["signal_id"],
                    "ticker": ticker,
                    "timestamp": datetime.utcnow(),
                    "shap_values": explanation.get("shap_values", {}),
                    "top_features": explanation.get("top_features", []),
                    "summary": explanation.get("summary", ""),
                })
                self.redis.cache_signal(signal)
                self.producer.send("signal-events", ticker, signal)
                self.producer.send("backtest-jobs", ticker, signal)
                self.producer.send("portfolio-jobs", ticker, signal)
                SIGNALS_GENERATED.labels(ticker=ticker, type=signal["signal_type"]).inc()
                logger.info("signal generated: %s %s %.3f", ticker, signal["signal_type"], signal["score"])


if __name__ == "__main__":
    SignalService().run()
