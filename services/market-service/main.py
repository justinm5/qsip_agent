import json
import logging
import os
import threading
import time
from datetime import datetime

import yfinance as yf
from prometheus_client import Counter, Histogram, start_http_server

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.kafka_client import KafkaProducer
from qsip.market import MarketDataClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TICKS_FETCHED = Counter("market_ticks_fetched_total", "Market ticks fetched", ["ticker"])
FETCH_LATENCY = Histogram("market_fetch_seconds", "Market fetch latency")

UNIVERSE = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "JPM",
    "XOM", "JNJ", "V", "PG", "UNH", "HD", "MA", "BAC", "ABBV", "PFE",
    "KO", "PEP", "COST", "TMO", "AVGO", "DIS", "WMT", "MRK", "CVX",
    "ABT", "MCD", "ACN", "ADBE", "CRM", "NKE", "TXN", "VZ", "NFLX",
    "PM", "BMY", "QCOM", "RTX",
]


class MarketService:
    def __init__(self):
        self.cfg = Config.from_env()
        self.db = TimescaleDB(self.cfg.db_dsn)
        self.producer = KafkaProducer(self.cfg.kafka_brokers)
        self.client = MarketDataClient(
            polygon_key=self.cfg.polygon_api_key,
            alpaca_key=self.cfg.alpaca_api_key,
            alpaca_secret=self.cfg.alpaca_secret_key,
        )

    def run(self):
        start_http_server(int(os.getenv("METRICS_PORT", "9091")))
        while True:
            self._fetch_all()
            time.sleep(60)

    def _fetch_all(self):
        threads = []
        for ticker in UNIVERSE:
            t = threading.Thread(target=self._fetch_one, args=(ticker,), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=60)

    def _fetch_one(self, ticker: str):
        with FETCH_LATENCY.time():
            rows = self.client.fetch(ticker)
            if not rows:
                return
            for row in rows:
                self.db.insert_market_data(ticker, row)
            event = {
                "event_id": f"{ticker}_{datetime.utcnow().isoformat()}",
                "source": "market-service",
                "event_type": "ohlcv",
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": {"data": rows, "source": rows[0].get("source", "unknown")},
            }
            self.producer.send("raw-events", ticker, event)
            TICKS_FETCHED.labels(ticker=ticker).inc(rows[-1].get("volume", 0))
            logger.info("market fetched %s rows=%d", ticker, len(rows))


if __name__ == "__main__":
    MarketService().run()
