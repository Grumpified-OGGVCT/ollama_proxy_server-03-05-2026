# app/middleware/security.py
import time
from typing import Dict
from collections import defaultdict
from fastapi import FastAPI, Request

class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds

        # Clean old entries
        self._requests[key] = [
            ts for ts in self._requests[key]
            if ts > window_start
        ]

        if len(self._requests[key]) >= max_requests:
            return False

        self._requests[key].append(now)
        return True

def add_security_headers_middleware(app: FastAPI):
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
