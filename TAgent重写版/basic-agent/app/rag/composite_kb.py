"""把多个知识来源拼在一起检索。

本地教材 + OpenNotebook 是第一阶段最可能的形态：
一边失败时另一边仍能作答，三个 service 不用知道背后有几个来源。
"""

from __future__ import annotations

import logging
from typing import Any


log = logging.getLogger(__name__)


class CompositeKnowledgeBase:
    def __init__(self, *sources):
        if not sources:
            raise ValueError("CompositeKnowledgeBase needs at least one source.")
        self.sources = sources

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "composite",
            "sources": [
                source.describe() if hasattr(source, "describe") else {"kind": type(source).__name__}
                for source in self.sources
            ],
        }

    def warm_up(self) -> None:
        errors: list[str] = []
        for source in self.sources:
            try:
                source.warm_up()
            except Exception as exc:
                errors.append(f"{type(source).__name__}: {exc}")
                # 少一个来源不致命，但必须喊出来：否则配错地址的表现是
                # "答疑一切正常，只是笔记一条都检索不到"，没人会去查。
                log.warning(
                    "知识来源 %s 预热失败，本次运行它不会参与检索：%s",
                    _kind_of(source),
                    exc,
                )
        if len(errors) == len(self.sources):
            raise RuntimeError("所有知识来源预热失败：" + "；".join(errors))

    def ensure_index(self) -> list:
        chunks: list = []
        for source in self.sources:
            if hasattr(source, "ensure_index"):
                try:
                    chunks.extend(source.ensure_index() or [])
                except Exception:
                    continue
        return chunks

    def retrieve(self, query: str, notebook_ids: list[str] | None = None):
        return self._merge(lambda source: source.retrieve(query, notebook_ids=notebook_ids), notebook_ids)

    def search(self, query: str, *, k: int = 3, notebook_ids: list[str] | None = None):
        documents: list = []
        for source in self._iter_sources(notebook_ids):
            try:
                documents.extend(source.search(query, k=k, notebook_ids=notebook_ids) or [])
            except Exception:
                continue
        return documents

    def chunks(self, notebook_ids: list[str] | None = None):
        documents: list = []
        errors: list[str] = []
        for source in self._iter_sources(notebook_ids):
            try:
                documents.extend(source.chunks(notebook_ids=notebook_ids) or [])
            except Exception as exc:
                errors.append(str(exc))
        if not documents:
            raise RuntimeError("没有可出题的知识片段。" + (" ".join(errors) if errors else ""))
        return documents

    def sample_exam_context(
        self, topic: str | None = None, notebook_ids: list[str] | None = None
    ) -> str:
        parts: list[str] = []
        for source in self._iter_sources(notebook_ids):
            try:
                context = source.sample_exam_context(topic, notebook_ids=notebook_ids)
            except Exception:
                continue
            if context and context.strip():
                parts.append(context.strip())
        return "\n\n---\n\n".join(parts)

    def quiz_documents(self, *, max_documents: int = 2, notebook_ids: list[str] | None = None):
        from app.rag.knowledge_base import select_quiz_documents

        return select_quiz_documents(self.chunks(notebook_ids=notebook_ids), max_documents=max_documents)

    def _iter_sources(self, notebook_ids: list[str] | None):
        scoped = [str(item).strip() for item in notebook_ids or [] if str(item).strip()]
        for source in self.sources:
            kind = source.describe().get("kind") if hasattr(source, "describe") else ""
            if scoped and kind == "local":
                continue
            yield source

    def _merge(self, call, notebook_ids: list[str] | None = None):
        parts: list[str] = []
        documents: list = []
        errors: list[str] = []
        for source in self._iter_sources(notebook_ids):
            try:
                context, docs = call(source)
            except Exception as exc:
                errors.append(str(exc))
                log.warning("知识来源 %s 检索失败，已跳过：%s", _kind_of(source), exc)
                continue
            if context and context.strip():
                parts.append(context.strip())
            documents.extend(docs or [])
        if not parts and not documents:
            raise RuntimeError("所有知识来源检索失败。" + (" ".join(errors) if errors else ""))
        return "\n\n---\n\n".join(parts), documents


def _kind_of(source) -> str:
    if hasattr(source, "describe"):
        try:
            return str(source.describe().get("kind") or type(source).__name__)
        except Exception:
            pass
    return type(source).__name__
