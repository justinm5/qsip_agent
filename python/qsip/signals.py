from __future__ import annotations

import json
import logging
import os
import pickle
from datetime import datetime
from typing import Any

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

DEFAULT_FEATURE_KEYS = [
    "return_1d", "return_5d", "return_20d", "return_60d",
    "volatility_20d", "volume_ratio", "rsi_14", "macd", "macd_signal",
    "bb_position", "zscore_20d",
    "insider_buys_30d", "insider_sells_30d", "insider_buy_ratio",
    "insider_buy_dollars_30d", "insider_sell_dollars_30d", "insider_net_dollars_30d",
    "news_sentiment_mean", "news_sentiment_std", "news_count_24h",
    "earnings_sentiment", "guidance_change", "risk_score",
    "options_activity_score", "call_put_ratio",
]


class SignalEngine:
    """Rule-based + ML signal generation."""

    def __init__(self, model_path: str = "/models", feature_keys: list[str] | None = None):
        self.model_path = model_path
        self.feature_keys = feature_keys or DEFAULT_FEATURE_KEYS
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        model_file = os.path.join(self.model_path, "xgb_model.pkl")
        if os.path.exists(model_file):
            try:
                with open(model_file, "rb") as f:
                    self.model = pickle.load(f)
                logger.info("loaded ML model from %s", model_file)
            except Exception as e:
                logger.warning("failed to load model: %s", e)

    def generate(self, ticker: str, features: dict[str, float]) -> list[dict[str, Any]]:
        signals = []

        if self._insider_conviction(features):
            signals.append(self._make_signal(ticker, "insider_conviction", "long", features))

        if self._volume_anomaly(features):
            signals.append(self._make_signal(ticker, "volume_anomaly", "long" if features.get("return_1d", 0) > 0 else "short", features))

        if self._news_surprise(features):
            signals.append(self._make_signal(ticker, "news_surprise", "long" if features.get("news_sentiment_mean", 0) > 0 else "short", features))

        if self._price_divergence(features):
            signals.append(self._make_signal(ticker, "price_divergence", "long", features))

        if self._earnings_guidance(features):
            signals.append(self._make_signal(ticker, "earnings_guidance", "long" if features.get("guidance_change", 0) > 0 else "short", features))

        if self._options_activity(features):
            signals.append(self._make_signal(ticker, "options_activity", "long" if features.get("call_put_ratio", 1) > 2 else "short", features))

        # ML overlay
        ml_score = self._ml_score(features)
        for sig in signals:
            sig["ml_score"] = ml_score
            sig["score"] = self._ensemble_score(sig["score"], ml_score, features)

        if not signals and ml_score > 0.65:
            signals.append(self._make_signal(ticker, "ml_alpha", "long", features, ml_score=ml_score))

        return signals

    def _insider_conviction(self, f: dict[str, float]) -> bool:
        return (
            f.get("insider_buy_ratio", 0) > 0.7
            and f.get("insider_buy_dollars_30d", 0) > 1_000_000
            and f.get("return_20d", 0) < 0.05
        )

    def _volume_anomaly(self, f: dict[str, float]) -> bool:
        return f.get("volume_ratio", 1.0) > 3.0

    def _news_surprise(self, f: dict[str, float]) -> bool:
        return abs(f.get("news_sentiment_mean", 0)) > 0.5 and abs(f.get("return_1d", 0)) < 0.005

    def _price_divergence(self, f: dict[str, float]) -> bool:
        return f.get("insider_net_dollars_30d", 0) > 500_000 and f.get("return_20d", 0) < -0.10

    def _earnings_guidance(self, f: dict[str, float]) -> bool:
        return abs(f.get("guidance_change", 0)) > 0.5 or f.get("earnings_sentiment", 0) > 0.6

    def _options_activity(self, f: dict[str, float]) -> bool:
        return f.get("options_activity_score", 0) > 5.0

    def _ml_score(self, f: dict[str, float]) -> float:
        if self.model is None:
            return 0.5
        try:
            x = self._to_vector(f)
            pred = self.model.predict_proba([x])[0][1]
            return float(pred)
        except Exception as e:
            logger.warning("ml prediction failed: %s", e)
            return 0.5

    def _ensemble_score(self, rule_score: float, ml_score: float, f: dict[str, float]) -> float:
        weight = 0.5 if self.model else 0.1
        base = (1 - weight) * rule_score + weight * ml_score
        if f.get("insider_buy_ratio", 0) > 0.8 and f.get("volatility_20d", 1.0) < 0.4:
            base = min(1.0, base + 0.1)
        return float(base)

    def _make_signal(self, ticker: str, signal_type: str, direction: str, features: dict[str, float], ml_score: float | None = None) -> dict[str, Any]:
        base_score = self._base_score(signal_type, features)
        return {
            "signal_id": f"{ticker}_{signal_type}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            "timestamp": datetime.utcnow().isoformat(),
            "ticker": ticker,
            "signal_type": signal_type,
            "direction": direction,
            "score": round(base_score, 4),
            "features": features,
            "ml_score": round(ml_score if ml_score is not None else 0.5, 4),
        }

    def _base_score(self, signal_type: str, f: dict[str, float]) -> float:
        if signal_type == "insider_conviction":
            return min(1.0, 0.5 + 0.2 * f.get("insider_buy_ratio", 0) + 0.0000002 * f.get("insider_buy_dollars_30d", 0))
        if signal_type == "volume_anomaly":
            return min(1.0, 0.4 + 0.1 * f.get("volume_ratio", 1.0))
        if signal_type == "news_surprise":
            return min(1.0, 0.4 + abs(f.get("news_sentiment_mean", 0)))
        if signal_type == "price_divergence":
            return min(1.0, 0.5 - f.get("return_20d", 0))
        if signal_type == "earnings_guidance":
            return min(1.0, 0.4 + abs(f.get("guidance_change", 0)) + f.get("earnings_sentiment", 0))
        if signal_type == "options_activity":
            return min(1.0, 0.4 + 0.1 * f.get("options_activity_score", 0))
        if signal_type == "ml_alpha":
            return f.get("ml_score", 0.5)
        return 0.5

    def _to_vector(self, f: dict[str, float]) -> list[float]:
        return [float(f.get(k, 0.0)) for k in self.feature_keys]


def attach_targets(prices: pl.DataFrame, feature_time: datetime, horizon_days: int = 20) -> float | None:
    """Compute forward excess return for a feature vector."""
    if prices.height < horizon_days + 1:
        return None
    future = prices.filter(pl.col("time") > feature_time).head(horizon_days)
    if future.height == 0:
        return None
    start = prices.filter(pl.col("time") <= feature_time)["close"].tail(1)[0]
    end = future["close"].tail(1)[0]
    if start == 0:
        return None
    return float((end - start) / start)
