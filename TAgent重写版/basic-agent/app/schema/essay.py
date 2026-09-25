"""逐句批注与论文批改的数据模型。

两处共用这一套：
- 整卷大题：在原有 rubric 计分之外，补上「问题出在哪一句」的高亮；
- 答疑论文辅助：整篇三维打分 + 高亮。

设计要点全在 app/util/text.py 的 split_sentences 注释里说过一遍，这里只重复
最要紧的一条：**模型只回句子编号，永不回原文片段或字符下标**。区间由后端
自己切分时就存好，高亮时查表，零匹配零猜测。

本模块是纯逻辑，不碰网络，可离线单测。
"""

from __future__ import annotations

import math
import re
from typing import List, Literal, Optional, Sequence, Set

from pydantic import Field, field_validator

from app.schema.exam import StrictModel
from app.util.text import Sentence


AnnotationKind = Literal["issue", "praise"]
DimensionName = Literal["content", "argument", "language"]

DIMENSION_LABELS: dict[str, str] = {
    "content": "切题与内容",
    "argument": "论证与结构",
    "language": "语言与规范",
}

# 权重之和必须是 1.0，否则总分没有意义（见 weighted_score 的断言）
DIMENSION_WEIGHTS: dict[str, float] = {
    "content": 0.40,
    "argument": 0.35,
    "language": 0.25,
}

# 评分要点由后端给死，模型只负责逐条判命中/未命中。
#
# 让模型自己想要点，分母就会飘——同一篇作文重批两次，一次它想出 3 条要点、
# 一次想出 5 条，分数自然对不上。要点写死之后 score_ratio 的分母是常数，
# 打分就变成可复算的计数（整卷大题实测过：同一份答卷重判 3 次得分完全一致）。
#
# 每维 4 条 → score_ratio ∈ {0, .25, .5, .75, 1}，粒度够用又不至于让模型纠结。
RUBRIC_POINTS: dict[str, tuple[str, ...]] = {
    "content": (
        "回应了题目要求，没有答非所问",
        "用上了课程材料里的概念，而不是只凭常识泛谈",
        "有具体例子、数据或案例支撑，不是空泛表述",
        "观点明确，读得出作者自己的立场",
    ),
    "argument": (
        "每个论点都有对应的论据，不是只下结论",
        "段落之间有逻辑推进，不是并列罗列",
        "考虑了反面情形或适用局限",
        "结论由前文推出，不是凭空跳出来的",
    ),
    "language": (
        "没有明显病句或成分残缺",
        "术语使用准确，没有张冠李戴",
        "是书面语，没有口语化表达",
        "段落长度与格式得当，没有整篇一段到底",
    ),
}

# 定额，不是阈值。模型对「发现问题就标出来」这种阈值判断服从度很差，
# 要么全标要么不标；改成「最多挑 N 处、按严重程度排序」就稳定得多，
# 顺带把这一轮的输出量变成有上界的。
MAX_ISSUES = 3
MAX_PRAISES = 2


# ====================== LLM 输出（不可信，严格校验） ======================
class LLMAnnotation(StrictModel):
    sentence_id: str = Field(min_length=1)
    kind: AnnotationKind
    comment: str = Field(min_length=1)


class LLMAnnotationBatch(StrictModel):
    items: List[LLMAnnotation] = Field(default_factory=list)


# 「1. 」「2、」「（3）」「三、」这类列表编号。prompt 里的要点是编号列出来的，
# 模型照抄时多半连编号一起抄回来——编号不可能是要点正文的一部分。
_LIST_MARKER = re.compile(r"^\s*[（(]?\s*(?:\d{1,2}|[一二三四五六七八九十]{1,3})\s*[）).、．:：]\s*")


