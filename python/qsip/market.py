from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
import yfinance as yf

logger = logging.getLogger(__name__)


class MarketDataClient:
    """Multi-source market data fetcher."""

    def __init__(self, polygon_key: str = "", alpaca_key: str = "", alpaca_secret: str = ""):
        self.polygon_key = polygon_key
        self.alpaca_key = alpaca_key
        self.alpaca_secret = alpaca_secret
        self.client = httpx.Client(timeout=30.0)

    def fetch_yahoo(self, ticker: str, period: str = "1y") -> list[dict[str, Any]]:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=period, auto_adjust=True)
            rows = []
            for idx, row in hist.iterrows():
                rows.append({
                    "time": idx.to_pydatetime().replace(tzinfo=None),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                    "source": "yahoo",
                })
            return rows
        except Exception as e:
            logger.error("yahoo fetch failed for %s: %s", ticker, e)
            return []

    def fetch_polygon(self, ticker: str, days: int = 252) -> list[dict[str, Any]]:
        if not self.polygon_key:
            return []
        try:
            end = datetime.utcnow().date()
            start = end - timedelta(days=days)
            url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
            params = {"apiKey": self.polygon_key, "limit": 50000}
            r = self.client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            rows = []
            for r in data.get("results", []):
                ts = datetime.utcfromtimestamp(r["t"] / 1000)
                rows.append({
                    "time": ts,
                    "open": float(r.get("o", 0)),
                    "high": float(r.get("h", 0)),
                    "low": float(r.get("l", 0)),
                    "close": float(r.get("c", 0)),
                    "volume": int(r.get("v", 0)),
                    "vwap": float(r.get("vw", 0)),
                    "source": "polygon",
                })
            return rows
        except Exception as e:
            logger.error("polygon fetch failed for %s: %s", ticker, e)
            return []

    def fetch(self, ticker: str) -> list[dict[str, Any]]:
        rows = self.fetch_polygon(ticker)
        if rows:
            return rows
        return self.fetch_yahoo(ticker)
