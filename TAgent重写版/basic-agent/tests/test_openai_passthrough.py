"""透传通道 /v1/raw 的行为约定。

这里钉住的核心事实是：**它不做检索注入**。
/v1/chat/completions 会把课程教材塞进 prompt，OpenNotebook 拿它做摘要会跑偏；
/v1/raw/chat/completions 必须原样转发。这条一旦被改坏，OpenNotebook 那头
表现为"总结出来的东西里混进了系统仿真教材"，很难反查到这里，所以用测试焊死。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.infra import passthrough_client
from app.schema.provider import ModelProvider


def make_provider(**overrides) -> ModelProvider:
    fields = {
        "name": "DeepSeek",
        "served_model_id": "deepseek",
        "base_url": "https://api.deepseek.com",
        "upstream_model": "deepseek-chat",
        "auth_mode": "bearer",
        "api_key": "sk-test",
        "temperature": 0.1,
    }
    fields.update(overrides)
    return ModelProvider(**fields)


class TestBuildPayload:
    def test_swaps_served_id_for_upstream_model(self):
        """客户端报 served_model_id，上游只认 upstream_model。"""
        payload = passthrough_client.build_payload(
            {"model": "deepseek", "messages": []}, make_provider()
        )
        assert payload["model"] == "deepseek-chat"

    def test_drops_tagent_only_fields(self):
        """notebook_ids 是 TAgent 的扩展字段，上游会因为不认识而报 400。"""
        payload = passthrough_client.build_payload(
            {"model": "deepseek", "messages": [], "notebook_ids": ["nb:1"]},
            make_provider(),
        )
        assert "notebook_ids" not in payload

    def test_forwards_arbitrary_openai_fields(self):
        """透传的意义就在于 tools / response_format 这些字段能原样带过去。"""
        payload = passthrough_client.build_payload(
            {
                "model": "deepseek",
                "messages": [],
                "tools": [{"type": "function"}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
            },
            make_provider(),
        )
        assert payload["tools"] == [{"type": "function"}]
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["temperature"] == 0.7

    def test_does_not_mutate_caller_payload(self):
        original = {"model": "deepseek", "messages": [], "notebook_ids": ["nb:1"]}
        passthrough_client.build_payload(original, make_provider())
        assert original["model"] == "deepseek"
        assert original["notebook_ids"] == ["nb:1"]


class TestBuildHeaders:
    def test_bearer_mode_sends_key(self):
        headers = passthrough_client.build_headers(make_provider())
        assert headers["Authorization"] == "Bearer sk-test"

    def test_none_mode_omits_authorization(self):
        """auth_mode=none 的本地模型（Ollama / LM Studio）不能带 Authorization。"""
        headers = passthrough_client.build_headers(
            make_provider(auth_mode="none", api_key="")
        )
        assert "Authorization" not in headers


class TestPassthroughRoute:
    """走 Flask 测试客户端，确认请求真的原样落到上游、且没有检索注入。"""

    def test_forwards_messages_verbatim(self, client, monkeypatch, registered_provider):
        seen = {}

        def fake_complete(data, provider, **kwargs):
            seen["data"] = data
            seen["provider"] = provider
            body = json.dumps(
                {
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "ok"}}
                    ],
                }
            ).encode()
            return 200, body, "application/json"

        monkeypatch.setattr(passthrough_client, "complete", fake_complete)

        sent = [{"role": "user", "content": "把这段话总结成三句"}]
        response = client.post(
            "/v1/raw/chat/completions",
            json={"model": "deepseek", "messages": sent},
        )

        assert response.status_code == 200
        # 关键断言：messages 一字未改，没有任何检索出来的教材内容被塞进去
        assert seen["data"]["messages"] == sent
        assert len(seen["data"]["messages"]) == 1

    def test_relays_upstream_status_code(self, client, monkeypatch, registered_provider):
        """上游 401 就该原样是 401，不能被翻译成 502 —— 否则那头没法排查。"""

        def fake_complete(data, provider, **kwargs):
            return 401, b'{"error":{"message":"bad key"}}', "application/json"

        monkeypatch.setattr(passthrough_client, "complete", fake_complete)

        response = client.post(
            "/v1/raw/chat/completions",
            json={"model": "deepseek", "messages": []},
        )
        assert response.status_code == 401

    def test_streams_upstream_bytes(self, client, monkeypatch, registered_provider):
        def fake_stream(data, provider, **kwargs):
            assert data.get("stream") is True

            def generate():
                yield b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
                yield b"data: [DONE]\n\n"

            return generate()

        monkeypatch.setattr(passthrough_client, "stream", fake_stream)

        response = client.post(
            "/v1/raw/chat/completions",
            json={"model": "deepseek", "messages": [], "stream": True},
        )
        assert response.status_code == 200
        assert response.mimetype == "text/event-stream"
        assert b"[DONE]" in response.get_data()

    def test_models_list_matches_registry(self, client, registered_provider):
        """两条通道共用一份注册表 —— 这就是"统一配置"落地的地方。"""
        raw = client.get("/v1/raw/models").get_json()
        rag = client.get("/v1/models").get_json()
        assert [m["id"] for m in raw["data"]] == [m["id"] for m in rag["data"]]

    def test_unknown_model_is_rejected(self, client, registered_provider):
        response = client.post(
            "/v1/raw/chat/completions",
            json={"model": "not-registered", "messages": []},
        )
        assert response.status_code == 404


class TestTransportErrors:
    def test_timeout_maps_to_504(self):
        error = passthrough_client.translate_transport_error(
            httpx.TimeoutException("timed out")
        )
        assert error.status == 504

    def test_connect_error_maps_to_502(self):
        error = passthrough_client.translate_transport_error(
            httpx.ConnectError("refused")
        )
        assert error.status == 502

    def test_tls_failure_says_so_in_chinese(self):
        """证书问题在国内网络下很常见，错误信息要能直接看懂。"""
        error = passthrough_client.translate_transport_error(
            httpx.ConnectError("CERTIFICATE_VERIFY_FAILED")
        )
        assert "证书" in error.message
