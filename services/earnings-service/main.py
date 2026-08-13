import logging
import os
import threading
import time
from datetime import datetime

from prometheus_client import Counter, start_http_server

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.earnings import EarningsTranscriptClient
from qsip.kafka_client import KafkaProducer
from qsip.redis_client import RedisClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EARNINGS_PROCESSED = Counter("earnings_processed_total", "Earnings transcripts processed", ["ticker"])

UNIVERSE = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "JPM", "JNJ", "V"]


class EarningsService:
    def __init__(self):
        self.cfg = Config.from_env()
        self.db = TimescaleDB(self.cfg.db_dsn)
        self.redis = RedisClient(self.cfg.redis_addr)
        self.producer = KafkaProducer(self.cfg.kafka_brokers)
        self.client = EarningsTranscriptClient(
            alpha_vantage_key=self.cfg.alpha_vantage_key,
            fmp_key=self.cfg.fmp_key,
        )

    def run(self):
        start_http_server(int(os.getenv("METRICS_PORT", "9091")))
        while True:
            for ticker in UNIVERSE:
                try:
                    self._process_ticker(ticker)
                except Exception as e:
                    logger.error("earnings processing failed for %s: %s", ticker, e)
            time.sleep(3600)

    def _process_ticker(self, ticker: str):
        transcripts = self.client.fetch(ticker)
        for t in transcripts:
            self.db.insert_earnings_transcript(t)
            event = {
                "event_id": f"earnings-{ticker}-{datetime.utcnow().isoformat()}",
                "source": "earnings-service",
                "event_type": "earnings_transcript",
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": t,
            }
            self.producer.send("raw-events", ticker, event)
            self.redis.publish("earnings", event)
            EARNINGS_PROCESSED.labels(ticker=ticker).inc()
            logger.info("earnings transcript processed %s guidance=%s", ticker, t.get("guidance_change"))


if __name__ == "__main__":
    EarningsService().run()
