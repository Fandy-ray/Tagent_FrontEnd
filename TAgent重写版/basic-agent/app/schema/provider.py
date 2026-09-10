"""模型 provider 的数据结构与字段校验规则。

schema 层：只描述"一个合法的 provider 长什么样"，不做持久化、不发请求。
repository 与 service 都依赖本模块；本模块不依赖任何其他层。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse


PROVIDER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
AUTH_MODES = {"bearer", "none"}


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    api_key: str
    base_url: str
    model: str
    served_model_id: str
    temperature: float
    auth_mode: str = "bearer"

@dataclass(frozen=True)
class ModelProvider:
    name: str
    served_model_id: str
    base_url: str
    upstream_model: str
    auth_mode: str
    api_key: str
    temperature: float = 0.1
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    @property
    def as_openai_config(self) -> OpenAICompatibleConfig:
        return OpenAICompatibleConfig(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.upstream_model,
            served_model_id=self.served_model_id,
            temperature=self.temperature,
            auth_mode=self.auth_mode,
        )

def parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed

def normalize_base_url(value: Any) -> str:
    base_url = str(value or "").strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an http:// or https:// URL")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not contain credentials")
    return base_url

def normalize_temperature(value: Any) -> float:
    try:
        temperature = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("temperature must be a number") from exc
    if not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("temperature must be a finite number between 0 and 2")
    return temperature

def mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 4:
        return "****"
    return f"****{api_key[-4:]}"
