"""本地知识库：加载、切块、建索引、检索、采样。

三个 service 共用同一个实例——嵌入模型和 FAISS 索引都很贵，
不能让 ChatService / QuizService / ExamService 各建一份。

线程安全：_vector_lock 只保护建索引这一步；检索本身是只读的。
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import re
import shutil
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
from app.rag.references import REFERENCE_CHUNK_FORMAT, reference_documents, reference_files
from app.util.markdown_sanitizer import clean_reference_for_display, truncate_markdown_fragment


log = logging.getLogger(__name__)
EMBEDDING_MODEL = "shibing624/text2vec-base-chinese"
# 切块参数或缓存格式一变就要改这个值：缓存按「教材内容 + 嵌入模型 + 这个值」认，
# 改了才会重建，不然会拿旧切法的索引配新切法的片段
INDEX_CACHE_FORMAT = "faiss-v1-md-headers-800-50"


def _load_default_embeddings():
    """优先只读本机 Hugging Face 缓存，缓存里没有才联网下载。

    以前用 snapshot_download(local_files_only=True) 判断缓存在不在，但它按模型仓库的
    **完整**文件清单核对：这个仓库还带 onnx / openvino 等我们用不到的文件，缓存里没有，
    于是每次都被判「缓存不完整」而改走联网——联网时启动慢（实测 27.7 秒后仍然失败），
    断网时直接失败，本地教材检索跟着不能用。其实 sentence-transformers 要的权重、
    分词器、池化配置都在缓存里，让它自己只读本地，断网也是 3 秒左右加载完。
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    try:
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL, model_kwargs={"local_files_only": True}
        )
        log.info("嵌入模型走本地缓存：%s", EMBEDDING_MODEL)
        return embeddings
    except Exception as exc:
        log.warning("本地缓存里没有可用的嵌入模型（%s），改为联网下载 %s", exc, EMBEDDING_MODEL)
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


