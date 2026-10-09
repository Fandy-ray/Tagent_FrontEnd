"""答疑用到的材料 → 前端「参考资料」里的出处。

检索到的几块材料原样塞进了 prompt，这里把同一批材料摆成出处列表随回答一起返回：
学生看得到这条回答依据的是教材哪一章哪一页、哪篇论文、笔记本里哪条来源。
以前接口只回正文，前端只能拿问题去笔记本里另搜一遍来猜出处（2026-10-07 Windows 测试报告：
「该接口未返回结构化引用」）。

三种材料各给各的字段，前端按 kind 认：
    textbook  本地教材 book1.md：chapter（第几章）、page（书上印的页码）
    paper     参考文献：title、citation（期刊、年、卷期页）、href（期刊官网的文章页）
    notebook  OpenNotebook：source_id（笔记本里的来源/笔记 ID）、notebook_id、notebook_name
"""

from __future__ import annotations

import bisect
import re
from typing import Any

SNIPPET_CHARS = 180

# 教材 book1.md 是逐页转写的，每页开头一行 `--- Page N ---`。N 比书上印的页码大 1
# （第 1 页是空白的打印封面；文中「页码信息」写着印刷页码，从头到尾抽查十几处都差 1）。
_PAGE_MARK = re.compile(r"^---\s*Page\s+(\d+)\s*---\s*$")
# 章号取自一到三级标题里的「第 N 章」，或打头的小节号（「2.3 分布假设与检验」「四、1.1.3 系统仿真的优势」
# → 第 2 / 1 章）。小节号前只许有几个字的前缀，后面要跟着标题文字：四级标题里的「步长为 0.01 的情况」
# 「时间点：.1053E+02 = 10.53 秒」这类数值不算；前缀里有「图 / 表 / 例 / 式」的是图表编号，也不算。
_CHAPTER_HEADING = re.compile(r"第\s*(\d{1,2})\s*章")
_SECTION_HEADING = re.compile(r"^[^\d图表例式]{0,8}?(\d{1,2})\.\d{1,2}(?:\.\d{1,2})?\s*[^\d\s.]")
_HEADING = re.compile(r"^#{1,3}\s")
# 论文块末尾的「——摘自《题目》（出处）」，片段里不重复它
_PAPER_LABEL = re.compile(r"\n——摘自《[^\n]*$")
_URL = re.compile(r"https?://\S+")


def annotate_book_locations(content: str, chunks: list[Any]) -> None:
    """给教材的每一块标上 source = textbook，再记上 chapter / page（找不到的不记）。

    块是按顺序切出来的：拿每块第一行的开头去原文里往后找，找到的位置之前最近的页标记、章号就是它的。
    切块时每行首尾的空白会被去掉，所以只取一行之内的开头去找。
    """
    offsets: list[int] = []
    pages: list[int | None] = []
    chapters: list[int | None] = []
    page: int | None = None
    chapter: int | None = None
    position = 0
    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        marker = _PAGE_MARK.match(stripped)
        if marker:
            number = int(marker.group(1))
            page = number - 1 if number > 1 else None
        elif _HEADING.match(stripped):
            heading = stripped.lstrip("#").replace("*", "").strip()
            found = _CHAPTER_HEADING.search(heading) or _SECTION_HEADING.search(heading)
            if found:
                chapter = int(found.group(1))
        offsets.append(position)
        pages.append(page)
        chapters.append(chapter)
        position += len(line)

    cursor = 0
    for chunk in chunks:
        chunk.metadata["source"] = "textbook"
        head = chunk.page_content.strip().split("\n", 1)[0].strip()[:40]
        if not head:
            continue
        found_at = content.find(head, cursor)
        if found_at < 0:
            continue
        cursor = found_at + 1
        line_index = bisect.bisect_right(offsets, found_at) - 1
        if pages[line_index] is not None:
            chunk.metadata["page"] = pages[line_index]
        if chapters[line_index] is not None:
            chunk.metadata["chapter"] = chapters[line_index]


def citations_from_documents(documents: list[Any]) -> list[dict[str, Any]]:
    """去重后的出处，顺序同检索结果（越靠前越相关）。同一页教材、同一篇论文只列一次。"""
    seen: set[str] = set()
    citations: list[dict[str, Any]] = []
    for document in documents or []:
        citation = _citation(document)
        if citation is None or citation["id"] in seen:
            continue
        seen.add(citation["id"])
        citations.append(citation)
    return citations


def _citation(document: Any) -> dict[str, Any] | None:
    metadata = getattr(document, "metadata", None) or {}
    text = str(getattr(document, "page_content", "") or "")
    source = metadata.get("source")

    if source == "reference":
        name = str(metadata.get("file") or "").strip()
        title = str(metadata.get("h2") or name).strip()
        if not title:
            return None
        href = str(metadata.get("href") or "")
        return {
            "id": f"reference:{name or title}",
            "kind": "paper",
            "title": title,
            "citation": str(metadata.get("citation") or ""),
            "href": href if href.startswith(("https://", "http://")) else "",
            "snippet": _snippet(_PAPER_LABEL.sub("", text)),
        }

    if source == "opennotebook":
        ident = str(metadata.get("id") or "").strip()
        title = str(metadata.get("h1") or "").strip()
        if not ident and not title:
            return None
        return {
            "id": ident or f"notebook:{title}",
            "kind": "notebook",
            "source_id": ident,
            "title": title,
            "notebook_id": str(metadata.get("notebook_id") or ""),
            "notebook_name": str(metadata.get("notebook_name") or ""),
            "snippet": _snippet(text),
        }

    if source != "textbook":
        return None  # 认不出是哪种材料，宁可不列，也不冒充教材

    chapter = metadata.get("chapter")
    page = metadata.get("page")
    citation: dict[str, Any] = {
        "id": f"textbook:{chapter or ''}:{page or ''}",
        "kind": "textbook",
        "title": "课程教材",
        "snippet": _snippet(text),
    }
    if isinstance(chapter, int):
        citation["chapter"] = chapter
    if isinstance(page, int):
        citation["page"] = page
    return citation


def split_reference_source(source: str) -> tuple[str, str]:
    """`> 来源：` 那一行 → （期刊、年、卷期页，官网地址）。

    tools/fetch_references.py 写的是「系统仿真学报, 2022, 34(7): 1651-1661。https://…」；
    自己手写的可能只有前半句，也可能只有网址。
    """
    found = _URL.search(source)
    href = found.group(0).rstrip("。.，,)）") if found else ""
    citation = _URL.sub("", source).strip().split("。")[0].strip()
    return citation, href


def _snippet(text: str) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= SNIPPET_CHARS else flat[:SNIPPET_CHARS].rstrip() + "…"
