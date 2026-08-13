import logging
import os
import time
from datetime import datetime

from prometheus_client import Counter, start_http_server

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.kafka_client import KafkaProducer
from qsip.options import OptionsFlowClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPTIONS_PROCESSED = Counter("options_processed_total", "Options flow records processed", ["ticker"])

UNIVERSE = ["AAPL", "TSLA", "NVDA", "AMZN", "META", "MSFT", "GOOGL", "SPY", "QQQ"]


class OptionsService:
    def __init__(self):
        self.cfg = Config.from_env()
        self.db = TimescaleDB(self.cfg.db_dsn)
        self.producer = KafkaProducer(self.cfg.kafka_brokers)
        self.client = OptionsFlowClient(polygon_key=self.cfg.polygon_api_key)

    def run(self):
        start_http_server(int(os.getenv("METRICS_PORT", "9091")))
        while True:
            for ticker in UNIVERSE:
                try:
                    self._process_ticker(ticker)
                except Exception as e:
                    logger.error("options processing failed for %s: %s", ticker, e)
            time.sleep(300)

    def _process_ticker(self, ticker: str):
        rows = self.client.fetch(ticker)
        for row in rows:
            self.db.insert_options_flow(row)
            event = {
                "event_id": f"options-{ticker}-{row.get('expiration')}-{row.get('strike')}",
                "source": "options-service",
                "event_type": "options_flow",
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": row,
            }
            self.producer.send("raw-events", ticker, event)
            OPTIONS_PROCESSED.labels(ticker=ticker).inc()
        if rows:
            logger.info("options flow %s records=%d", ticker, len(rows))


if __name__ == "__main__":
    OptionsService().run()
