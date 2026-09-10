"""响应体组装。

公开通道（/rag/query）与内部通道（/internal/rag/query）返回的结构完全一致，
过去这段组装在两个 controller 里各写了一遍——放在这里让两边共用，
而不是让一个 controller 去 import 另一个。
"""

from __future__ import annotations

import uuid

from flask import jsonify


def public_value(value):
    """pydantic 模型取其公开投影；普通对象原样返回。"""
    return value.model_dump() if hasattr(value, "model_dump") else value


def envelope(data, provider, *, code: int = 200, msg: str = "success"):
    """业务接口的统一信封：{code, msg, data, model}。"""
    return jsonify(
        {
            "code": code,
            "msg": msg,
            "data": public_value(data),
            "model": provider.served_model_id,
        }
    )


def rag_answer_payload(question: str, result: dict) -> dict:
    return {
        "user_question": question,
        "final_answer": result["content"],
        "step_log": result.get("step_log", []),
        "retrieved_context": result.get("retrieved_context", ""),
    }


def quiz_payload(result: dict) -> dict:
    return {"id": str(uuid.uuid4()), **result}
