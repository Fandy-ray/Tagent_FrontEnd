"""论文批改 schema：标注校验、区间挂载、本地快筛、计分。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schema.essay import (
    DIMENSION_WEIGHTS,
    Annotation,
    LLMAnnotation,
    LLMAnnotationBatch,
    LLMDimension,
    LLMEssayTopic,
    attach_spans,
    build_dimension,
    numbered_text,
    quick_scan,
    validate_annotations,
    weighted_score,
)
from app.util.text import split_sentences


SOURCE = "排队论研究随机服务。它的核心是到达率。\n模型假设很强。结论未必成立。"
SENTENCES = split_sentences(SOURCE)
KNOWN = {s.id for s in SENTENCES}


def batch(*pairs) -> LLMAnnotationBatch:
    return LLMAnnotationBatch(
        items=[LLMAnnotation(sentence_id=sid, kind=kind, comment="评语") for sid, kind in pairs]
    )


# ====================== 标注校验 ======================


def test_accepts_a_subset_of_sentences():
    # 和判分不同：标注是从全文里挑几句，不要求覆盖每一句
    validate_annotations(batch(("P1S1", "issue")), KNOWN)


def test_accepts_an_empty_batch():
    # 一篇没毛病的作文就该零标注，这不是错误
    validate_annotations(LLMAnnotationBatch(), KNOWN)


def test_rejects_unknown_sentence_id():
    # 模型编了个不存在的编号，高亮就会查表失败——必须在这一层挡掉
    with pytest.raises(ValueError, match="不存在的句子"):
        validate_annotations(batch(("P9S9", "issue")), KNOWN)


def test_rejects_duplicate_sentence():
    with pytest.raises(ValueError, match="标注了多次"):
        validate_annotations(batch(("P1S1", "issue"), ("P1S1", "praise")), KNOWN)


def test_rejects_more_issues_than_the_quota():
    over = batch(("P1S1", "issue"), ("P1S2", "issue"), ("P2S1", "issue"), ("P2S2", "issue"))
    with pytest.raises(ValueError, match="超过定额"):
        validate_annotations(over, KNOWN, max_issues=3)


def test_rejects_more_praises_than_the_quota():
    over = batch(("P1S1", "praise"), ("P1S2", "praise"), ("P2S1", "praise"))
    with pytest.raises(ValueError, match="超过定额"):
        validate_annotations(over, KNOWN, max_praises=2)


def test_quotas_are_counted_per_kind_not_in_total():
    # 3 问题 + 2 亮点 = 5 条，各自都在定额内，不该因为总数 5 就被拒
    ok = batch(
        ("P1S1", "issue"), ("P1S2", "issue"), ("P2S1", "issue"),
        ("P2S2", "praise"),
    )
    validate_annotations(ok, KNOWN, max_issues=3, max_praises=2)


def test_llm_output_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        LLMAnnotation(sentence_id="P1S1", kind="issue", comment="x", severity="high")


def test_llm_output_rejects_bad_kind():
    with pytest.raises(ValidationError):
        LLMAnnotation(sentence_id="P1S1", kind="warning", comment="x")


# ====================== 区间挂载 ======================


def test_attach_spans_slices_back_to_the_original():
    annotations = attach_spans(batch(("P1S2", "issue"), ("P2S1", "praise")), SENTENCES)
    assert len(annotations) == 2
    for a in annotations:
        assert SOURCE[a.start : a.end] == a.text


def test_attach_spans_sorts_by_position_not_by_model_order():
    # 模型先说 P2S1 再说 P1S1，渲染必须按原文顺序，否则相邻高亮边界会算错
    annotations = attach_spans(batch(("P2S1", "issue"), ("P1S1", "praise")), SENTENCES)
    assert [a.sentence_id for a in annotations] == ["P1S1", "P2S1"]
    assert annotations[0].start < annotations[1].start


def test_attach_spans_drops_ids_it_cannot_place():
    # 正常路径上 validate_annotations 已经挡掉了，这里是最后一道防线：
    # 宁可少一条批注，也不能让前端拿到一个没法定位的区间
    annotations = attach_spans(batch(("P9S9", "issue")), SENTENCES)
    assert annotations == []


def test_annotation_rejects_negative_span():
    with pytest.raises(ValidationError):
        Annotation(sentence_id="P1S1", kind="issue", comment="x", start=-1, end=3, text="a")


# ====================== 本地快筛 ======================


def test_quick_scan_counts_without_whitespace():
    source = "一句 话。\n\n另一段。"
    scan = quick_scan(source, split_sentences(source))
    assert scan.characters == len("一句话。另一段。")
    assert scan.paragraphs == 2
    assert scan.sentences == 2


def test_quick_scan_flags_duplicate_sentences():
    source = "结论成立。中间一句。结论成立。"
    scan = quick_scan(source, split_sentences(source))
    assert scan.duplicate_sentence_ids == ["P1S3"], "第二次出现才算重复，第一次不算"


def test_quick_scan_ignores_whitespace_when_comparing_duplicates():
    source = "结论 成立。结论成立。"
    scan = quick_scan(source, split_sentences(source))
    assert len(scan.duplicate_sentence_ids) == 1


@pytest.mark.parametrize(
    "source",
    ["见《系统仿真导论》。", "如前所述（参见第三章）。", "已有研究表明[12]。"],
)
def test_quick_scan_detects_citations(source):
    assert quick_scan(source, split_sentences(source)).cites_material


def test_quick_scan_reports_no_citation_when_absent():
    source = "我认为排队论很重要。它应用广泛。"
    assert not quick_scan(source, split_sentences(source)).cites_material


def test_quick_scan_counts_empty_paragraphs():
    source = "第一段。\n\n\n第二段。"
    assert quick_scan(source, split_sentences(source)).empty_paragraphs == 2


def test_quick_scan_handles_blank_input():
    scan = quick_scan("", [])
    assert scan.characters == 0 and scan.sentences == 0


# ====================== 计分 ======================


def test_score_ratio_is_hits_over_total():
    d = LLMDimension(hits=["a", "b", "c"], misses=["d"])
    assert d.score_ratio == 0.75


def test_score_ratio_of_an_empty_rubric_is_zero_not_a_crash():
    assert LLMDimension().score_ratio == 0.0


def test_weighted_score_of_a_perfect_paper_is_full_marks():
    dims = [build_dimension(n, LLMDimension(hits=["a"])) for n in DIMENSION_WEIGHTS]
    assert weighted_score(dims) == 100


def test_weighted_score_of_an_empty_paper_is_zero():
    dims = [build_dimension(n, LLMDimension(misses=["a"])) for n in DIMENSION_WEIGHTS]
    assert weighted_score(dims) == 0


def test_weighted_score_respects_the_weights():
    # 只有 content(0.4) 满分，其余为 0 → 40
    dims = [
        build_dimension("content", LLMDimension(hits=["a"])),
        build_dimension("argument", LLMDimension(misses=["a"])),
        build_dimension("language", LLMDimension(misses=["a"])),
    ]
    assert weighted_score(dims) == 40


def test_weighted_score_rejects_weights_that_do_not_sum_to_one():
    # 少一个维度就悄悄按 0.75 的总权重算分，学生会莫名其妙被扣分
    dims = [build_dimension("content", LLMDimension(hits=["a"]))]
    with pytest.raises(ValueError, match="必须为 1.0"):
        weighted_score(dims)


def test_declared_weights_sum_to_one():
    assert sum(DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)


# ====================== 带编号的正文 ======================


def test_numbered_text_prefixes_every_sentence():
    rendered = numbered_text(SENTENCES)
    assert rendered.splitlines()[0].startswith("P1S1 ")
    assert len(rendered.splitlines()) == len(SENTENCES)


def test_numbered_text_can_narrow_to_flagged_paragraphs():
    # 下钻时只铺被点名的段，省的就是这一轮的输入长度
    rendered = numbered_text(SENTENCES, only_paragraphs={2})
    assert all(line.startswith("P2") for line in rendered.splitlines())
    assert rendered.splitlines()


# ====================== 评分要点必须对得上 ======================


def full(dimension: str) -> LLMDimension:
    from app.schema.essay import RUBRIC_POINTS

    return LLMDimension(hits=list(RUBRIC_POINTS[dimension]))


def test_accepts_a_complete_rubric():
    from app.schema.essay import RUBRIC_POINTS, validate_dimension

    points = RUBRIC_POINTS["content"]
    validate_dimension(LLMDimension(hits=list(points[:2]), misses=list(points[2:])), "content")


def test_rejects_a_dropped_rubric_point():
    # 漏一条，分母从 4 变 3，学生凭空多得分
    from app.schema.essay import RUBRIC_POINTS, validate_dimension

    points = RUBRIC_POINTS["content"]
    with pytest.raises(ValueError, match="漏了"):
        validate_dimension(LLMDimension(hits=list(points[:3])), "content")


def test_rejects_an_invented_rubric_point():
    from app.schema.essay import RUBRIC_POINTS, validate_dimension

    points = RUBRIC_POINTS["language"]
    with pytest.raises(ValueError, match="多了"):
        validate_dimension(LLMDimension(hits=list(points) + ["我自己想的要点"]), "language")


def test_rejects_a_duplicated_rubric_point():
    # 重复报会让分母变大，学生平白被扣分
    from app.schema.essay import RUBRIC_POINTS, validate_dimension

    points = RUBRIC_POINTS["argument"]
    dup = LLMDimension(hits=[points[0], points[0]], misses=list(points[1:]))
    with pytest.raises(ValueError, match="重复"):
        validate_dimension(dup, "argument")


@pytest.mark.parametrize("dimension", ["content", "argument", "language"])
def test_every_dimension_has_a_validatable_full_rubric(dimension):
    from app.schema.essay import validate_dimension

    validate_dimension(full(dimension), dimension)
    assert full(dimension).score_ratio == 1.0


# ====================== 要点编号（模型照抄 prompt 里的序号） ======================


def test_accepts_rubric_points_copied_with_their_numbers():
    """prompt 里的要点是「1. …」编号列出来的，模型照抄时会连编号一起抄回来。

    编号不是要点正文的一部分，得在入口剥掉；否则精确集合比对每次都判不过，
    两次重试之后整篇批改报 502。带真实知识库上下文时 DeepSeek 稳定复现。
    """
    from app.schema.essay import RUBRIC_POINTS, validate_dimension

    points = RUBRIC_POINTS["argument"]
    numbered = LLMDimension(
        hits=[f"1. {points[0]}", f"2、{points[1]}"],
        misses=[f"（3）{points[2]}", f"4) {points[3]}"],
    )

    validate_dimension(numbered, "argument")
    assert numbered.hits == list(points[:2])
    assert numbered.score_ratio == 0.5


@pytest.mark.parametrize("prefix", ["1. ", "1．", "2、", "（3）", "(4) ", "三、", "5: "])
def test_strips_every_common_list_marker(prefix):
    from app.schema.essay import RUBRIC_POINTS, validate_dimension

    points = RUBRIC_POINTS["language"]
    marked = LLMDimension(hits=[f"{prefix}{points[0]}"], misses=list(points[1:]))

    validate_dimension(marked, "language")
    assert marked.hits == [points[0]]


def test_stripping_numbers_does_not_loosen_the_comparison():
    # 剥编号只针对编号：换个说法抄回来仍然要判不过，不然分母又开始飘
    from app.schema.essay import RUBRIC_POINTS, validate_dimension

    points = RUBRIC_POINTS["content"]
    paraphrased = LLMDimension(hits=[f"1. {points[0]}改了几个字"], misses=list(points[1:]))

    with pytest.raises(ValueError, match="对不上"):
        validate_dimension(paraphrased, "content")


# ====================== 出题 ======================


def topic(**overrides) -> LLMEssayTopic:
    payload = {
        "title": "排队论视角下的银行窗口配置",
        "requirements": ["用 M/M/c 模型估算平均等待时间", "写明到达与服务的假设"],
        "suggested_chars": 1200,
    }
    payload.update(overrides)
    return LLMEssayTopic(**payload)


def test_topic_accepts_a_well_formed_answer():
    assert topic().requirements == ["用 M/M/c 模型估算平均等待时间", "写明到达与服务的假设"]


def test_topic_rejects_unknown_fields():
    # 让模型顺手给参考答案是常事，那不是这个接口该下发的东西
    with pytest.raises(ValidationError):
        topic(reference_answer="……")


@pytest.mark.parametrize("requirements", [["只有一条要求"], ["一", "二", "三", "四", "五"]])
def test_topic_requires_two_to_four_requirements(requirements):
    with pytest.raises(ValidationError):
        topic(requirements=requirements)


def test_topic_rejects_a_too_short_title():
    with pytest.raises(ValidationError):
        topic(title="排队")


def test_topic_strips_numbering_from_requirements():
    result = topic(requirements=["1. 用 M/M/c 模型估算平均等待时间", "2、写明到达与服务的假设"])
    assert result.requirements == ["用 M/M/c 模型估算平均等待时间", "写明到达与服务的假设"]


def test_topic_rejects_a_requirement_that_is_only_a_number():
    with pytest.raises(ValidationError):
        topic(requirements=["1. ", "写明到达与服务的假设"])

