"""本地知识库：加载、切块、建索引、检索、采样。

三个 service 共用同一个实例——嵌入模型和 FAISS 索引都很贵，
不能让 ChatService / QuizService / ExamService 各建一份。

线程安全：_vector_lock 只保护建索引这一步；检索本身是只读的。
"""

from __future__ import annotations

import logging
import random
import re
import threading
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.config import (
    DEFAULT_KNOWLEDGE_FILE,
    DEFAULT_TEXT_DB_DIR,
    EXAM_CONTEXT_CHAR_LIMIT,
    EXAM_CONTEXT_SEPARATOR,
    EXAM_SAMPLE_K,
)
from app.util.markdown_sanitizer import clean_reference_for_display, truncate_markdown_fragment


log = logging.getLogger(__name__)
EMBEDDING_MODEL = "shibing624/text2vec-base-chinese"


def _load_default_embeddings():
    """优先用本机 Hugging Face 缓存，避免启动时再打镜像（国内 SSL 经常直接断）。"""
    from langchain_huggingface import HuggingFaceEmbeddings

    model_name = EMBEDDING_MODEL
    try:
        from huggingface_hub import snapshot_download

        model_name = snapshot_download(EMBEDDING_MODEL, local_files_only=True)
        log.info("嵌入模型走本地缓存：%s", model_name)
    except Exception as exc:
        log.warning(
            "本地缓存不可用（%s），改为联网下载 %s",
            exc,
            EMBEDDING_MODEL,
        )
        model_name = EMBEDDING_MODEL
    return HuggingFaceEmbeddings(model_name=model_name)


class KnowledgeBase:
    def __init__(
        self,
        *,
        text_db_dir: str | Path | None = None,
        knowledge_file: str | Path | None = None,
        embeddings=None,
        vectorstore=None,
    ):
        self.text_db_dir = Path(text_db_dir or DEFAULT_TEXT_DB_DIR)
        self.knowledge_file = Path(knowledge_file or DEFAULT_KNOWLEDGE_FILE)
        self.embeddings = embeddings
        self.vectorstore = vectorstore
        self._knowledge_chunks: list[Document] | None = None
        self._vector_lock = threading.RLock()

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "local",
            "file": str(self.knowledge_file),
            "indexed": self.vectorstore is not None,
        }

    def warm_up(self) -> None:
        """启动时预热：加载嵌入模型并建好索引，避免首个请求扛这份开销。"""
        self.ensure_index()

    def search(self, query: str, *, k: int = 3, notebook_ids: list[str] | None = None) -> list[Document]:
        """相似度检索。判卷时给解答题补充知识片段用。"""
        self.ensure_index()
        return self.vectorstore.similarity_search(query, k=k)

    def quiz_documents(self, *, max_documents: int = 2) -> list[Document]:
        return select_quiz_documents(self.chunks(), max_documents=max_documents)

    def retrieve(self, query: str, notebook_ids: list[str] | None = None):
        self.ensure_index()
        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4},
        )
        documents = retriever.invoke(query)
        context = "\n\n---\n\n".join(document.page_content for document in documents)
        return context, documents
    def ensure_index(self) -> list[Document]:
        if self._knowledge_chunks is not None and self.vectorstore is not None:
            return self._knowledge_chunks
        with self._vector_lock:
            self.chunks()
            if self.vectorstore is None:
                if self.embeddings is None:
                    self.embeddings = _load_default_embeddings()
                from langchain_community.vectorstores import FAISS

                self.vectorstore = FAISS.from_documents(self._knowledge_chunks, self.embeddings)
            return self._knowledge_chunks
    def chunks(self, notebook_ids: list[str] | None = None) -> list[Document]:
        if self._knowledge_chunks is not None:
            return self._knowledge_chunks
        with self._vector_lock:
            if self._knowledge_chunks is None:
                self._knowledge_chunks = self._build_text_database(self.knowledge_file)
            return self._knowledge_chunks
    @staticmethod
    def _build_text_database(path: Path) -> list[Document]:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise RuntimeError("The local knowledge document is empty.")
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
        )
        sections = header_splitter.split_text(content)
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=50)
        chunks = splitter.split_documents(sections)
        if not chunks:
            raise RuntimeError("The local knowledge document produced no searchable chunks.")
        return chunks
    def sample_exam_context(self, topic: str | None = None, notebook_ids: list[str] | None = None) -> str:
        """Select diverse knowledge chunks and cap the prompt context size."""
        chunks = self.ensure_index()
        if topic:
            documents = self.vectorstore.max_marginal_relevance_search(
                topic,
                k=EXAM_SAMPLE_K,
                fetch_k=20,
            )
        else:
            groups: dict[tuple[Any, Any, Any], list[Document]] = {}
            for document in chunks:
                key = tuple(document.metadata.get(name) for name in ("h1", "h2", "h3"))
                groups.setdefault(key, []).append(document)
            if len(groups) <= 1:
                pool = list(chunks)
                random.shuffle(pool)
                documents = pool[: EXAM_SAMPLE_K * 2]
            else:
                buckets = [list(group) for group in groups.values()]
                random.shuffle(buckets)
                for bucket in buckets:
                    random.shuffle(bucket)
                documents = []
                while len(documents) < EXAM_SAMPLE_K:
                    progressed = False
                    for bucket in buckets:
                        if bucket:
                            documents.append(bucket.pop())
                            progressed = True
                            if len(documents) >= EXAM_SAMPLE_K:
                                break
                    if not progressed:
                        break

        seen: set[str] = set()
        parts: list[str] = []
        total = 0
        for document in documents:
            fingerprint = re.sub(r"\s+", "", document.page_content)[:120]
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            remaining = EXAM_CONTEXT_CHAR_LIMIT - total
            if remaining <= 0:
                break
            content = document.page_content.strip()[:remaining]
            if content:
                parts.append(content)
                total += len(content)
            if len(parts) >= EXAM_SAMPLE_K:
                break
        return EXAM_CONTEXT_SEPARATOR.join(parts)