class KnowledgeBase:
    def __init__(
        self,
        *,
        text_db_dir: str | Path | None = None,
        knowledge_file: str | Path | None = None,
        embeddings=None,
        vectorstore=None,
        index_cache_dir: str | Path | None = None,
        references_dir: str | Path | None = None,
    ):
        self.text_db_dir = Path(text_db_dir or DEFAULT_TEXT_DB_DIR)
        # 参考文献目录（《系统仿真学报》等论文抽出的 .md）；None = 只用教材（单测默认如此）
        self.references_dir = Path(references_dir) if references_dir else None
        # 向量索引的磁盘缓存目录；None = 不缓存（单测注入假嵌入时就是这样）
        self.index_cache_dir = Path(index_cache_dir) if index_cache_dir else None
        self.knowledge_file = Path(knowledge_file or DEFAULT_KNOWLEDGE_FILE)
        self.embeddings = embeddings
        self.vectorstore = vectorstore
        self._knowledge_chunks: list[Document] | None = None
        # 并进索引的参考文献篇数，建好块之后才知道（describe 每次检索都会被调，不能每次去列目录）
        self._reference_count: int | None = None
        # 嵌入模型是否已经单线程推理过一次（见 ensure_index）
        self._query_ready = False
        self._vector_lock = threading.RLock()

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "local",
            "file": str(self.knowledge_file),
            "references": self._reference_count,
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
        if self._knowledge_chunks is not None and self.vectorstore is not None and self._query_ready:
            return self._knowledge_chunks
        with self._vector_lock:
            self.chunks()
            if self.vectorstore is None:
                if self.embeddings is None:
                    self.embeddings = _load_default_embeddings()
                self.vectorstore = self._load_or_build_index()
            if not self._query_ready:
                # 进程里**第一次**推理必须单线程做完：16 路检索同时成为第一次推理，
                # 实测 3 次里 2 次段错误（进程直接没了）、1 次卡死（CPU 空转 700%）；先单独推理一次，
                # 之后 16 路同时只要 0.3 秒（2026-10-03）。以前预热总要嵌入整本教材，顺带做了这一步；
                # 有了索引缓存以后预热只读盘、不推理，第一次推理就落到了学生的第一个问题上。
                # 在锁里做：预热之前就到的检索都在这里排队，等这一次做完。
                if self.embeddings is not None:
                    self.embeddings.embed_query("预热")
                self._query_ready = True
            return self._knowledge_chunks

    # ---------------------------------------------------------------- 索引缓存
    #
    # 以前每次启动都把整本教材重新嵌入一遍建 FAISS 索引：本机实测预热 23 秒，其中 20 秒在这一步
    # （2026-10-02）。教材不常变，建好的索引存到应用数据目录里，下次启动直接读回来。
    # 放应用数据目录而不是项目目录，理由同学习记录库：项目在 iCloud 同步的桌面上。

    def _index_cache_path(self) -> Path | None:
        if self.index_cache_dir is None:
            return None
        digest = hashlib.sha256()
        digest.update(INDEX_CACHE_FORMAT.encode())
        digest.update(EMBEDDING_MODEL.encode())
        digest.update(self.knowledge_file.read_bytes())
        # 参考文献加了、删了、改了都要重建：文件名和内容都算进去（没有论文时缓存键和以前一样）
        papers = reference_files(self.references_dir)
        if papers:
            digest.update(REFERENCE_CHUNK_FORMAT.encode())
        for path in papers:
            digest.update(b"\0" + path.name.encode() + b"\0")
            digest.update(path.read_bytes())
        return self.index_cache_dir / digest.hexdigest()[:16]

    def _load_or_build_index(self):
        from langchain_community.vectorstores import FAISS

        cache = self._index_cache_path()
        if cache is not None and (cache / "index.faiss").exists():
            try:
                # 反序列化只读我们自己写进应用数据目录的文件；能改那里的人本来就能以本用户身份跑代码
                store = FAISS.load_local(str(cache), self.embeddings, allow_dangerous_deserialization=True)
                log.info("向量索引走缓存：%s", cache)
                return store
            except Exception as exc:  # noqa: BLE001 —— 缓存坏了就重建，不能因此起不来
                log.warning("向量索引缓存读不了，重建：%s", exc)

        texts = [chunk.page_content for chunk in self._knowledge_chunks]
        store = FAISS.from_embeddings(
            list(zip(texts, self._embed_reusing_memo(texts))),
            self.embeddings,
            metadatas=[chunk.metadata for chunk in self._knowledge_chunks],
        )
        if cache is not None:
            self._save_index_cache(store, cache)
        return store

    # ---------------------------------------------------------------- 逐块的向量缓存
    #
    # 上面的索引缓存按「教材 + 全部论文」整体认：加一篇论文、改一行教材，整份就作废，
    # 以前要把 2400 多块全部重新嵌入（本机 61~69 秒，嵌入速度和线程数、Apple GPU 都几乎无关）。
    # 这里另存一份「每块文字 → 向量」，重建时只嵌入新出现的块：加一篇论文只算它自己那二十来块。

    def _vector_memo_path(self) -> Path | None:
        if self.index_cache_dir is None:
            return None
        model = hashlib.sha256(EMBEDDING_MODEL.encode()).hexdigest()[:8]
        # 点开头：_save_index_cache 清理旧索引时会跳过它
        return self.index_cache_dir / f".chunk-vectors-{model}.npz"

    def _embed_reusing_memo(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        memo_path = self._vector_memo_path()
        keys = [hashlib.sha1(text.encode("utf-8")).hexdigest() for text in texts]
        known: dict[str, Any] = {}
        if memo_path is not None and memo_path.exists():
            try:
                with np.load(memo_path) as data:
                    known = dict(zip(data["keys"].tolist(), data["vectors"]))
            except Exception as exc:  # noqa: BLE001 —— 坏了就当没有，全部重新嵌入
                log.warning("块向量缓存读不了，全部重新嵌入：%s", exc)
                known = {}

        todo: dict[str, str] = {}  # 同样的文字只嵌入一次（教材里有十几块完全相同）
        for key, text in zip(keys, texts):
            if key not in known and key not in todo:
                todo[key] = text
        if todo:
            fresh = self.embeddings.embed_documents(list(todo.values()))
            for key, vector in zip(todo, fresh):
                known[key] = np.asarray(vector, dtype=np.float32)
        log.info("向量：复用 %d 块，新嵌入 %d 块", len(set(keys)) - len(todo), len(todo))

        if memo_path is not None:
            self._save_vector_memo(memo_path, {key: known[key] for key in dict.fromkeys(keys)})
        return [np.asarray(known[key], dtype=np.float32).tolist() for key in keys]

    @staticmethod
    def _save_vector_memo(path: Path, vectors: dict[str, Any]) -> None:
        """只留这次用到的块（不越攒越多），先写临时文件再改名。"""
        import numpy as np

        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "wb") as handle:
                np.savez(handle, keys=np.array(list(vectors)), vectors=np.stack(list(vectors.values())))
            os.replace(tmp, path)
            # 换过嵌入模型的话，旧模型的那份没用了
            for old in path.parent.glob(".chunk-vectors-*.npz"):
                if old != path:
                    old.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001 —— 存不下只是下次还要重新嵌入
            log.warning("块向量缓存没存上：%s", exc)
        finally:
            tmp.unlink(missing_ok=True)

    @staticmethod
    def _save_index_cache(store, cache: Path) -> None:
        """先写临时目录再改名：进程写到一半被杀，留下的也不会是一份读得进来的半截索引。"""
        tmp = cache.with_name(f".{cache.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            store.save_local(str(tmp))
            if cache.exists():
                shutil.rmtree(cache, ignore_errors=True)
            os.replace(tmp, cache)
            # 教材换过之后旧的那份就没用了，别越攒越多
            for old in cache.parent.iterdir():
                if old != cache and not old.name.startswith("."):
                    shutil.rmtree(old, ignore_errors=True)
            log.info("向量索引已缓存：%s", cache)
        except Exception as exc:  # noqa: BLE001 —— 存不下缓存只是下次还慢，不影响这次
            log.warning("向量索引缓存没存上：%s", exc)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
    def chunks(self, notebook_ids: list[str] | None = None) -> list[Document]:
        if self._knowledge_chunks is not None:
            return self._knowledge_chunks
        with self._vector_lock:
            if self._knowledge_chunks is None:
                chunks = self._build_text_database(self.knowledge_file)
                papers = reference_documents(self.references_dir)
                self._reference_count = len({paper.metadata["file"] for paper in papers})
                if papers:
                    log.info("参考文献 %d 篇（%d 块）并入本地知识库", self._reference_count, len(papers))
                self._knowledge_chunks = chunks + papers
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
