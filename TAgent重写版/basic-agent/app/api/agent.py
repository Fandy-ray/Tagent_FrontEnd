"""RAG 问答与单题测评的公开通道。"""

from __future__ import annotations

import time

from flask import Blueprint

from app.api.deps import get_chat_service, get_quiz_service, select_provider
from app.api.learner import current_learner, note_chat
from app.api.response import envelope, quiz_payload, rag_answer_payload
from app.api.validators import json_body, optional_notebook_ids, optional_text, required_text


blueprint = Blueprint("agent", __name__)


@blueprint.post("/rag/query")
def rag_query():
    data = json_body()
    question = required_text(data, "user_question")
    provider = select_provider(data.get("model"))
    messages = [{"role": "user", "content": question}]
    notebook_ids = optional_notebook_ids(data)
    started_at = time.monotonic()
    result = get_chat_service().answer(messages, provider, notebook_ids=notebook_ids)
    note_chat(
        current_learner(),
        provider,
        mode="qa",
        messages=messages,
        answer=result["content"],
        finish_reason="stop",
        notebook_ids=notebook_ids,
        started_at=started_at,
    )
    return envelope(rag_answer_payload(question, result), provider)


@blueprint.post("/quiz/generate")
def generate_quiz():
    data = json_body()
    provider = select_provider(data.get("model"))
    result = get_quiz_service().generate_quiz(provider, notebook_ids=optional_notebook_ids(data))
    return envelope(quiz_payload(result), provider)


@blueprint.post("/quiz/review")
def review_quiz():
    data = json_body()
    question = required_text(data, "question")
    user_answer = required_text(data, "user_answer")
    reference_context = optional_text(data, "reference_context")
    provider = select_provider(data.get("model"))
    result = get_quiz_service().review_quiz(question, user_answer, provider, reference_context)
    return envelope(result, provider)
