import threading
from urllib.parse import urlparse

import httpx
from langchain_openai import ChatOpenAI

from app.schema.provider import ModelProvider


def _remove_authorization(request: httpx.Request) -> None:
    if "Authorization" in request.headers:
        del request.headers["Authorization"]


def _uses_environment_proxy(base_url: str) -> bool:
    hostname = (urlparse(base_url).hostname or "").lower()
    return hostname not in {"127.0.0.1", "localhost", "::1"}


class ModelClientFactory:
    def __init__(self, timeout_seconds: float = 180, max_retries: int = 1):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._lock = threading.RLock()
        self._clients: dict[tuple[str, str, float, int], ChatOpenAI] = {}
        self._http_clients: dict[tuple[str, str, float, int], httpx.Client] = {}

    def get(
        self,
        provider: ModelProvider,
        *,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> ChatOpenAI:
        request_timeout = timeout_seconds or self.timeout_seconds
        request_retries = self.max_retries if max_retries is None else max_retries
        key = (provider.served_model_id, provider.updated_at, request_timeout, request_retries)
        with self._lock:
            cached = self._clients.get(key)
            if cached is not None:
                return cached

            self._invalidate_unlocked(provider.served_model_id)
            hooks = {"request": [_remove_authorization]} if provider.auth_mode == "none" else None
            http_client = httpx.Client(
                timeout=request_timeout,
                event_hooks=hooks,
                trust_env=_uses_environment_proxy(provider.base_url),
            )
            client = ChatOpenAI(
                model=provider.upstream_model,
                base_url=provider.base_url,
                api_key=provider.api_key if provider.auth_mode == "bearer" else "local-no-auth",
                temperature=provider.temperature,
                timeout=request_timeout,
                max_retries=request_retries,
                http_client=http_client,
            )
            self._http_clients[key] = http_client
            self._clients[key] = client
            return client

    def invalidate(self, served_model_id: str | None = None) -> None:
        with self._lock:
            if served_model_id is None:
                keys = list(self._clients)
                for model_id, _updated_at, _timeout, _retries in keys:
                    self._invalidate_unlocked(model_id)
            else:
                self._invalidate_unlocked(served_model_id)

    def close(self) -> None:
        self.invalidate(None)

    def _invalidate_unlocked(self, served_model_id: str) -> None:
        keys = [key for key in self._clients if key[0] == served_model_id]
        for key in keys:
            self._clients.pop(key, None)
            http_client = self._http_clients.pop(key, None)
            if http_client is not None:
                http_client.close()
