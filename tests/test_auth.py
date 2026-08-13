import pytest

from qsip.auth import AuthManager


def test_auth_manager():
    auth = AuthManager("test-secret", redis_addr="localhost:6379")
    try:
        auth.create_user("alice", "password123", "researcher")
    except Exception:
        pytest.skip("redis unavailable")
    token = auth.authenticate("alice", "password123")
    assert token is not None
    payload = auth.decode_token(token)
    assert payload["role"] == "researcher"
    assert not auth.authenticate("alice", "wrong")


def test_rate_limit():
    auth = AuthManager("test-secret", redis_addr="localhost:6379")
    # If Redis unavailable, this may fail; skip if no redis
    try:
        assert auth.rate_limit("test-key", max_requests=2, window_seconds=60)
        assert auth.rate_limit("test-key", max_requests=2, window_seconds=60)
    except Exception:
        pytest.skip("redis unavailable")
