from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OptionsFlowClient:
    """Fetch options flow and compute activity scores."""

    def __init__(self, polygon_key: str = ""):
        self.polygon_key = polygon_key
        self.client = httpx.Client(timeout=30.0)

    def fetch(self, ticker: str) -> list[dict[str, Any]]:
        if not self.polygon_key:
            return []
        try:
            # Snapshot of option contracts for ticker
            url = f"https://api.polygon.io/v3/reference/options/contracts"
            params = {
                "underlying_ticker": ticker,
                "apiKey": self.polygon_key,
                "limit": 100,
            }
            r = self.client.get(url, params=params)
            r.raise_for_status()
            contracts = r.json().get("results", [])
            results = []
            for c in contracts[:20]:
                oi = c.get("open_interest", 0) or 0
                vol = c.get("volume", 0) or 0
                if vol == 0:
                    continue
                score = self._activity_score(vol, oi, c.get("open_interest") or 0)
                results.append({
                    "timestamp": datetime.utcnow(),
                    "ticker": ticker,
                    "option_type": c.get("contract_type"),
                    "strike": c.get("strike_price"),
                    "expiration": c.get("expiration_date"),
                    "volume": vol,
                    "open_interest": oi,
                    "premium": vol * (c.get("strike_price") or 0) * 100,
                    "source": "polygon",
                    "activity_score": score,
                })
            return results
        except Exception as e:
            logger.error("options fetch failed: %s", e)
            return []

    def _activity_score(self, volume: int, open_interest: int, avg_volume: int) -> float:
        if avg_volume == 0:
            return float(volume)
        return float(volume / avg_volume)
