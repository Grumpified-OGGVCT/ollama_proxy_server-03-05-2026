import httpx
from typing import Dict


class BackendConnectionPool:
    def __init__(self):
        self.pools: Dict[str, httpx.AsyncClient] = {}

    def get_client(self, server_url: str) -> httpx.AsyncClient:
        if server_url not in self.pools:
            self.pools[server_url] = httpx.AsyncClient(http2=True, limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=300.0))
        return self.pools[server_url]
