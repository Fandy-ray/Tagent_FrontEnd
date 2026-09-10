"""内部通道：Open WebUI 经 localhost 携带临时 provider envelope 调用。

与公开通道的差别只有两点：token 鉴权，以及 provider 来自请求体而非注册表。
业务逻辑一律走 service，校验走 validators，响应组装走 response——
不从任何兄弟 controller import。
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.api.deps import (
    get_chat_service,
    get_exam_service,
    get_quiz_service,
    invalidate_provider,
)
from app.api.openai_view import chat_completion_response
from app.api.response import envelope, quiz_payload, rag_answer_payload
from app.api.security import require_internal_token
from app.api.validators import (
    exam_review_payload,
    exam_topic,
    json_body,
    optional_notebook_ids,
    optional_text,
    required_text,
)
from app.errors.api_errors import AgentAPIError
from app.service.provider_service import parse_ephemeral_provider


blueprint = Blueprint("internal", __name__, url_prefix="/internal")


@blueprint.before_request
def authenticate_internal_request():
    require_internal_token()


def _envelope():
    """拆开 {provider, payload} 信封，返回请求级 provider 与业务负载。"""
    data = json_body()
    try:
        provider = parse_ephemeral_provider(data.get("provider"))
    except ValueError as exc:
        raise AgentAPIError(str(exc), 400, "invalid_provider") from exc
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise AgentAPIError("payload must be an object.", 400, "invalid_payload")
    return provider, payload


@blueprint.post("/v1/chat/completions")
def chat_completions():
    provider, payload = _envelope()
    return chat_completion_response(payload, provider)


@blueprint.post("/rag/query")
def rag_query():
    provider, payload = _envelope()
    question = required_text(payload, "user_question")
    result = get_chat_service().answer(
        [{"role": "user", "content": question}],
        provider,
        notebook_ids=optional_notebook_ids(payload),
    )
    return envelope(rag_answer_payload(question, result), provider)


@blueprint.post("/quiz/generate")
def generate_quiz():
    provider, _payload = _envelope()
    result = get_quiz_service().generate_quiz(provider, notebook_ids=optional_notebook_ids(_payload))
    return envelope(quiz_payload(result), provider)


@blueprint.post("/quiz/review")
def review_quiz():
    provider, payload = _envelope()
    question = required_text(payload, "question")
    user_answer = required_text(payload, "user_answer")
    reference_context = optional_text(payload, "reference_context")
    result = get_quiz_service().review_quiz(question, user_answer, provider, reference_context)
    return envelope(result, provider)


@blueprint.post("/quiz/exam/generate")
def generate_exam():
    provider, payload = _envelope()
    result = get_exam_service().generate_exam(
        exam_topic(payload), provider, notebook_ids=optional_notebook_ids(payload)
    )
    return envelope(result, provider)


@blueprint.post("/quiz/exam/review")
def review_exam():
    provider, payload = _envelope()
    exam_id, answers = exam_review_payload(payload)
    result = get_exam_service().review_exam(exam_id, answers, provider)
    return envelope(result, provider)


@blueprint.post("/cache/invalidate")
def invalidate_cache():
    data = json_body()
    model_id = data.get("model")
    if model_id is not None and not isinstance(model_id, str):
        raise AgentAPIError("model must be a string.", 400, "validation_error")
    invalidate_provider(model_id)
    return jsonify({"status": "ok"})
