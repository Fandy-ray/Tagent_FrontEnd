"""上游 LLM 异常 -> 本服务领域异常的翻译。

放在 infra/：认识 openai 库的异常类型是基础设施的事，
service 只应看到 AgentAPIError / UpstreamLLMError 这类领域词汇。
"""

from __future__ import annotations

from langchain_core.exceptions import OutputParserException
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from app.errors.api_errors import AgentAPIError


def is_timeout_error(error: Exception) -> bool:
    if isinstance(error, (APITimeoutError, TimeoutError)):
        return True
    return "timeout" in type(error).__name__.lower() or "timed out" in str(error).lower()


def translate_upstream_error(error: Exception) -> AgentAPIError:
    if isinstance(error, AgentAPIError):
        return error
    if isinstance(error, AuthenticationError):
        return AgentAPIError("The selected provider rejected its credentials.", 401, "upstream_authentication_error")
    if isinstance(error, RateLimitError):
        return AgentAPIError("The selected provider is rate limited.", 429, "upstream_rate_limited")
    if isinstance(error, APITimeoutError):
        return AgentAPIError("The selected provider timed out.", 504, "upstream_timeout")
    if isinstance(error, APIConnectionError):
        cause = str(getattr(error, "__cause__", "") or error)
        if "CERTIFICATE" in cause.upper() or "SSL" in cause.upper():
            return AgentAPIError(
                "无法校验 DeepSeek 的 HTTPS 证书，网络可能被拦截或需要代理。",
                502,
                "upstream_unavailable",
            )
        return AgentAPIError("The selected provider is unavailable.", 502, "upstream_unavailable")
    if isinstance(error, (BadRequestError, OutputParserException, ValueError)):
        return AgentAPIError("The selected provider returned an invalid response.", 502, "upstream_invalid_response")
    return AgentAPIError("The selected provider request failed.", 502, "upstream_error")
