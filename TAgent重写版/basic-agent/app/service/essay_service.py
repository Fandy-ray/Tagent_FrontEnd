"""小论文批改与逐句批注。

两个入口，共用一套核心：

- review_paper()      答疑里的论文辅助：三维并发打分 + 条件下钻出高亮
- annotate_answer()   整卷大题的逐句批注：按需单独发一轮

「渐进式披露」在这里是两层意思：
1. **输出**上——不是每句都评，而是定额挑最值得说的几处；
2. **调用**上——没被点名的段落不下钻，整卷大题不点开就一轮都不花。

第 2 层才是省钱的大头：本项目自己的压测结论是单次调用的输出 token 量与上下文
长度才是主要耗时来源（见 app/config.py），所以不发的那一轮省得最彻底。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from app.config import (
    ANNOTATE_LLM_BUDGET,
    ANNOTATE_LLM_TIMEOUT,
    ANNOTATE_MIN_ANSWER_CHARS,
    ANNOTATE_MIN_ATTEMPT_TIMEOUT,
    ESSAY_CONTEXT_CHAR_LIMIT,
    ESSAY_LLM_BUDGET,
    ESSAY_LLM_TIMEOUT,
    ESSAY_MAX_CHARS,
    ESSAY_MAX_FLAGGED_PARAGRAPHS,
    ESSAY_MIN_ATTEMPT_TIMEOUT,
    ESSAY_MIN_CHARS,
)
from app.errors.exam_errors import InvalidExamRequestError, UpstreamLLMError
from app.infra.llm_json import call_json_llm
from app.prompts.essay_prompts import (
    build_annotation_prompt,
    build_dimension_prompt,
    build_essay_answer_annotation_prompt,
    dimension_order,
)
from app.schema.essay import (
    MAX_ISSUES,
    MAX_PRAISES,
    Annotation,
    LLMAnnotationBatch,
    LLMDimension,
    PaperReview,
    attach_spans,
    build_dimension,
    numbered_text,
    quick_scan,
    validate_annotations,
    validate_dimension,
    weighted_score,
)
from app.schema.provider import ModelProvider
from app.util.text import split_sentences


# 需要参考材料的维度。language 只看文字本身，给它材料纯属浪费 token 和时间。
_NEEDS_CONTEXT = {"content", "argument"}
# 只有论证维度顺带报可疑段落——它本来就要通读全文，这一步是白捡的，
# 不必单独跑一轮「找可疑段落」。
_REPORTS_FLAGS = "argument"


class EssayService:
    def __init__(self, *, knowledge_base, client_factory, llm_gate):
        self.knowledge_base = knowledge_base
        self.client_factory = client_factory
        self.llm_gate = llm_gate

    # ====================== 论文辅助 ======================
    def review_paper(
        self,
        text: str,
        topic: str | None,
        provider: ModelProvider,
        notebook_ids: list[str] | None = None,
    ) -> PaperReview:
        source = (text or "").strip()
        sentences = split_sentences(source)
        scan = quick_scan(source, sentences)

        if scan.characters < ESSAY_MIN_CHARS:
            raise InvalidExamRequestError(
                f"正文只有 {scan.characters} 字，太短了，先写到 {ESSAY_MIN_CHARS} 字以上再来批"
            )
        if scan.characters > ESSAY_MAX_CHARS:
            raise InvalidExamRequestError(
                f"正文 {scan.characters} 字，超过了单次批改上限 {ESSAY_MAX_CHARS} 字，"
                "请分段提交"
            )

        numbered = numbered_text(sentences)
        started = time.monotonic()
        deadline = started + ESSAY_LLM_BUDGET

        with self.llm_gate.acquire():
            context = self._context_for(topic, source, notebook_ids)

            budget = max(0.0, deadline - time.monotonic())
            # 与 generate_exam / generate_flash_deck 同一套余量算法：call_json_llm
            # 在 remaining < attempt_timeout + 5 时直接判预算不足抛 504，
            # 这里的 -15 就是留给它的余量，别减小。
            attempt_timeout = min(
                ESSAY_LLM_TIMEOUT, max(ESSAY_MIN_ATTEMPT_TIMEOUT, budget - 15.0)
            )

            def run_dimension(dimension: str) -> tuple[str, LLMDimension]:
                prompt = build_dimension_prompt(
                    dimension,
                    numbered,
                    topic=topic,
                    context=context if dimension in _NEEDS_CONTEXT else "",
                    want_flags=(dimension == _REPORTS_FLAGS),
                )
                client = self.client_factory.get(
                    provider, timeout_seconds=int(attempt_timeout), max_retries=0
                ).bind(max_tokens=900)
                result = call_json_llm(
                    client,
                    prompt,
                    LLMDimension,
                    attempt_timeout=attempt_timeout,
                    budget_seconds=budget,
                    # **必须**走 post_validate，不能拿到结果之后在外面校验：
                    # 模型把要点换个说法抄回来是常事，那是该重试的情形。
                    # 放在圈外校验，一次不合格就直接 500 了（实测踩过）。
                    post_validate=lambda value, d=dimension: validate_dimension(value, d),
                )
                return dimension, result

            names = list(dimension_order())
            with ThreadPoolExecutor(max_workers=len(names)) as pool:
                graded = dict(pool.map(run_dimension, names))

            annotations = self._drill_down(
                graded[_REPORTS_FLAGS].flagged_paragraphs,
                sentences,
                provider,
                deadline,
            )

        dimensions = [build_dimension(name, graded[name]) for name in names]
        return PaperReview(
            word_count=scan.characters,
            quick_scan=scan,
            dimensions=dimensions,
            annotations=annotations,
            score=weighted_score(dimensions),
            overall_comment=graded["content"].comment,
        )

    def _context_for(self, topic: str | None, source: str, notebook_ids) -> str:
        """按题目（没题目就按正文开头）检索材料，用来判「是否用上课程内容」。

        检索失败不该让整次批改失败——语言维度根本不需要材料，另两维没材料也
        还能评，只是「用上课程概念」那条判得保守些。
        """
        query = (topic or "").strip() or source[:120]
        try:
            documents = self.knowledge_base.search(query, k=3, notebook_ids=notebook_ids)
        except Exception:
            return ""
        pieces = [d.page_content[:600] for d in documents]
        joined = "\n\n---\n\n".join(pieces)
        return joined[:ESSAY_CONTEXT_CHAR_LIMIT]

    def _drill_down(
        self,
        flagged: list[int],
        sentences,
        provider: ModelProvider,
        deadline: float,
    ) -> list[Annotation]:
        """条件触发的第四轮：没被点名就一轮都不发。"""
        paragraphs = {p for p in flagged if p > 0}
        if not paragraphs or not sentences:
            return []
        # 点名太多就只取靠前的几段，否则「只看可疑段落」这句话就没意义了
        paragraphs = set(sorted(paragraphs)[:ESSAY_MAX_FLAGGED_PARAGRAPHS])

        focused = [s for s in sentences if s.paragraph in paragraphs]
        if not focused:
            return []

        budget = max(0.0, deadline - time.monotonic())
        attempt_timeout = min(
            ESSAY_LLM_TIMEOUT, max(ESSAY_MIN_ATTEMPT_TIMEOUT, budget - 15.0)
        )
        prompt = build_annotation_prompt(
            numbered_text(focused),
            focus="这几段是通读后觉得问题最集中的部分。",
            max_issues=MAX_ISSUES,
            max_praises=MAX_PRAISES,
        )
        return self._annotate(
            prompt, focused, provider, attempt_timeout, budget, MAX_ISSUES, MAX_PRAISES
        )

    # ====================== 整卷大题的逐句批注 ======================
    def annotate_answer(
        self,
        answer: str,
        question: str,
        rubric: str,
        provider: ModelProvider,
        *,
        max_issues: int = 2,
        max_praises: int = 1,
    ) -> list[Annotation]:
        """给一道大题的作答做逐句批注。

        **不进判卷流程**，由前端在学生点开某道题时单独调。判卷本身已经要等
        一轮模型，再给每道大题各发一轮会让等待翻倍；而绝大多数学生只会细看
        自己答得差的那一两道。不点开就一轮都不花。
        """
        source = (answer or "").strip()
        sentences = split_sentences(source)
        scan = quick_scan(source, sentences)
        if scan.characters < ANNOTATE_MIN_ANSWER_CHARS:
            # 太短的答案逐句批注没有意义：整段就一两句，判分的评语已经说清了
            return []

        started = time.monotonic()
        budget = ANNOTATE_LLM_BUDGET
        attempt_timeout = min(
            ANNOTATE_LLM_TIMEOUT, max(ANNOTATE_MIN_ATTEMPT_TIMEOUT, budget - 15.0)
        )
        prompt = build_essay_answer_annotation_prompt(
            numbered_text(sentences),
            question,
            rubric,
            max_issues=max_issues,
            max_praises=max_praises,
        )
        with self.llm_gate.acquire():
            return self._annotate(
                prompt,
                sentences,
                provider,
                attempt_timeout,
                max(0.0, budget - (time.monotonic() - started)),
                max_issues,
                max_praises,
            )

    # ====================== 共用 ======================
    def _annotate(
        self,
        prompt: str,
        sentences,
        provider: ModelProvider,
        attempt_timeout: float,
        budget: float,
        max_issues: int,
        max_praises: int,
    ) -> list[Annotation]:
        client = self.client_factory.get(
            provider, timeout_seconds=int(attempt_timeout), max_retries=0
        ).bind(max_tokens=200 + 160 * (max_issues + max_praises))
        try:
            known = {s.id for s in sentences}
            batch = call_json_llm(
                client,
                prompt,
                LLMAnnotationBatch,
                attempt_timeout=attempt_timeout,
                budget_seconds=budget,
                # 同上：编错句号、超定额都该重试一次，而不是抛给用户
                post_validate=lambda value: validate_annotations(
                    value, known, max_issues=max_issues, max_praises=max_praises
                ),
            )
        except UpstreamLLMError:
            # 批注是锦上添花：分数和维度评语已经拿到了，没必要因为多标几句
            # 失败就把整次批改判失败。少几条下划线，比一片红字好。
            return []
        return attach_spans(batch, sentences)