class LLMDimension(StrictModel):
    """一个维度的判分结果。沿用解答题那套：逐条勾要点，不给整体印象分。"""

    hits: List[str] = Field(default_factory=list)
    misses: List[str] = Field(default_factory=list)
    comment: str = ""
    # 论证维度顺带返回可疑段号，省掉单独一轮「找可疑段落」
    flagged_paragraphs: List[int] = Field(default_factory=list)

    @field_validator("hits", "misses", mode="before")
    @classmethod
    def _drop_list_markers(cls, value):
        """比对之前先剥掉要点前面的编号。

        prompt 用「1. …」的形式列要点，评语里「命中了第 1、2 条」指的就是这个编号，
        所以编号得留在 prompt 里（前端按同一套顺序给要点编号，学生才对得上）。代价是
        模型会把编号一起抄回 hits/misses，而 validate_dimension 做的是精确集合比对，
        一比就不过，两次重试之后整篇批改报 502「AI 输出结构异常」。

        实测：带上真实知识库上下文时 DeepSeek 稳定复现（2/2），用打桩的空上下文反而
        碰不到，所以这不是偶发抖动，是必须在入口normalize 掉的东西。

        只剥编号，不做别的宽松处理——把要点换个说法抄回来仍然要判不过。
        """
        if not isinstance(value, list):
            return value

        return [
            _LIST_MARKER.sub("", item).strip() if isinstance(item, str) else item
            for item in value
        ]

    @property
    def score_ratio(self) -> float:
        """命中数 / 总要点数。模型只报勾选结果，比例由后端算——它算不准除法。"""
        total = len(self.hits) + len(self.misses)
        return (len(self.hits) / total) if total else 0.0


def validate_annotations(
    batch: LLMAnnotationBatch,
    known_ids: Set[str],
    *,
    max_issues: int = MAX_ISSUES,
    max_praises: int = MAX_PRAISES,
) -> None:
    """标注 ID 必须是已知句子的**子集**，且不超定额。

    注意和 validate_grade_batch 的区别：判分要求 ID 集合**精确相等**（每题都得
    有分），标注则是模型从全文里**挑几句**，所以只能要求子集。相等在这里是错的
    ——它会逼模型给每一句都写评语，正好是渐进式披露要避免的事。
    """
    seen: Set[str] = set()
    for item in batch.items:
        if item.sentence_id not in known_ids:
            raise ValueError(f"标注指向了不存在的句子：{item.sentence_id}")
        if item.sentence_id in seen:
            raise ValueError(f"同一句被标注了多次：{item.sentence_id}")
        seen.add(item.sentence_id)

    issues = sum(1 for item in batch.items if item.kind == "issue")
    praises = sum(1 for item in batch.items if item.kind == "praise")
    if issues > max_issues:
        raise ValueError(f"问题标注 {issues} 条，超过定额 {max_issues}")
    if praises > max_praises:
        raise ValueError(f"亮点标注 {praises} 条，超过定额 {max_praises}")


def validate_dimension(result: LLMDimension, dimension: str) -> None:
    """hits + misses 必须正好等于该维度的要点全集。

    模型漏报一条要点，分母就从 4 变成 3，学生凭空多得分；重复报一条则相反。
    两种都要挡——这是「打分是可复算的计数」这句话的实际保障。
    """
    expected = set(RUBRIC_POINTS[dimension])
    got = list(result.hits) + list(result.misses)
    if len(got) != len(set(got)):
        raise ValueError(f"{dimension} 的评分要点有重复：{got}")
    if set(got) != expected:
        missing = expected - set(got)
        extra = set(got) - expected
        raise ValueError(
            f"{dimension} 的评分要点对不上：漏了 {sorted(missing)}，多了 {sorted(extra)}"
        )


# ====================== 对外形状（带原文区间） ======================
class Annotation(StrictModel):
    """一条批注。start/end 是**原文**下标，前端据此高亮，不要自己再找位置。"""

    sentence_id: str
    kind: AnnotationKind
    comment: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str


def attach_spans(batch: LLMAnnotationBatch, sentences: Sequence[Sentence]) -> List[Annotation]:
    """把模型回的编号换成带区间的批注，并按原文顺序排好。

    前端要按顺序渲染下划线，乱序会让相邻高亮的边界算错，所以这里就排好。
    """
    index = {sentence.id: sentence for sentence in sentences}
    annotations = [
        Annotation(
            sentence_id=item.sentence_id,
            kind=item.kind,
            comment=item.comment,
            start=index[item.sentence_id].start,
            end=index[item.sentence_id].end,
            text=index[item.sentence_id].text,
        )
        for item in batch.items
        if item.sentence_id in index
    ]
    return sorted(annotations, key=lambda a: a.start)


