"""通用文本与序列工具。任何层都可依赖，本模块不依赖任何层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content or "")

def chunked(items: list, size: int) -> list[list]:
    return [items[index : index + size] for index in range(0, len(items), size)]

def deal_shards(text: str, shard_count: int, *, separator: str, char_limit: int) -> list[str]:
    """把一整段拼好的参考材料切回独立片段，轮流发牌成 shard_count 份。

    给闪卡分片出题用：每片拿到互不相同的材料，是并发分片不撞考点的主要手段
    （整卷那边实测过"把已考知识点清单塞回 prompt"，结果是重复更多，不走那条）。

    - 片段数少于 shard_count 时按片段数发牌，绝不产出空材料的一片；
    - 每份按 char_limit 收，但至少保留一个完整片段，宁可超一点也不给半句话；
    - 放不下的片段**跳过而不是就此收手**——各片材料的丰富度正是"分片不撞考点"
      这个说法的全部依据，一份超大材料不该顺带把它后面还塞得下的都挤掉。
    """
    pieces = [piece.strip() for piece in (text or "").split(separator)]
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        return []

    count = max(1, min(shard_count, len(pieces)))
    buckets: list[list[str]] = [[] for _ in range(count)]
    for index, piece in enumerate(pieces):
        buckets[index % count].append(piece)

    shards: list[str] = []
    for bucket in buckets:
        kept: list[str] = []
        total = 0
        for piece in bucket:
            # 第一份无条件收下：宁可超出 char_limit，也不能把一份材料截成半句话
            if kept and total + len(separator) + len(piece) > char_limit:
                continue  # 这份太大，跳过它接着试后面的，别让一份材料断送整片
            total += (len(separator) if kept else 0) + len(piece)
            kept.append(piece)
        if kept:
            shards.append(separator.join(kept))
    return shards


# ====================== 句子切分（逐句批注的唯一事实源） ======================
#
# 高亮要能落回原文，靠的**不是**让模型回引文或字符下标——模型会改写引文，
# 下标更是算不准。做法反过来：这里先把正文切好、编好号（P2S3），把带号的
# 正文喂给模型，模型只回编号；高亮时拿编号查这里存下的 (start, end)。
# 零匹配、零猜测。
#
# 所以这个函数是**唯一事实源**：前端绝不能自己再切一遍，两边规则差一条，
# 所有高亮就整体错位。切分结果连同区间一起下发。

SENTENCE_END = "。！？!?…"

# 成对符号：在它们内部出现的句末标点不算句子结束（引文里的问号最常见）
_PAIRS = {
    "（": "）", "(": ")", "【": "】", "[": "]", "《": "》",
    "「": "」", "『": "』", "“": "”", "‘": "’",
}
# 句末标点后面紧跟的收尾符号要一起收进这句，不能留给下一句开头
_TRAILING = "”’」』）)】]》\"'"


@dataclass(frozen=True)
class Sentence:
    """一个句子及其在**原文**中的区间。恒等式：source[start:end] == text。"""

    id: str          # "P2S3"：第 2 段第 3 句
    paragraph: int   # 段号，从 1 起
    index: int       # 段内句号，从 1 起
    start: int       # 原文下标，含
    end: int         # 原文下标，不含
    text: str


def split_sentences(source: str) -> list[Sentence]:
    """把正文切成带原文区间的句子。

    只按 。！？!? 和省略号断句，**不按英文句点断**——小数（3.5）、缩写、
    文件名、URL 都会被误伤，而中文学术写作本来就用。断句。分号同理不断：
    它多半连接的是同一句话的两个分句，断开会切出一堆没法单独评的碎片。

    成对符号内部不断句，句末标点后面的收尾引号/括号跟着前一句走。
    段落按空行或换行切，段内没有句末标点时整段算一句。
    """
    sentences: list[Sentence] = []
    if not source:
        return sentences

    paragraph_no = 0
    for para_start, para_end in _paragraph_spans(source):
        paragraph_no += 1
        index = 0
        for start, end in _sentence_spans(source, para_start, para_end):
            index += 1
            sentences.append(
                Sentence(
                    id=f"P{paragraph_no}S{index}",
                    paragraph=paragraph_no,
                    index=index,
                    start=start,
                    end=end,
                    text=source[start:end],
                )
            )
    return sentences


def _paragraph_spans(source: str) -> list[tuple[int, int]]:
    """按换行切段并去掉两端空白，返回**原文**下标区间；空段丢弃。"""
    spans: list[tuple[int, int]] = []
    cursor = 0
    for chunk in source.split("\n"):
        start, end = cursor, cursor + len(chunk)
        cursor = end + 1  # 跳过 "\n"
        while start < end and source[start].isspace():
            start += 1
        while end > start and source[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))
    return spans


def _sentence_spans(source: str, para_start: int, para_end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    stack: list[str] = []
    start = para_start
    position = para_start

    while position < para_end:
        char = source[position]
        if stack and char == stack[-1]:
            stack.pop()
        elif char in _PAIRS:
            stack.append(_PAIRS[char])
        elif char in SENTENCE_END and not stack:
            position += 1
            # 连着的句末标点（？！、……）算同一个结尾
            while position < para_end and source[position] in SENTENCE_END:
                position += 1
            # 收尾引号/括号跟着前一句
            while position < para_end and source[position] in _TRAILING:
                position += 1
            spans.append((start, position))
            while position < para_end and source[position].isspace():
                position += 1
            start = position
            continue
        position += 1

    if start < para_end:  # 段尾没有句末标点的残句
        spans.append((start, para_end))
    return spans
