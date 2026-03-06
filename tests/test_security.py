# tests/test_security.py
import pytest
import asyncio
from app.utils.auth import AuthManager
from app.middleware.security import RateLimiter


def test_auth_manager_constant_time(tmp_path):
    users_file = tmp_path / "authorized_users.txt"
    users_file.write_text("admin:secretkey123")

    auth = AuthManager(users_file=users_file)

    # Valid token
    assert auth.validate_token("admin:secretkey123") == "admin"

    # Invalid token
    assert auth.validate_token("admin:wrongkey") is None

    # Empty string/None tests
    assert auth.validate_token("") is None
    assert auth.validate_token(None) is None


@pytest.mark.asyncio
async def test_rate_limiter_sliding_window():
    limiter = RateLimiter()
    key = "test_user_ip"

    # Suppose window is 1 second, max requests is 2
    assert await limiter.is_allowed(key, max_requests=2, window_seconds=1) is True
    assert await limiter.is_allowed(key, max_requests=2, window_seconds=1) is True
    assert await limiter.is_allowed(key, max_requests=2, window_seconds=1) is False

    # Wait for the window to pass
    await asyncio.sleep(1.1)

    # Should be allowed again
    assert await limiter.is_allowed(key, max_requests=2, window_seconds=1) is True
