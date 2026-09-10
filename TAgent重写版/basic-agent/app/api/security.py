"""管理通道与内部通道的 token 鉴权。

两个 token 都用 hmac.compare_digest 做定长比较，避免计时侧信道。
未配置 token 时返回 503 而不是 403：这是"功能未启用"，不是"你没权限"。
"""

from __future__ import annotations

import hmac

from flask import current_app, request

from app.errors.api_errors import AgentAPIError


def require_admin_token() -> None:
    expected = current_app.config.get("AGENT_ADMIN_TOKEN", "")
    if not expected:
        raise AgentAPIError(
            "Agent administration is unavailable because its token is not configured.",
            503,
            "admin_token_not_configured",
        )
    provided = request.headers.get("X-Agent-Admin-Token", "")
    if not provided or not hmac.compare_digest(provided, expected):
        raise AgentAPIError("Forbidden.", 403, "forbidden")

def require_internal_token() -> None:
    expected = current_app.config.get("AGENT_INTERNAL_TOKEN", "")
    if not expected:
        raise AgentAPIError(
            "The internal agent channel is unavailable because its token is not configured.",
            503,
            "internal_token_not_configured",
        )
    provided = request.headers.get("X-Agent-Internal-Token", "")
    if not provided or not hmac.compare_digest(provided, expected):
        raise AgentAPIError("Forbidden.", 403, "forbidden")
