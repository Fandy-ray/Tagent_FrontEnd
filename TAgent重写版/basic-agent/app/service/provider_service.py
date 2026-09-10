"""provider 的请求级校验与环境配置装配。

service 层：把外部传入的原始 payload 变成可信的 ModelProvider，不落盘。
（WebUI 经内部通道发来的临时 provider 走这里，永不进注册表。）
"""

from __future__ import annotations

from typing import Any

from app.schema.provider import (
    AUTH_MODES,
    PROVIDER_ID_PATTERN,
    ModelProvider,
    normalize_base_url,
    normalize_temperature,
)
from app.util.timeutil import utc_now


def parse_ephemeral_provider(payload: Any) -> ModelProvider:
    """Validate a request-scoped provider without persisting it to the registry."""
    if not isinstance(payload, dict):
        raise ValueError("provider must be an object")

    now = utc_now()
    name = str(payload.get("name") or "").strip()
    served_model_id = str(payload.get("served_model_id") or "").strip()
    base_url = normalize_base_url(payload.get("base_url"))
    upstream_model = str(payload.get("upstream_model") or "").strip()
    auth_mode = str(payload.get("auth_mode") or "bearer").strip().lower()
    temperature = normalize_temperature(payload.get("temperature", 0.1))

    if not name:
        raise ValueError("provider name is required")
    if not PROVIDER_ID_PATTERN.fullmatch(served_model_id):
        raise ValueError("served_model_id contains unsupported characters or has invalid length")
    if not upstream_model:
        raise ValueError("upstream_model is required")
    if auth_mode not in AUTH_MODES:
        raise ValueError("auth_mode must be 'bearer' or 'none'")

    api_key = "" if auth_mode == "none" else str(payload.get("api_key") or "")
    if auth_mode == "bearer" and not api_key:
        raise ValueError("api_key is required when auth_mode is bearer")

    return ModelProvider(
        name=name,
        served_model_id=served_model_id,
        base_url=base_url,
        upstream_model=upstream_model,
        auth_mode=auth_mode,
        api_key=api_key,
        temperature=temperature,
        enabled=True,
        created_at=str(payload.get("created_at") or now),
        updated_at=str(payload.get("updated_at") or now),
    )
