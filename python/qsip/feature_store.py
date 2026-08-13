from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

import numpy as np

from qsip.db import TimescaleDB


class FeatureStore:
    """Central feature registry guaranteeing training/inference parity."""

    def __init__(self, db: TimescaleDB, version: str = "v1"):
        self.db = db
        self.version = version

    def save(self, ticker: str, features: dict[str, Any], is_training: bool = False) -> None:
        self.db.store_feature_vector(ticker, self.version, features, is_training)

    def get(self, ticker: str) -> dict[str, Any] | None:
        row = self.db.get_latest_feature_vector(ticker, self.version)
        if not row:
            return None
        features = row["features"] if isinstance(row["features"], dict) else json.loads(row["features"])
        return features

    def get_training_data(self, limit: int = 100_000) -> list[tuple[dict[str, Any], float | None]]:
        rows = self.db.get_training_features(self.version, limit)
        result = []
        for r in rows:
            features = r["features"] if isinstance(r["features"], dict) else json.loads(r["features"])
            # target is stored separately or derived
            result.append((features, r.get("target_return_20d")))
        return result

    def feature_signature(self, features: dict[str, Any]) -> str:
        """Hash of feature keys/values for reproducibility."""
        canonical = json.dumps(features, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
