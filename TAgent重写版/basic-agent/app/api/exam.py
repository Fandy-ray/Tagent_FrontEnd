"""整卷生成与判卷的公开通道。"""

from __future__ import annotations

from flask import Blueprint

from app.api.deps import get_exam_service, select_provider
from app.api.response import envelope
from app.api.validators import exam_json_body, exam_review_payload, exam_topic, optional_notebook_ids
from app.errors.api_errors import ModelNotFoundError
from app.errors.exam_errors import ExamGoneError


blueprint = Blueprint("exam", __name__)


@blueprint.post("/quiz/exam/generate")
def generate_exam():
    payload = exam_json_body()
    provider = select_provider(payload.get("model"))
    result = get_exam_service().generate_exam(
        exam_topic(payload), provider, notebook_ids=optional_notebook_ids(payload)
    )
    return envelope(result, provider)


@blueprint.post("/quiz/exam/review")
def review_exam():
    payload = exam_json_body()
    try:
        provider = select_provider(payload.get("model"))
    except ModelNotFoundError as exc:
        # 判卷模型必须与出卷模型一致；模型已下线时试卷等同失效。
        raise ExamGoneError("出卷模型已不可用，请重新生成试卷") from exc
    exam_id, answers = exam_review_payload(payload)
    result = get_exam_service().review_exam(exam_id, answers, provider)
    return envelope(result, provider)
