import json
from typing import Optional


class IdempotencyManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 86400  # 24 hours per OLLAMA API spec

    async def check_or_create(self, key: str, operation: str, params: dict) -> tuple[bool, Optional[dict]]:
        """
        Returns: (is_new, cached_result)
        True = proceed with operation
        False = return cached result
        """
        cache_key = f"idempotency:{operation}:{key}"
        cached = await self.redis.get(cache_key)
        if cached:
            return False, json.loads(cached)

        await self.redis.setex(cache_key, self.ttl, json.dumps({"status": "pending"}))
        return True, None

    async def complete_operation(self, key: str, operation: str, result: dict):
        cache_key = f"idempotency:{operation}:{key}"
        await self.redis.setex(cache_key, self.ttl, json.dumps({"status": "completed", "result": result}))
