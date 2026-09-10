"""Production wiring tests for dynamic-provider exam grading."""

import json
import types

import pytest

from app.service.exam_service import ExamService
from app.service.quiz_service import QuizService
from app.errors.api_errors import AgentAPIError
from app.schema.exam import (
    CHOICE_COUNT_RANGE,
    CLOZE_COUNT_RANGE,
    ESSAY_COUNT_RANGE,
    DraftChoiceQuestion,
    DraftClozeQuestion,
    DraftEssayQuestion,
    GeneratedExamDraft,
    normalize_draft,
    ratio_to_score,
)
from app.errors.exam_errors import InvalidExamRequestError, UpstreamLLMError
from app.repository.exam_cache import ExamCache, LLMGate, StoredExam
from app.schema.provider import ModelProvider


TEST_PROVIDER = ModelProvider(
    name="Test provider",
    served_model_id="test-provider",
    base_url="https://example.invalid/v1",
    upstream_model="test-upstream",
    auth_mode="bearer",
    api_key="test-key",
    temperature=0.1,
    created_at="2026-07-18T00:00:00Z",
    updated_at="2026-07-18T00:00:00Z",
)


def make_exam(exam_id="wiring-exam-1"):
    draft = GeneratedExamDraft(
        cloze=[
            DraftClozeQuestion(
                cue="功率单位",
                text="接收功率约 1 ____",
                accept=["mW"],
                match_mode="exact",
                points=5,
            ),
            DraftClozeQuestion(
                cue="延迟类型",
                text="____ 是分组排队等待造成的",
                accept=["排队延迟"],
                points=5,
            ),
            *[
                DraftClozeQuestion(
                    cue=f"c{i}", text=f"第 {i} 题 ____", accept=[f"答案{i}"], points=5
                )
                for i in range(3, CLOZE_COUNT_RANGE[0] + 1)
            ],
        ],
        choice=[
            DraftChoiceQuestion(
                question=f"选择题{i}",
                options=["甲", "乙", "丙", "丁"],
                correct_index=0,
                points=6,
            )
            for i in range(CHOICE_COUNT_RANGE[0])
        ],
        essay=[
            DraftEssayQuestion(
                question="论述离散事件仿真的核心流程",
                reference_answer="参考答案",
                rubric="要点覆盖",
                points=30,
            ),
            *[
                DraftEssayQuestion(
                    question=f"论述题 {i}",
                    reference_answer="参考答案",
                    rubric="要点覆盖",
                    points=30,
                )
                for i in range(1, ESSAY_COUNT_RANGE[0])
            ],
        ],
    )
    return normalize_draft(draft, exam_id)


class ScriptedGradeLLM:
    """按批作答的假模型。

    判分已按题型分批（见 rag_service._grade_batches），每批的 ID 集合都要精确
    匹配，所以默认只回本批 prompt 里出现的题号——照搬整份 payload 会被
    validate_grade_batch 判为"多余 ID"。verbatim=True 用于故意回错题号的用例。
    """

    def __init__(self, payload, verbatim=False):
        self.payload = payload
        self.verbatim = verbatim
        self.calls = 0
        self.prompts = []

    def bind(self, **_kwargs):
        return self

    async def ainvoke(self, prompt):
        self.calls += 1
        self.last_prompt = prompt
        self.prompts.append(prompt)
        payload = self.payload
        if not self.verbatim:
            payload = {
                **payload,
                "items": [
                    item
                    for item in payload["items"]
                    if f'"{item["question_id"]}"' in prompt
                ],
            }
        return types.SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))


class RejectingFactory:
    def get(self, *_args, **_kwargs):
        raise AssertionError("Local-only grading must not construct an LLM client")


class StaticFactory:
    def __init__(self, client):
        self.client = client

    def get(self, selected, **_kwargs):
        assert selected.served_model_id == TEST_PROVIDER.served_model_id
        return self.client


class FakeKnowledgeBase:
    """判卷路径不碰知识库；retrieve 只为单题判分那条用例提供片段。"""

    def retrieve(self, _query, notebook_ids=None):
        return "教材片段", []

    def sample_exam_context(self, topic=None, notebook_ids=None) -> str:
        return "教材片段"

    def search(self, _query, *, k=3):
        return [types.SimpleNamespace(page_content="教材片段")]