class DimensionResult(StrictModel):
    name: DimensionName
    label: str
    weight: float
    score_ratio: float = Field(ge=0.0, le=1.0)
    hits: List[str]
    misses: List[str]
    comment: str

    @field_validator("score_ratio", mode="before")
    @classmethod
    def _finite(cls, v):
        f = float(v)
        if not math.isfinite(f):
            raise ValueError("score_ratio 必须是有限数")
        return min(1.0, max(0.0, f))


class QuickScan(StrictModel):
    """本地快筛：0 次模型调用，提交瞬间就能给。"""

    characters: int
    paragraphs: int
    sentences: int
    empty_paragraphs: int
    duplicate_sentence_ids: List[str]
    cites_material: bool


class PaperReview(StrictModel):
    title: str = "小论文批改"
    word_count: int
    quick_scan: QuickScan
    dimensions: List[DimensionResult]
    annotations: List[Annotation]
    score: int = Field(ge=0, le=100)
    overall_comment: str = ""


# ====================== 本地快筛（纯字符串，0 调用） ======================
_CITATION_HINT = re.compile(r"[（(]\s*(?:见|参见|引自|据)|《[^》]{1,40}》|\[\d{1,3}\]")


def quick_scan(source: str, sentences: Sequence[Sentence]) -> QuickScan:
    """能本地算的就本地算——学生提交后立刻看到这些，不必等模型。"""
    paragraphs = [p for p in (source or "").split("\n")]
    non_empty = [p for p in paragraphs if p.strip()]

    # 重复句：归一后完全相同的句子，第二次起算重复
    seen: dict[str, str] = {}
    duplicates: List[str] = []
    for sentence in sentences:
        key = re.sub(r"\s+", "", sentence.text)
        if not key:
            continue
        if key in seen:
            duplicates.append(sentence.id)
        else:
            seen[key] = sentence.id

    return QuickScan(
        characters=len(re.sub(r"\s+", "", source or "")),
        paragraphs=len(non_empty),
        sentences=len(sentences),
        empty_paragraphs=len(paragraphs) - len(non_empty),
        duplicate_sentence_ids=duplicates,
        cites_material=bool(_CITATION_HINT.search(source or "")),
    )


# ====================== 计分 ======================
def weighted_score(dimensions: Sequence[DimensionResult], *, full_marks: int = 100) -> int:
    """按权重折算百分制。权重和必须是 1，否则总分没有意义。"""
    if not dimensions:
        return 0
    total_weight = sum(d.weight for d in dimensions)
    if not math.isclose(total_weight, 1.0, abs_tol=1e-6):
        raise ValueError(f"维度权重之和是 {total_weight}，必须为 1.0")
    ratio = sum(d.score_ratio * d.weight for d in dimensions)
    return int(round(min(1.0, max(0.0, ratio)) * full_marks))


def build_dimension(name: DimensionName, result: LLMDimension) -> DimensionResult:
    return DimensionResult(
        name=name,
        label=DIMENSION_LABELS[name],
        weight=DIMENSION_WEIGHTS[name],
        score_ratio=result.score_ratio,
        hits=result.hits,
        misses=result.misses,
        comment=result.comment,
    )


def numbered_text(sentences: Sequence[Sentence], *, only_paragraphs: Optional[Set[int]] = None) -> str:
    """把正文渲染成带编号的样子喂给模型。模型只需要照着编号回话。

    only_paragraphs 给下钻用：只铺被点名的那几段，别的段不进 prompt——
    省的就是这一轮的输入长度。
    """
    lines = [
        f"{sentence.id} {sentence.text}"
        for sentence in sentences
        if only_paragraphs is None or sentence.paragraph in only_paragraphs
    ]
    return "\n".join(lines)
