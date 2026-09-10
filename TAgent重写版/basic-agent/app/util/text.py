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
