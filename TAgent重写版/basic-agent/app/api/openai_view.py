"""OpenAI 兼容线格式的响应组装（含 SSE 流）。

放在 api 层而不是 service：这里做的全是"把 service 的返回值摆成 OpenAI 的样子"，
是表示层的事。/v1/chat/completions 与 /internal/v1/chat/completions 共用本模块，
两个 controller 因此不必互相 import。

注意 stream_with_context 必须留在本层：service 只返回裸生成器，
一旦生成器跨出请求上下文再被消费，Flask 的 request 就没了。
"""

from __future__ import annotations

import json
import time
import uuid

from flask import Response, jsonify, stream_with_context

from app.api.deps import get_chat_service
from app.api.validators import optional_notebook_ids, validate_messages


def _chunk(
    chat_id: str,
    created: int,
    model: str,
    content: str | None,
    finish_reason=None,
    *,
    role: str | None = None,
):
    if role is not None:
        delta = {"role": role}
    else:
        delta = {} if content is None else {"content": content}
    return {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def chat_completion_response(data, provider):
    messages = validate_messages(data.get("messages"))
    notebook_ids = optional_notebook_ids(data)
    service = get_chat_service()
    chat_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    if not data.get("stream", False):
        result = service.answer(messages, provider, notebook_ids=notebook_ids)
        return jsonify(
            {
                "id": chat_id,
                "object": "chat.completion",
                "created": created,
                "model": provider.served_model_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": result["content"]},
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
            }
        )

    def generate():
        iterator = iter(service.stream_answer(messages, provider, notebook_ids=notebook_ids))
        finish_reason = "stop"
        try:
            role_chunk = _chunk(
                chat_id,
                created,
                provider.served_model_id,
                None,
                role="assistant",
            )
            yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"
            for item in iterator:
                if isinstance(item, tuple) and len(item) == 2:
                    token, item_finish_reason = item
                else:
                    token, item_finish_reason = item, None
                if item_finish_reason:
                    finish_reason = item_finish_reason
                if token:
                    payload = _chunk(
                        chat_id,
                        created,
                        provider.served_model_id,
                        str(token),
                    )
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            raise
        except Exception:
            payload = _chunk(
                chat_id,
                created,
                provider.served_model_id,
                "The selected provider stream ended unexpectedly.",
            )
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            close = getattr(iterator, "close", None)
            if callable(close):
                close()
        final_chunk = _chunk(
            chat_id,
            created,
            provider.served_model_id,
            None,
            finish_reason,
        )
        yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