def make_sim(exam, client=None):
    cache = ExamCache()
    cache.put(
        exam.exam_id,
        StoredExam(exam=exam, served_model_id=TEST_PROVIDER.served_model_id),
    )
    return ExamService(
        FakeKnowledgeBase(),
        StaticFactory(client) if client is not None else RejectingFactory(),
        exam_cache=cache,
        llm_gate=LLMGate(max_concurrent=2),
    )


def test_local_only_paths_never_construct_llm():
    exam = make_exam()
    sim = make_sim(exam)
    review = sim.review_exam(
        exam.exam_id,
        {"C1": "MW", "C2": " 排队延迟。", "M1": 0, "M2": 1},
        TEST_PROVIDER,
    )
    by_id = {result.id: result for result in review.results}
    assert by_id["C1"].verdict == "wrong"
    assert by_id["C2"].verdict == "correct"
    assert by_id["M1"].verdict == "correct"
    assert by_id["M2"].verdict == "wrong"
    assert by_id["E1"].verdict == "unanswered"
    assert review.total_score == sum(result.score for result in review.results)


def test_text_mismatch_and_essay_are_graded_in_separate_typed_batches():
    """填空复核与解答题必须分批送评：两套评分尺度不能挤在同一条 prompt 里。"""
    exam = make_exam("wiring-exam-2")
    client = ScriptedGradeLLM(
        {
            "items": [
                {"question_id": "C2", "score_ratio": 0, "feedback": "语义不符"},
                {"question_id": "E1", "score_ratio": 0.5, "feedback": "覆盖部分要点"},
            ],
            "overall_comment": "总体一般",
        }
    )
    review = make_sim(exam, client).review_exam(
        exam.exam_id,
        {"C2": "传播延迟", "E1": "事件调度、时钟推进、状态更新"},
        TEST_PROVIDER,
    )
    assert client.calls == 2  # 一批解答题 + 一批填空复核
    essay_prompts = [p for p in client.prompts if "只判**解答题**" in p]
    cloze_prompts = [p for p in client.prompts if "只判**填空题**" in p]
    assert len(essay_prompts) == 1 and len(cloze_prompts) == 1
    # 每批只看见自己的题号，互不串味
    assert '"E1"' in essay_prompts[0] and '"C2"' not in essay_prompts[0]
    assert '"C2"' in cloze_prompts[0] and '"E1"' not in cloze_prompts[0]

    by_id = {result.id: result for result in review.results}
    assert by_id["C2"].feedback == "语义不符"
    assert by_id["E1"].score == ratio_to_score(0.5, exam.essay[0].points)
    assert review.overall_comment == "总体一般"
    assert "传播延迟" in cloze_prompts[0]


def test_grade_llm_wrong_ids_retry_then_502():
    exam = make_exam("wiring-exam-3")
    client = ScriptedGradeLLM(
        {
            "items": [{"question_id": "E999", "score_ratio": 1, "feedback": "x"}],
            "overall_comment": "",
        },
        verbatim=True,
    )
    with pytest.raises(UpstreamLLMError) as exc_info:
        make_sim(exam, client).review_exam(
            exam.exam_id,
            {"E1": "作答内容"},
            TEST_PROVIDER,
        )
    assert exc_info.value.status_code == 502
    assert client.calls == 2


def test_unknown_or_mistyped_answers_rejected_before_llm():
    exam = make_exam("wiring-exam-4")
    sim = make_sim(exam)
    for answers in ({"Z9": "x"}, {"C1": 123}, {"M1": True}):
        with pytest.raises(InvalidExamRequestError):
            sim.review_exam(exam.exam_id, answers, TEST_PROVIDER)


def test_single_question_plain_text_maps_to_stable_502():
    class PlainTextClient:
        def invoke(self, _messages):
            return types.SimpleNamespace(content="回答正确，100 分")

    sim = QuizService(FakeKnowledgeBase(), StaticFactory(PlainTextClient()))
    with pytest.raises(AgentAPIError) as exc_info:
        sim.review_quiz("什么是系统仿真？", "回答", TEST_PROVIDER)
    assert exc_info.value.status == 502
