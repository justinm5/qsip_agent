from __future__ import annotations

import json
from typing import Any

import redis


class RedisClient:
    def __init__(self, addr: str = "localhost:6379"):
        self.client = redis.Redis.from_url(f"redis://{addr}", decode_responses=True)

    def publish(self, channel: str, payload: dict[str, Any]) -> None:
        self.client.publish(channel, json.dumps(payload))

    def set_json(self, key: str, payload: dict[str, Any], ex: int | None = None) -> None:
        self.client.set(key, json.dumps(payload), ex=ex)

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def cache_signal(self, signal: dict[str, Any]) -> None:
        key = f"signal:{signal['ticker']}:{signal['signal_id']}"
        self.set_json(key, signal, ex=3600)
        self.publish("signals", signal)

    def cache_feature(self, ticker: str, features: dict[str, Any]) -> None:
        self.set_json(f"features:{ticker}", features, ex=300)
