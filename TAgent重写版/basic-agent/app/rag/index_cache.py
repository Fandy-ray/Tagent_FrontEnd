"""可信本机目录的版本化 FAISS 缓存；不读取旧 pickle，也不删除旧版本。"""

from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
import weakref
from contextlib import contextmanager
from pathlib import Path

from langchain_core.documents import Document


log = logging.getLogger(__name__)
_LOCKS = weakref.WeakValueDictionary()
_LOCKS_GUARD = threading.Lock()


def json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def loaded_embedding_revision(embeddings) -> str | None:
    """读取已经加载的模型 commit，不联网，也不以模型名称猜测版本。"""
    first_module = getattr(getattr(embeddings, "_client", None), "_first_module", None)
    if not callable(first_module):
        return None
    try:
        revision = first_module().auto_model.config._commit_hash
    except (AttributeError, KeyError, IndexError, StopIteration):
        return None
    return revision.lower() if isinstance(revision, str) and re.fullmatch(r"[0-9a-fA-F]{40}", revision) else None


@contextmanager
def cache_lock(directory: Path):
    """线程和进程共用的文件锁；不可写时退回内存，不影响知识检索。"""
    key = os.path.normcase(str(directory.resolve()))
    with _LOCKS_GUARD:
        thread_lock = _LOCKS.get(key)
        if thread_lock is None:
            thread_lock = threading.Lock()
            _LOCKS[key] = thread_lock
    with thread_lock:
        handle = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            handle = (directory / ".lock").open("a+b")
            _lock_file(handle)
        except OSError as error:
            if handle is not None:
                handle.close()
            log.warning("缓存锁不可用（%s），使用内存索引。", type(error).__name__)
            yield False
            return
        try:
            yield True
        finally:
            try:
                _unlock_file(handle)
            finally:
                handle.close()


def atomic_write(path: Path, payload: bytes) -> None:
    """只替换同一缓存的明确目标文件，遗留临时文件不自动删除。"""
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class IndexCache:
    def __init__(self, root: Path, *, source_sha256: str, model_identity: dict, chunk_format: str):
        import faiss

        self.identity = {
            "version": 3,
            "source_sha256": source_sha256,
            "embedding": model_identity,
            "faiss_version": faiss.__version__,
            "chunk_format": chunk_format,
        }
        self.directory = root / "safe-v3" / sha256(json_bytes(self.identity))

    def load(self, embeddings, expected: list[Document]):
        """expected 按检索窗口排列；论文多个窗口可以指向同一父片段。"""
        try:
            manifest = json.loads((self.directory / "manifest.json").read_bytes())
            if manifest.get("identity") != self.identity:
                return None
            index_bytes = (self.directory / "index.faiss").read_bytes()
            document_bytes = (self.directory / "documents.json").read_bytes()
            if manifest.get("index_sha256") != sha256(index_bytes) or manifest.get("documents_sha256") != sha256(document_bytes):
                return None
            entries = json.loads(document_bytes)
            if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
                return None
            if [{"page_content": e.get("page_content"), "metadata": e.get("metadata")} for e in entries] != [
                {"page_content": doc.page_content, "metadata": doc.metadata} for doc in expected
            ]:
                return None
            ids = [entry.get("id") for entry in entries]
            if not all(isinstance(value, str) and value for value in ids) or len(set(ids)) != len(ids):
                return None
            import faiss
            import numpy as np
            from langchain_community.docstore.in_memory import InMemoryDocstore
            from langchain_community.vectorstores import FAISS

            # 官方字节序列化避免 Windows 中文路径限制；仅接受本机可信目录。
            # https://github.com/facebookresearch/faiss/wiki/Index-IO,-cloning-and-hyper-parameter-tuning
            index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype=np.uint8))
            if not isinstance(index, faiss.IndexFlatL2) or index.ntotal != len(expected):
                return None
            documents = {entry["id"]: Document(**entry) for entry in entries}
            log.info("向量索引走安全缓存：%s（%d 个窗口）", self.directory, index.ntotal)
            return FAISS(embeddings, index, InMemoryDocstore(documents), dict(enumerate(ids)))
        except (OSError, ValueError, TypeError, AttributeError, RuntimeError, KeyError):
            log.warning("向量索引缓存无效，重新构建。")
            return None

    def save(self, store) -> None:
        try:
            import faiss

            positions = sorted(store.index_to_docstore_id)
            if positions != list(range(store.index.ntotal)):
                raise ValueError("Incomplete vector/document mapping")
            documents = []
            for position in positions:
                document_id = store.index_to_docstore_id[position]
                document = store.docstore.search(document_id)
                if not isinstance(document, Document):
                    raise ValueError("Invalid cached document")
                documents.append({"id": document_id, "page_content": document.page_content, "metadata": document.metadata})
            index_bytes = faiss.serialize_index(store.index).tobytes()
            document_bytes = json_bytes(documents)
            # 清单最后发布。任何半截数据或错配版本均不能通过校验。
            for name, payload in (
                ("index.faiss", index_bytes),
                ("documents.json", document_bytes),
                ("manifest.json", json_bytes({"identity": self.identity, "index_sha256": sha256(index_bytes), "documents_sha256": sha256(document_bytes)})),
            ):
                atomic_write(self.directory / name, payload)
        except (OSError, ValueError, TypeError, RuntimeError):
            log.warning("向量索引缓存写入失败，继续使用内存索引。")


def _lock_file(handle) -> None:
    deadline = time.monotonic() + 180
    while True:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                # https://docs.python.org/3/library/msvcrt.html#msvcrt.locking
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def _unlock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_UN)
