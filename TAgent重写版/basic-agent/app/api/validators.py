"""请求参数校验。

controller 之间共用的校验放这里——过去 internal_routes 直接 import
agent_routes 的私有函数来复用，那让两个 controller 互相耦合。
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import request
from werkzeug.exceptions import BadRequest

from app.errors.api_errors import AgentAPIError
from app.errors.exam_errors import InvalidExamRequestError


MAX_MESSAGE_CHARS = 20_000
MAX_TOTAL_MESSAGE_CHARS = 100_000
MAX_MESSAGES = 50
ALLOWED_ROLES = {"system", "user", "assistant", "tool"}

MAX_EXAM_BODY_BYTES = 256 * 1024
MAX_TOPIC_LENGTH = 100
MAX_ANSWER_LENGTH = 5000
# 原始字符上限，比 ESSAY_MAX_CHARS（去空白后的字数）宽松：这里只防着把一兆
# 字符塞进切分器，真正的业务上下限在 service 里按去空白字数判。
MAX_ESSAY_RAW_CHARS = 20000


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AgentAPIError("Request body must be a JSON object.", 400, "invalid_json")
    return data


def validate_messages(value) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise AgentAPIError("messages must be a non-empty array.", 400, "invalid_messages")

    normalized = []
    total_chars = 0
    has_user = False
    for item in value:
        if not isinstance(item, dict):
            raise AgentAPIError("Each message must be an object.", 400, "invalid_messages")
        role = item.get("role")
        content = item.get("content")
        if role not in ALLOWED_ROLES or not isinstance(content, str):
            raise AgentAPIError("Only text messages with a supported role are accepted.", 400, "invalid_messages")
        if len(content) > MAX_MESSAGE_CHARS:
            raise AgentAPIError(
                f"Each message is limited to {MAX_MESSAGE_CHARS} characters.",
                400,
                "message_too_long",
            )
        total_chars += len(content)
        if total_chars > MAX_TOTAL_MESSAGE_CHARS:
            raise AgentAPIError(
                f"Message content is limited to {MAX_TOTAL_MESSAGE_CHARS} characters in total.",
                400,
                "messages_too_long",
            )
        has_user = has_user or role == "user"
        normalized.append({"role": role, "content": content})

    if not has_user:
        raise AgentAPIError("At least one user message is required.", 400, "invalid_messages")
    return normalized[-MAX_MESSAGES:]


def required_text(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AgentAPIError(f"{field} is required.", 400, "validation_error")
    if len(value) > MAX_MESSAGE_CHARS:
        raise AgentAPIError(f"{field} is too long.", 400, "message_too_long")
    return value.strip()


def optional_text(data: dict, field: str, *, max_length: int = MAX_TOTAL_MESSAGE_CHARS) -> str | None:
    value = data.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise AgentAPIError(f"{field} must be a string.", 400, "validation_error")
    if len(value) > max_length:
        raise AgentAPIError(f"{field} is too long.", 400, "message_too_long")
    return value.strip()


# ====================== 整卷接口专用 ======================
# 整卷请求体比聊天大一个量级（答案全文），单独放宽到 256 KiB 并自行校验。


def exam_json_body() -> dict[str, Any]:
    if request.content_length is not None and request.content_length > MAX_EXAM_BODY_BYTES:
        raise AgentAPIError("Request body exceeds the 256 KiB limit.", 413, "request_too_large")
    try:
        data = request.get_json(silent=False)
    except BadRequest as exc:
        raise AgentAPIError("Request body contains malformed JSON.", 400, "invalid_json") from exc
    if not isinstance(data, dict):
        raise InvalidExamRequestError("请求体必须是 JSON 对象")
    return data


def optional_notebook_ids(data: dict[str, Any]) -> list[str] | None:
    value = data.get("notebook_ids")
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise AgentAPIError("notebook_ids must be an array of strings.", 400, "validation_error")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AgentAPIError("notebook_ids must be an array of strings.", 400, "validation_error")
        notebook_id = item.strip()
        if len(notebook_id) > 200:
            raise AgentAPIError("notebook_ids contains an invalid id.", 400, "validation_error")
        if notebook_id in seen:
            continue
        seen.add(notebook_id)
        normalized.append(notebook_id)
        if len(normalized) > 20:
            raise AgentAPIError("notebook_ids is limited to 20 notebooks.", 400, "validation_error")
    return normalized or None


def exam_topic(payload: dict[str, Any]) -> str | None:
    value = payload.get("topic")
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise InvalidExamRequestError("topic 必须是字符串")
    value = value.strip()
    if len(value) > MAX_TOPIC_LENGTH:
        raise InvalidExamRequestError(f"topic 不能超过 {MAX_TOPIC_LENGTH} 字")
    return value or None


def exam_review_payload(payload: dict[str, Any]) -> tuple[str, dict[str, object]]:
    exam_id = payload.get("exam_id")
    if not isinstance(exam_id, str):
        raise InvalidExamRequestError("exam_id 必须是 UUID 字符串")
    try:
        uuid.UUID(exam_id)
    except (ValueError, AttributeError) as exc:
        raise InvalidExamRequestError("exam_id 必须是有效 UUID") from exc

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise InvalidExamRequestError("answers 必须是对象")
    for question_id, answer in answers.items():
        if not isinstance(question_id, str):
            raise InvalidExamRequestError("answers 的键必须是题号字符串")
        if isinstance(answer, str) and len(answer) > MAX_ANSWER_LENGTH:
            raise InvalidExamRequestError(f"{question_id} 的答案不能超过 {MAX_ANSWER_LENGTH} 字")
    return exam_id, answers


def essay_text(payload: dict[str, Any]) -> str:
    """论文正文。长度的**业务**上下限在 service 里判（要按去空白后的字数算），
    这里只挡住明显不合法的类型和离谱长度，免得把一兆字符塞进切分器。"""
    value = payload.get("text")
    if not isinstance(value, str):
        raise InvalidExamRequestError("text 必须是字符串")
    value = value.strip()
    if not value:
        raise InvalidExamRequestError("请先粘贴要批改的正文")
    if len(value) > MAX_ESSAY_RAW_CHARS:
        raise InvalidExamRequestError(f"正文不能超过 {MAX_ESSAY_RAW_CHARS} 个字符")
    return value


def annotate_payload(payload: dict[str, Any]) -> tuple[str, str, str]:
    """整卷大题按需批注：(exam_id, question_id, answer)。

    题干与评分要点**不从请求里取**，而是拿 exam_id + question_id 回缓存查——
    客户端传来的参考答案一律不可信。答案本身是学生自己的文本，由他提供没问题：
    批注不参与算分，分数在 review 那一步就定死了。
    """
    exam_id = payload.get("exam_id")
    if not isinstance(exam_id, str):
        raise InvalidExamRequestError("exam_id 必须是 UUID 字符串")
    try:
        uuid.UUID(exam_id)
    except (ValueError, AttributeError) as exc:
        raise InvalidExamRequestError("exam_id 必须是有效 UUID") from exc

    question_id = payload.get("question_id")
    if not isinstance(question_id, str) or not question_id.strip():
        raise InvalidExamRequestError("question_id 必须是题号字符串")
    if len(question_id) > 40:
        raise InvalidExamRequestError("question_id 不合法")

    answer = payload.get("answer")
    if not isinstance(answer, str):
        raise InvalidExamRequestError("answer 必须是字符串")
    if len(answer) > MAX_ANSWER_LENGTH:
        raise InvalidExamRequestError(f"答案不能超过 {MAX_ANSWER_LENGTH} 字")
    return exam_id, question_id.strip(), answer.strip()
