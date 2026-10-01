"""连上游：握手单独限时，读超时照旧。离线运行（只看客户端配置，不发请求）。"""

from __future__ import annotations

import httpx

from app.config import UPSTREAM_CONNECT_TIMEOUT
from app.infra.model_client_factory import ModelClientFactory
from app.schema.provider import ModelProvider


PROVIDER = ModelProvider(
    name="t", served_model_id="t", base_url="http://127.0.0.1:9/v1", upstream_model="u",
    auth_mode="none", api_key="", temperature=0.1,
    created_at="2026-09-30T00:00:00Z", updated_at="2026-09-30T00:00:00Z",
)


def test_connect_timeout_is_short_while_read_timeout_stays_long():
    client = ModelClientFactory().get(PROVIDER, timeout_seconds=90, max_retries=0)
    timeout = client.request_timeout
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == UPSTREAM_CONNECT_TIMEOUT
    assert timeout.read == 90, "生成慢是正常的，读超时不能跟着收紧"


def test_connect_timeout_never_exceeds_a_short_request_timeout():
    client = ModelClientFactory().get(PROVIDER, timeout_seconds=5, max_retries=0)
    assert client.request_timeout.connect == 5
