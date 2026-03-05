# app/utils/auth.py
import hmac
import hashlib
from pathlib import Path
from typing import Optional
from functools import lru_cache

class AuthManager:
    """File-based authentication with constant-time comparison."""

    def __init__(self, users_file: Path = None):
        self.users_file = users_file or Path("authorized_users.txt")
        self._cache = {}
        self._load_users_sync()

    def _load_users_sync(self):
        if not self.users_file.exists():
            return

        new_cache = {}
        with open(self.users_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ':' in line:
                    username, key = line.split(':', 1)
                    token = f"{username}:{key}"
                    new_cache[token] = username

        self._cache = new_cache

    def validate_token(self, token: str) -> Optional[str]:
        """Constant-time comparison to prevent timing attacks."""
        if not token:
            return None

        for cached_token, username in self._cache.items():
            if hmac.compare_digest(token, cached_token):
                return username

        return None

def get_current_user():
    # Placeholder for FastAPI dependency inject logic. Not defined in blueprint for some reason, so leaving as a dummy
    return "admin"
