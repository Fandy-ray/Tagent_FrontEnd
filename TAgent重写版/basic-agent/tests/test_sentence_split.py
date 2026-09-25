"""句子切分与原文区间。

这些用例守的是一条恒等式：source[start:end] == text。
高亮全靠它——它一旦破了，学生看到的下划线就会画在别的句子上。
"""

from __future__ import annotations

import pytest

from app.util.text import Sentence, split_sentences


def ids(source: str) -> list[str]:
    return [s.id for s in split_sentences(source)]


def texts(source: str) -> list[str]:
    return [s.text for s in split_sentences(source)]


# ====================== 恒等式：区间必须能切回原文 ======================

SAMPLES = [
    "系统仿真是一种方法。它用模型代替实物。",
    "他问：“这真的成立吗？”然后翻开了书。",
    "利用率是 0.75，不是 75。这个数不能约。",
    "单段没有句号",
    "第一段。\n\n第二段？第三句！",
    "排队论（M/M/1 模型）研究随机过程。参数由 λ 与 μ 决定。",
    "真的……然后呢？",
    "  前后都有空白  ",
    "嵌套【括号（里面。有句号）不断】句。",
]


@pytest.mark.parametrize("source", SAMPLES)
def test_span_slices_back_to_the_exact_text(source):
    for sentence in split_sentences(source):
        assert source[sentence.start : sentence.end] == sentence.text


@pytest.mark.parametrize("source", SAMPLES)
def test_spans_never_overlap_and_move_forward(source):
    spans = [(s.start, s.end) for s in split_sentences(source)]
    for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
        assert prev_end <= next_start, "区间重叠会让高亮互相覆盖"
    for start, end in spans:
        assert start < end, "空区间不该产出"


@pytest.mark.parametrize("source", SAMPLES)
def test_concatenating_sentences_loses_only_whitespace(source):
    joined = "".join(texts(source))
    assert "".join(joined.split()) == "".join(source.split())


# ====================== 断句规则 ======================


def test_splits_on_chinese_terminators():
    assert texts("第一句。第二句！第三句？") == ["第一句。", "第二句！", "第三句？"]


def test_does_not_split_on_ascii_period():
    # 小数、缩写、文件名、URL 都会被英文句点误伤，所以一概不按它断
    assert texts("利用率是 0.75。") == ["利用率是 0.75。"]


def test_does_not_split_on_semicolon():
    # 分号连接的多半是同一句话的两个分句，断开会切出没法单独评的碎片
    assert len(split_sentences("到达率是 λ；服务率是 μ。")) == 1


def test_question_mark_inside_quotes_does_not_split():
    source = "他问：“这真的成立吗？”然后翻开了书。"
    assert texts(source) == [source]


def test_quoted_sentence_does_not_split_at_the_closing_quote():
    """已知的保守取舍：引号收尾处一律不断句。

    下面两句结构完全一样（…“…终止符”…。），但语感上第一句该断、第二句不该：

        他说：“我不知道。”这是实话。      ← 引号后另起一句
        他问：“这真的成立吗？”然后翻开了书。 ← 引号后是同一句的延续

    没有语法分析就分不开这两者。两害相权取轻：**宁可少断，不可多断**。
    少断只是高亮范围大一点；多断会把一句话腰斩，学生看到「然后翻开了书。」
    这种残句挂着评语，比范围大更难懂。
    """
    assert texts("他说：“我不知道。”这是实话。") == ["他说：“我不知道。”这是实话。"]
    assert texts("他问：“这真的成立吗？”然后翻开了书。") == ["他问：“这真的成立吗？”然后翻开了书。"]


def test_nested_brackets_suppress_splitting():
    source = "嵌套【括号（里面。有句号）不断】句。"
    assert texts(source) == [source]


def test_consecutive_terminators_are_one_ending():
    assert texts("真的吗？！当然。") == ["真的吗？！", "当然。"]


def test_ellipsis_ends_a_sentence():
    assert texts("真的……然后呢？") == ["真的……", "然后呢？"]


def test_paragraph_without_terminator_is_one_sentence():
    assert texts("单段没有句号") == ["单段没有句号"]


# ====================== 编号 ======================


def test_ids_are_paragraph_then_sentence_scoped():
    assert ids("甲。乙。\n丙。") == ["P1S1", "P1S2", "P2S1"]


def test_blank_lines_do_not_consume_paragraph_numbers():
    # 空行只是分隔，不该让段号跳号——段号是要展示给学生的
    assert ids("甲。\n\n\n乙。") == ["P1S1", "P2S1"]


def test_ids_are_unique():
    source = "甲。乙。丙。\n丁。戊。\n\n己。"
    got = ids(source)
    assert len(got) == len(set(got))


# ====================== 边界 ======================


@pytest.mark.parametrize("source", ["", "   ", "\n\n", "\t \n  \t"])
def test_blank_input_yields_nothing(source):
    assert split_sentences(source) == []


def test_leading_and_trailing_whitespace_is_not_highlighted():
    # 高亮区间里带空白，画出来的下划线会莫名其妙多出一截
    (sentence,) = split_sentences("  中间有字  ")
    assert sentence.text == "中间有字"
    assert not sentence.text[:1].isspace()
    assert not sentence.text[-1:].isspace()


def test_returns_frozen_dataclass():
    (sentence,) = split_sentences("一句话。")
    assert isinstance(sentence, Sentence)
    with pytest.raises(Exception):
        sentence.start = 99  # type: ignore[misc]
