# 测试路径由 pyproject.toml 的 pythonpath 提供，此处无需 sys.path 操作。

from __future__ import annotations

import pytest

from app.factory import create_app
from app.schema.provider import ModelProvider


class FakeRegistry:
    """内存版模型注册表。

    只实现 controller 真正用到的四个读方法。用它是为了避免测试去碰
    config/model_providers.json —— 那是真实的密钥文件。
    """

    def __init__(self, providers: list[ModelProvider] | None = None):
        self.providers = list(providers or [])

    def enabled_providers(self) -> list[ModelProvider]:
        return [p for p in self.providers if p.enabled]

    def get_enabled_provider(self, served_model_id: str | None = None) -> ModelProvider:
        wanted = served_model_id or self.get_default_model_id()
        for provider in self.providers:
            if provider.served_model_id == wanted and provider.enabled:
                return provider
        raise KeyError(wanted or "default")

    def get_default_model_id(self) -> str:
        return self.providers[0].served_model_id if self.providers else ""

    def public_registry(self) -> dict:
        return {
            "providers": [
                {"served_model_id": p.served_model_id, "name": p.name}
                for p in self.providers
            ],
            "default_model_id": self.get_default_model_id(),
        }


class FakeServices:
    """services 容器的替身：透传通道压根不碰它，但 create_app 要求非 None。"""

    chat = None
    quiz = None
    exam = None
    knowledge_base = None
    client_factory = None

    def warm_up(self) -> None:
        pass

    def invalidate_provider(self, served_model_id=None) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.fixture
def provider() -> ModelProvider:
    return ModelProvider(
        name="DeepSeek",
        served_model_id="deepseek",
        base_url="https://api.deepseek.com",
        upstream_model="deepseek-chat",
        auth_mode="bearer",
        api_key="sk-test",
        temperature=0.1,
    )


@pytest.fixture
def registry(provider) -> FakeRegistry:
    return FakeRegistry([provider])


@pytest.fixture
def app(registry):
    application = create_app(
        {"TESTING": True},
        registry=registry,
        services=FakeServices(),
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_provider(registry, provider) -> ModelProvider:
    """语义上的"注册表里已经有一个可用模型"。registry fixture 已经放好了。"""
    return provider
