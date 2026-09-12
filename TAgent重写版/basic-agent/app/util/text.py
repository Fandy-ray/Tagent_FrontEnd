"""通用文本与序列工具。任何层都可依赖，本模块不依赖任何层。"""

from __future__ import annotations

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
