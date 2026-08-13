from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


class DataValidator:
    """Validate raw events before they enter the feature pipeline."""

    def __init__(self, db: Any, redis: Any):
        self.db = db
        self.redis = redis
        self._seen = set()

    def validate(self, event: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
        """Return (is_valid, list_of_issues)."""
        issues = []
        event_type = event.get("event_type", "")
        source = event.get("source", "")
        ticker = event.get("ticker")
        payload = event.get("payload", {})

        # Duplicate detection
        if self._is_duplicate(event):
            issues.append(self._issue(source, event_type, ticker, "duplicate", "warning", event))

        # Timestamp validation
        if not self._valid_timestamp(event.get("timestamp")):
            issues.append(self._issue(source, event_type, ticker, "bad_timestamp", "critical", event, "timestamp invalid or out of range"))

        # Source-specific checks
        if event_type in ("ohlcv", "price"):
            price_issues = self._validate_price(payload)
            issues.extend(price_issues)

        if event_type == "news_article":
            if not payload.get("title") and not payload.get("url"):
                issues.append(self._issue(source, event_type, ticker, "corrupt_news", "critical", event, "missing title and url"))

        if event_type in ("4", "3", "5", "8-k", "13d", "13g"):
            if not payload.get("accession"):
                issues.append(self._issue(source, event_type, ticker, "missing_accession", "warning", event))

        return len(issues) == 0 or all(i["severity"] != "critical" for i in issues), issues

    def validate_price_frame(self, df: pl.DataFrame) -> tuple[pl.DataFrame, list[dict[str, Any]]]:
        """Validate a price frame and return cleaned frame + issues."""
        issues = []
        if df.height == 0:
            return df, issues

        # Outlier volume
        avg_volume = df["volume"].mean()
        if avg_volume and avg_volume > 0:
            max_ratio = (df["volume"].max() or 0) / avg_volume
            if max_ratio > 20:
                issues.append(self._issue("market", "ohlcv", None, "volume_outlier", "warning", {}, f"volume {max_ratio:.1f}x mean"))

        # Bad OHLC (high < low, negative prices)
        bad_prices = df.filter((pl.col("high") < pl.col("low")) | (pl.col("close") <= 0))
        if bad_prices.height > 0:
            issues.append(self._issue("market", "ohlcv", None, "bad_ohlc", "critical", {}, f"{bad_prices.height} bad OHLC rows"))
            df = df.filter((pl.col("high") >= pl.col("low")) & (pl.col("close") > 0))

        # Suspicious return
        returns = df["close"].pct_change().abs()
        if returns.max() and returns.max() > 0.5:
            issues.append(self._issue("market", "ohlcv", None, "price_jump", "warning", {}, f"max daily return {returns.max():.2%}"))

        return df, issues

    def _is_duplicate(self, event: dict[str, Any]) -> bool:
        key = event.get("event_id") or f"{event.get('source')}:{event.get('event_type')}:{event.get('ticker')}:{hash(str(event.get('payload')))}"
        if key in self._seen:
            return True
        self._seen.add(key)
        # Also check Redis cache for cross-instance dedup
        try:
            if self.redis and self.redis.client.exists(f"seen:{key}"):
                return True
            if self.redis:
                self.redis.client.set(f"seen:{key}", "1", ex=86400)
        except Exception:
            pass
        return False

    def _valid_timestamp(self, ts: Any) -> bool:
        if not ts:
            return False
        try:
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            now = datetime.utcnow()
            if ts > now + timedelta(minutes=5):
                return False
            if ts < now - timedelta(days=365 * 5):
                return False
            return True
        except Exception:
            return False

    def _validate_price(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        issues = []
        data = payload.get("data", [])
        if not data:
            return issues
        try:
            df = pl.DataFrame(data)
            _, price_issues = self.validate_price_frame(df)
            issues.extend(price_issues)
        except Exception as e:
            issues.append(self._issue("market", "ohlcv", None, "corrupt_price", "critical", payload, str(e)))
        return issues

    def _issue(
        self,
        source: str,
        event_type: str,
        ticker: str | None,
        issue_type: str,
        severity: str,
        payload: dict[str, Any],
        reason: str = "",
        event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "source": source,
            "event_type": event_type,
            "ticker": ticker,
            "issue_type": issue_type,
            "severity": severity,
            "event_id": event.get("event_id") if event else None,
            "payload": payload,
            "reason": reason,
        }