def display_document(document: Document) -> str:
    headings = [
        str(document.metadata.get(key, "")).strip()
        for key in ("h1", "h2", "h3")
        if document.metadata.get(key)
    ]
    heading = " / ".join(headings)
    content = clean_reference_for_display(document.page_content)
    return f"### {heading}\n\n{content}" if heading else content
def select_quiz_documents(chunks: list[Document], *, max_documents: int = 2) -> list[Document]:
    if not chunks:
        raise RuntimeError("The local knowledge document produced no searchable chunks.")
    return random.sample(chunks, min(max_documents, len(chunks)))
def join_quiz_context(documents: list[Document], *, max_chars: int = 1800) -> str:
    return _join_limited_sections(
        [clean_reference_for_display(document.page_content) for document in documents],
        max_chars=max_chars,
    )
def join_quiz_display(documents: list[Document], *, max_chars: int = 2200) -> str:
    return _join_limited_sections([display_document(document) for document in documents], max_chars=max_chars)
def _join_limited_sections(sections: list[str], *, max_chars: int) -> str:
    selected = []
    remaining = max_chars
    for section in sections:
        cleaned = section.strip()
        if not cleaned or remaining <= 0:
            continue
        if len(cleaned) > remaining:
            cleaned = truncate_markdown_fragment(cleaned, remaining)
        if not cleaned:
            continue
        selected.append(cleaned)
        remaining -= len(cleaned)
        if remaining > 0:
            remaining -= len("\n\n---\n\n")
    return "\n\n---\n\n".join(selected)
def first_heading(documents: list[Document]) -> str:
    for document in documents:
        for key in ("h3", "h2", "h1"):
            value = str(document.metadata.get(key, "")).strip()
            if value:
                return value
    return ""
