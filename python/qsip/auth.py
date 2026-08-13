from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable

import jwt
import redis


class AuthManager:
    """JWT + RBAC + Redis token-bucket rate limiting."""

    def __init__(self, secret: str, redis_addr: str = "localhost:6379"):
        self.secret = secret or os.urandom(32).hex()
        self.redis = redis.Redis.from_url(f"redis://{redis_addr}", decode_responses=True)

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, username: str, password: str, role: str = "viewer") -> dict[str, Any]:
        # In production store hashed passwords in DB; this is simplified
        key = f"user:{username}"
        if self.redis.exists(key):
            raise ValueError("user exists")
        self.redis.hset(key, mapping={"password": self.hash_password(password), "role": role})
        return {"username": username, "role": role}

    def authenticate(self, username: str, password: str) -> str | None:
        key = f"user:{username}"
        stored = self.redis.hgetall(key)
        if not stored:
            return None
        if stored.get("password") != self.hash_password(password):
            return None
        token = jwt.encode(
            {
                "sub": username,
                "role": stored.get("role", "viewer"),
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(hours=24),
            },
            self.secret,
            algorithm="HS256",
        )
        return token

    def decode_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, self.secret, algorithms=["HS256"])
        except Exception:
            return None

    def require_role(self, allowed_roles: list[str]):
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Token must be passed as kwarg by middleware
                token = kwargs.pop("_token", None)
                if not token:
                    raise PermissionError("missing token")
                payload = self.decode_token(token)
                if not payload or payload.get("role") not in allowed_roles:
                    raise PermissionError("insufficient permissions")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def rate_limit(self, key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        """Token bucket rate limit. Returns True if allowed."""
        bucket_key = f"rl:{key}"
        pipe = self.redis.pipeline()
        now = time.time()
        pipe.hmget(bucket_key, ["tokens", "last"])
        result = pipe.execute()
        tokens, last = (float(x) if x else None for x in result[0])
        if tokens is None:
            tokens = max_requests
            last = now

        elapsed = now - last
        tokens = min(max_requests, tokens + elapsed * (max_requests / window_seconds))
        if tokens < 1:
            return False
        tokens -= 1
        pipe.hset(bucket_key, mapping={"tokens": tokens, "last": now})
        pipe.expire(bucket_key, window_seconds)
        pipe.execute()
        return True
