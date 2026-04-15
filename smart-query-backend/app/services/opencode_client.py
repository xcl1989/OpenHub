"""OpenCode HTTP 客户端服务 - 全局单例，连接池复用"""

import httpx
from typing import Optional
from app.config import config


class OpenCodeClient:
    """OpenCode API 客户端，使用全局连接池"""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    def _get_auth(self) -> tuple[str, str]:
        return (config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD)

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
                transport=httpx.AsyncHTTPTransport(retries=3),
            )
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str, **kwargs) -> httpx.Response:
        client = await self.get_client()
        url = f"{config.OPENCODE_BASE_URL}{path}"
        kwargs.setdefault("auth", self._get_auth())
        return await client.get(url, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        client = await self.get_client()
        url = f"{config.OPENCODE_BASE_URL}{path}"
        kwargs.setdefault("auth", self._get_auth())
        return await client.post(url, **kwargs)

    async def put(self, path: str, **kwargs) -> httpx.Response:
        client = await self.get_client()
        url = f"{config.OPENCODE_BASE_URL}{path}"
        kwargs.setdefault("auth", self._get_auth())
        return await client.put(url, **kwargs)

    async def patch(self, path: str, **kwargs) -> httpx.Response:
        client = await self.get_client()
        url = f"{config.OPENCODE_BASE_URL}{path}"
        kwargs.setdefault("auth", self._get_auth())
        return await client.patch(url, **kwargs)

    async def get_client_for_stream(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
                transport=httpx.AsyncHTTPTransport(retries=3),
            )
        return self._client


opencode_client = OpenCodeClient()
