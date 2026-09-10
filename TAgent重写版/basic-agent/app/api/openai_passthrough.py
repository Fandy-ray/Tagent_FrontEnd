"""OpenAI 兼容的**透传**通道。

给 OpenNotebook 这类"自己已经组好 prompt"的调用方用：模型注册表、Key、
超时都沿用 basic-agent 这一份，但不做任何检索注入。

    /v1/models            -> 走 RAG 的答疑通道（openai_compat.py）
    /v1/raw/models        -> 本模块，同一份模型清单
    /v1/raw/chat/completions -> 原样转发给上游

OpenNotebook 的 "OpenAI Compatible" provider 填 base_url 为
http://host.docker.internal:5001/v1/raw 即可（Docker Desktop 会把它 NAT 到
宿主的 127.0.0.1，所以 basic-agent 不必改成监听 0.0.0.0）。
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, stream_with_context

from app.api.deps import get_registry, select_provider
from app.api.validators import json_body
from app.infra import passthrough_client
from app.util.timeutil import timestamp_to_epoch


blueprint = Blueprint("openai_passthrough", __name__, url_prefix="/v1/raw")


@blueprint.get("/models")
def list_models():
    """与 /v1/models 同一份清单：两条通道共用一个模型注册表，这正是统一配置的意义。"""
    providers = get_registry().enabled_providers()
    return jsonify(
        {
            "object": "list",
            "data": [
                {
                    "id": provider.served_model_id,
                    "name": provider.name,
                    "object": "model",
                    "created": timestamp_to_epoch(provider.created_at),
                    "owned_by": "tagent",
                }
                for provider in providers
            ],
        }
    )


@blueprint.post("/chat/completions")
def chat_completions():
    data = json_body()
    provider = select_provider(data.get("model"))

    if not data.get("stream", False):
        status, body, content_type = passthrough_client.complete(data, provider)
        return Response(body, status=status, content_type=content_type)

    # stream_with_context：生成器要在请求上下文里被消费，否则 Flask 的 request 已经没了
    upstream = passthrough_client.stream(data, provider)
    return Response(
        stream_with_context(upstream),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
