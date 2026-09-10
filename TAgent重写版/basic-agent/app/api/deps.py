"""controller 的依赖获取入口。

**这是全工程唯一允许碰 current_app.extensions 的地方。**
service 层不认识 Flask，拿依赖一律经过这里注入。
"""

from __future__ import annotations

from flask import current_app

from app.errors.api_errors import ModelNotFoundError


def get_registry():
    return current_app.extensions["model_provider_registry"]


def select_provider(model_id: str | None = None):
    registry = get_registry()
    try:
        return registry.get_enabled_provider(model_id)
    except KeyError:
        missing = model_id or registry.get_default_model_id() or "default"
        raise ModelNotFoundError(missing)


def get_services():
    return current_app.extensions["services"]


def get_chat_service():
    return get_services().chat


def get_quiz_service():
    return get_services().quiz


def get_exam_service():
    return get_services().exam


def invalidate_provider(model_id: str | None) -> None:
    services = current_app.extensions.get("services")
    if services is not None and hasattr(services, "invalidate_provider"):
        services.invalidate_provider(model_id)
