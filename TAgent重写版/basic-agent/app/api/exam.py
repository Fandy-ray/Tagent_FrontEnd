"""整卷生成与判卷、闪卡生成的公开通道。"""

from __future__ import annotations

from flask import Blueprint

from app.api.deps import get_essay_service, get_exam_service, select_provider
from app.api.learner import (
    current_learner,
    note_essay_review,
    note_exam_generated,
    note_exam_reviewed,
)
from app.api.response import envelope
from app.api.validators import (
    annotate_payload,
    essay_text,
    exam_json_body,
    exam_review_payload,
    exam_topic,
    optional_notebook_ids,
)
from app.config import IDEMPOTENT_REPLAY_SECONDS
from app.errors.api_errors import ModelNotFoundError
from app.errors.exam_errors import ExamGoneError
from app.util.singleflight import SingleFlight, fingerprint


blueprint = Blueprint("exam", __name__)

# 同样内容的请求只算一次（为什么见 app/util/singleflight.py）。
# 出卷、出卡、出题只合并「正在跑的」：学生主动点「再来一套」「重新出题」要的是新的。
# 判卷、批改、批注再加短时重放：刷新后重交拿到的就是刚才那份，不会一刷新分数就变。
#
# 往学习记录库里记的那一笔都写在**领头那次的闭包里**：合并进来的、重放的请求不再跑闭包，
# 所以同一次批改只记一条，不会因为学生连点或刷新重交记出好几条一样的。
_flights = SingleFlight()


def _once(route: str, provider, fields: dict, run, *, replay: bool):
    key = fingerprint(route, provider.served_model_id, fields)
    return _flights.do(key, run, replay_seconds=IDEMPOTENT_REPLAY_SECONDS if replay else 0.0)


@blueprint.post("/quiz/exam/generate")
def generate_exam():
    payload = exam_json_body()
    provider = select_provider(payload.get("model"))
    topic, notebook_ids = exam_topic(payload), optional_notebook_ids(payload)
    learner = current_learner()

    def run():
        exam = get_exam_service().generate_exam(topic, provider, notebook_ids=notebook_ids)
        note_exam_generated(learner, provider, topic=topic, exam=exam)
        return exam

    result = _once(
        "exam/generate",
        provider,
        {"topic": topic, "notebooks": sorted(notebook_ids or [])},
        run,
        replay=False,
    )
    return envelope(result, provider)


@blueprint.post("/quiz/flash/generate")
def generate_flash():
    """闪卡：只出能本地判定的题型（填空 + 选择）、不计分、判定在前端做，所以没有配套的 review 接口。"""
    payload = exam_json_body()
    provider = select_provider(payload.get("model"))
    topic, notebook_ids = exam_topic(payload), optional_notebook_ids(payload)
    result = _once(
        "flash/generate",
        provider,
        {"topic": topic, "notebooks": sorted(notebook_ids or [])},
        lambda: get_exam_service().generate_flash_deck(topic, provider, notebook_ids=notebook_ids),
        replay=False,
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
    learner = current_learner()

    def run():
        review = get_exam_service().review_exam(exam_id, answers, provider)
        note_exam_reviewed(learner, provider, exam_id=exam_id, answers=answers, review=review)
        return review

    result = _once(
        "exam/review",
        provider,
        {"exam_id": exam_id, "answers": answers},
        run,
        replay=True,
    )
    return envelope(result, provider)


@blueprint.post("/quiz/exam/annotate")
def annotate_essay_answer():
    """整卷大题的逐句批注 —— **按需**，不进判卷流程。

    判卷本身已经要等一轮模型；再给每道大题各发一轮，等待就翻倍了。而绝大多数
    学生只会细看自己答得差的那一两道，所以改成点开哪道才批哪道，不点就不花。
    这是「渐进式披露」管到调用层：省得最彻底的那一轮是根本没发出去的那轮。
    """
    payload = exam_json_body()
    provider = select_provider(payload.get("model"))
    exam_id, question_id, answer = annotate_payload(payload)

    def run():
        question, rubric = get_exam_service().essay_question_for_annotation(
            exam_id, question_id, provider
        )
        return get_essay_service().annotate_answer(answer, question, rubric, provider)

    annotations = _once(
        "exam/annotate",
        provider,
        {"exam_id": exam_id, "question_id": question_id, "answer": answer},
        run,
        replay=True,
    )
    # envelope 只对**顶层**值调 model_dump，dict 里裹着的 pydantic 对象它看不见，
    # 直接交给 jsonify 会 TypeError。所以这里自己摊平。
    return envelope(
        {
            "question_id": question_id,
            "annotations": [item.model_dump() for item in annotations],
        },
        provider,
    )


@blueprint.post("/essay/review")
def review_essay():
    """论文辅助：三维并发打分 + 条件下钻出高亮。"""
    payload = exam_json_body()
    provider = select_provider(payload.get("model"))
    text, topic, notebook_ids = essay_text(payload), exam_topic(payload), optional_notebook_ids(payload)
    learner = current_learner()

    def run():
        review = get_essay_service().review_paper(text, topic, provider, notebook_ids=notebook_ids)
        note_essay_review(learner, provider, topic=topic, text=text, review=review)
        return review

    result = _once(
        "essay/review",
        provider,
        {"text": text, "topic": topic, "notebooks": sorted(notebook_ids or [])},
        run,
        replay=True,
    )
    return envelope(result, provider)


@blueprint.post("/essay/topic")
def propose_essay_topic():
    """答疑论文模式的「出题」：按笔记本材料出一道小论文题。

    topic 字段是学生给的选题方向（可选，≤100 字，与出卷接口同一个校验）。
    """
    payload = exam_json_body()
    provider = select_provider(payload.get("model"))
    hint, notebook_ids = exam_topic(payload), optional_notebook_ids(payload)
    result = _once(
        "essay/topic",
        provider,
        {"hint": hint, "notebooks": sorted(notebook_ids or [])},
        lambda: get_essay_service().propose_topic(hint, provider, notebook_ids=notebook_ids),
        replay=False,
    )
    return envelope(result, provider)
