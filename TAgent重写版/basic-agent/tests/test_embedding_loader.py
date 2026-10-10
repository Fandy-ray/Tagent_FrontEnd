"""嵌入模型先只读本地缓存：断网也能起、也能检索本地教材。离线运行（不真的加载模型）。"""

from __future__ import annotations

import sys
import types

from app.rag import knowledge_base


def install_fake(monkeypatch, fail_local: bool):
    calls = []

    class FakeEmbeddings:
        def __init__(self, model_name, model_kwargs=None):
            calls.append(model_kwargs or {})
            if fail_local and (model_kwargs or {}).get("local_files_only"):
                raise OSError("not cached")

    monkeypatch.setitem(sys.modules, "langchain_huggingface", types.SimpleNamespace(HuggingFaceEmbeddings=FakeEmbeddings))
    return calls


def test_cached_model_loads_without_touching_the_network(monkeypatch):
    calls = install_fake(monkeypatch, fail_local=False)
    knowledge_base._load_default_embeddings()
    assert calls == [{"local_files_only": True}]


def test_falls_back_to_download_only_when_the_cache_really_lacks_the_model(monkeypatch):
    calls = install_fake(monkeypatch, fail_local=True)
    knowledge_base._load_default_embeddings()
    assert calls == [{"local_files_only": True}, {}]


# ====================== 向量索引的磁盘缓存 ======================
from langchain_core.embeddings import Embeddings  # noqa: E402


class CountingEmbeddings(Embeddings):
    """确定性的假嵌入：数被调用了几次，用来判断这次是重建还是读的缓存。"""

    def __init__(self):
        self.documents_embedded = 0

    def embed_documents(self, texts):
        self.documents_embedded += len(texts)
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        return self._vector(text)

    @staticmethod
    def _vector(text):
        return [float((sum(map(ord, text)) * (i + 3)) % 97) / 97.0 for i in range(8)]


def make_kb(tmp_path, embeddings, book="# 排队论\n\n到达率与服务率。\n\n## 仿真\n\n仿真时钟推进。\n", **kwargs):
    from app.rag.knowledge_base import KnowledgeBase

    book_file = tmp_path / "book.md"
    if not book_file.exists() or book_file.read_text(encoding="utf-8") != book:
        book_file.write_text(book, encoding="utf-8")
    kwargs.setdefault("embedding_revision", "test-embedding-v1")
    return KnowledgeBase(knowledge_file=book_file, embeddings=embeddings, index_cache_dir=tmp_path / "cache", **kwargs)


def test_second_start_reads_the_index_instead_of_embedding_the_book_again(tmp_path):
    first = CountingEmbeddings()
    make_kb(tmp_path, first).warm_up()
    assert first.documents_embedded > 0

    second = CountingEmbeddings()
    kb = make_kb(tmp_path, second)
    kb.warm_up()
    assert second.documents_embedded == 0
    context, documents = kb.retrieve("到达率")
    assert documents and ("到达率" in context or "仿真" in context)


def test_a_changed_book_rebuilds_and_preserves_the_old_cache(tmp_path):
    first = make_kb(tmp_path, CountingEmbeddings())
    first.warm_up()
    old_cache = first._index_cache_path()
    again = CountingEmbeddings()
    make_kb(tmp_path, again, book="# 新教材\n\n系统动力学。\n").warm_up()

    assert again.documents_embedded > 0
    assert old_cache.is_dir()
    assert len(list((tmp_path / "cache" / "safe-v3").glob("*/manifest.json"))) == 2


def test_a_corrupt_cache_is_rebuilt_not_fatal(tmp_path):
    initial = make_kb(tmp_path, CountingEmbeddings())
    initial.warm_up()
    entry = initial._index_cache_path()
    (entry / "index.faiss").write_bytes(b"not an index")

    rebuilt = CountingEmbeddings()
    kb = make_kb(tmp_path, rebuilt)
    kb.warm_up()
    # 索引文件坏了照样重建；逐块的向量还在，所以不用再嵌入一遍
    assert rebuilt.documents_embedded == 0
    assert kb.retrieve("仿真")[1]
    assert (entry / "index.faiss").read_bytes() != b"not an index"


def test_first_build_does_not_call_the_missing_cache_invalid(tmp_path, caplog):
    """还没建过缓存是正常情况；以前第一次启动就打一句「缓存无效」，看着像出了故障。"""
    with caplog.at_level("WARNING"):
        make_kb(tmp_path, CountingEmbeddings()).warm_up()
    assert "无效" not in caplog.text

    entry = make_kb(tmp_path, CountingEmbeddings())._index_cache_path()
    (entry / "documents.json").write_bytes(b"[]")
    caplog.clear()
    with caplog.at_level("WARNING"):
        make_kb(tmp_path, CountingEmbeddings()).warm_up()
    assert "无效" in caplog.text  # 真坏了照样要说


def test_no_cache_dir_means_no_files(tmp_path):
    from app.rag.knowledge_base import KnowledgeBase

    book = tmp_path / "book.md"
    book.write_text("# 排队论\n\n到达率。\n", encoding="utf-8")
    KnowledgeBase(knowledge_file=book, embeddings=CountingEmbeddings()).warm_up()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["book.md"]


# ====================== 逐块的向量缓存：重建时只嵌入新块 ======================


def test_editing_the_book_only_embeds_the_changed_chunks(tmp_path):
    book = "# 排队论\n\n到达率与服务率。\n\n## 仿真\n\n仿真时钟推进。\n"
    make_kb(tmp_path, CountingEmbeddings(), book=book).warm_up()

    changed = CountingEmbeddings()
    make_kb(tmp_path, changed, book=book + "\n## 新增一节\n\n输出分析与置信区间。\n").warm_up()
    assert changed.documents_embedded == 1  # 只有新加的那一块


def test_a_broken_vector_memo_means_embedding_everything_not_a_crash(tmp_path):
    make_kb(tmp_path, CountingEmbeddings()).warm_up()
    [memo] = (tmp_path / "cache" / "safe-v3").glob(".chunk-vectors-*.npz")
    memo.write_bytes(b"broken")
    [entry] = (tmp_path / "cache" / "safe-v3").glob("*/index.faiss")
    entry.write_bytes(b"broken")  # 只损坏明确文件，逼它重建；不删除目录

    again = CountingEmbeddings()
    kb = make_kb(tmp_path, again)
    kb.warm_up()
    assert again.documents_embedded > 0 and kb.retrieve("仿真")[1]


def test_the_vector_memo_keeps_only_the_chunks_in_use(tmp_path):
    import numpy as np

    make_kb(tmp_path, CountingEmbeddings(), book="# 甲\n\n第一版内容。\n").warm_up()
    make_kb(tmp_path, CountingEmbeddings(), book="# 乙\n\n第二版内容。\n").warm_up()
    [memo] = (tmp_path / "cache" / "safe-v3").glob(".chunk-vectors-*.npz")
    with np.load(memo) as data:
        assert len(data["keys"]) == 1  # 第一版的块没留下，不会越攒越多


# ====================== 第一次推理必须单线程 ======================


def test_the_first_inference_runs_alone_before_concurrent_searches(tmp_path):
    """16 路检索同时成为进程里第一次推理时，嵌入模型会段错误或卡死（实测）。

    ensure_index 要在锁里先单独推理一次；先到的检索都在锁外排队，等它做完才并发。
    """
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    events = []
    lock = threading.Lock()
    in_flight = [0]

    class WatchingEmbeddings(CountingEmbeddings):
        def embed_query(self, text):
            with lock:
                in_flight[0] += 1
                events.append((text, in_flight[0]))
            time.sleep(0.02)
            with lock:
                in_flight[0] -= 1
            return super().embed_query(text)

    kb = make_kb(tmp_path, WatchingEmbeddings())
    barrier = threading.Barrier(16)

    def search(i):
        barrier.wait()
        return kb.search(f"第{i}问", k=1)

    with ThreadPoolExecutor(16) as pool:
        assert all(pool.map(search, range(16)))

    first_text, concurrency_at_first = events[0]
    assert first_text == "预热" and concurrency_at_first == 1
    assert [text for text, _ in events].count("预热") == 1  # 只预热一次
    assert len(events) == 17


def test_warm_up_alone_does_the_first_inference(tmp_path):
    """启动时的预热就把第一次推理做掉，不留给学生的第一个问题。"""
    seen = []

    class Recording(CountingEmbeddings):
        def embed_query(self, text):
            seen.append(text)
            return super().embed_query(text)

    make_kb(tmp_path, Recording()).warm_up()
    assert seen == ["预热"]


def test_unknown_model_revision_never_reuses_disk_vectors(tmp_path):
    first = CountingEmbeddings()
    make_kb(tmp_path, first, embedding_revision=None).warm_up()
    second = CountingEmbeddings()
    make_kb(tmp_path, second, embedding_revision=None).warm_up()
    assert first.documents_embedded > 0 and second.documents_embedded > 0
    assert not (tmp_path / "cache").exists()


def test_model_revision_change_invalidates_both_index_and_vector_memo(tmp_path):
    make_kb(tmp_path, CountingEmbeddings()).warm_up()
    changed = CountingEmbeddings()
    make_kb(tmp_path, changed, embedding_revision="test-embedding-v2").warm_up()
    assert changed.documents_embedded > 0
    assert len(list((tmp_path / "cache" / "safe-v3").glob("*/manifest.json"))) == 2
    assert len(list((tmp_path / "cache" / "safe-v3").glob(".chunk-vectors-*.npz"))) == 2


def test_legacy_cache_is_not_loaded_or_deleted(tmp_path):
    legacy = tmp_path / "cache" / "legacy"
    legacy.mkdir(parents=True)
    original = b"not trusted pickle"
    (legacy / "index.pkl").write_bytes(original)
    (legacy / "index.faiss").write_bytes(b"old index")
    kb = make_kb(tmp_path, CountingEmbeddings())
    kb.warm_up()
    assert (legacy / "index.pkl").read_bytes() == original
    assert (legacy / "index.faiss").read_bytes() == b"old index"
    assert not list(kb._index_cache_path().glob("*.pkl"))


def test_unwritable_cache_location_falls_back_to_memory(tmp_path):
    (tmp_path / "cache").write_bytes(b"file, not directory")
    kb = make_kb(tmp_path, CountingEmbeddings())
    assert kb.retrieve("仿真")[1]
    assert (tmp_path / "cache").read_bytes() == b"file, not directory"


def test_mapping_corruption_is_rejected_even_with_a_matching_checksum(tmp_path):
    import hashlib
    import json

    kb = make_kb(tmp_path, CountingEmbeddings())
    kb.warm_up()
    directory = kb._index_cache_path()
    entries = json.loads((directory / "documents.json").read_text(encoding="utf-8"))
    entries[0]["metadata"]["h1"] = "wrong citation"
    payload = json.dumps(entries).encode("utf-8")
    (directory / "documents.json").write_bytes(payload)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["documents_sha256"] = hashlib.sha256(payload).hexdigest()
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    again = make_kb(tmp_path, CountingEmbeddings())
    again.warm_up()
    assert all(d.metadata.get("h1") != "wrong citation" for d in again.retrieve("到达率")[1])


def test_repeated_retrieval_is_shared_and_keeps_citations_isolated(tmp_path):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    class Watching(CountingEmbeddings):
        queries = 0

        def embed_query(self, text):
            self.queries += 1
            time.sleep(0.02)
            return super().embed_query(text)

    embeddings = Watching()
    kb = make_kb(tmp_path, embeddings)
    kb.warm_up()
    barrier = threading.Barrier(10)

    def retrieve(_):
        barrier.wait()
        return kb.retrieve("到达率")

    with ThreadPoolExecutor(10) as pool:
        replies = list(pool.map(retrieve, range(10)))
    assert embeddings.queries == 2  # 一次单线程预热，一次同题检索
    replies[0][1][0].metadata["h1"] = "changed by caller"
    assert replies[1][1][0].metadata["h1"] != "changed by caller"
    assert kb.retrieve("到达率")[1][0].metadata["h1"] != "changed by caller"


def test_query_cache_ttl_capacity_identity_and_disable(monkeypatch):
    from langchain_core.documents import Document
    from app.rag import query_result_cache

    now = [100.0]
    monkeypatch.setattr(query_result_cache.time, "monotonic", lambda: now[0])
    calls = []

    def load():
        calls.append(1)
        return [Document(page_content="doc", metadata={"reference": {"page": 2}})]

    cache = query_result_cache.QueryResultCache(max_entries=1, ttl_seconds=60)
    cache.get_or_load("a", identity="v1", k=4, load=load)
    cache.get_or_load("a", identity="v1", k=4, load=load)
    assert len(calls) == 1
    cache.get_or_load("b", identity="v1", k=4, load=load)
    assert len(cache._entries) == 1
    cache.get_or_load("a", identity="v1", k=4, load=load)
    cache.get_or_load("a", identity="v2", k=4, load=load)
    cache.get_or_load("a", identity="v2", k=3, load=load)
    now[0] += 60
    cache.get_or_load("a", identity="v2", k=3, load=load)
    assert len(calls) == 6
    cache.enabled = False
    cache.get_or_load("a", identity="v2", k=3, load=load)
    cache.get_or_load("a", identity="v2", k=3, load=load)
    assert len(calls) == 8


def test_failed_shared_query_wakes_waiters_and_is_not_cached():
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from app.rag.query_result_cache import QueryResultCache
    from langchain_core.documents import Document

    cache = QueryResultCache(max_entries=2)
    barrier = threading.Barrier(5)
    calls = []

    def fail():
        calls.append(1)
        time.sleep(0.05)
        raise ValueError("retrieval failed")

    def retrieve(_):
        barrier.wait()
        try:
            cache.get_or_load("q", identity="v1", k=4, load=fail)
        except ValueError:
            return "failed"

    with ThreadPoolExecutor(5) as pool:
        assert list(pool.map(retrieve, range(5))) == ["failed"] * 5
    assert len(calls) == 1 and not cache._inflight and not cache._entries
    assert cache.get_or_load("q", identity="v1", k=4, load=lambda: [Document(page_content="retry")])[0].page_content == "retry"


def test_retrieval_cache_configuration_is_wired_and_disk_disable_wins(tmp_path, monkeypatch):
    from app.config import AgentConfig
    from app.container import build_knowledge_base

    monkeypatch.setenv("RAG_INDEX_CACHE_DIR", str(tmp_path / "独立缓存"))
    monkeypatch.setenv("TAGENT_VECTOR_CACHE", "1")
    monkeypatch.setenv("RAG_RETRIEVAL_CACHE_MAX_ENTRIES", "7")
    monkeypatch.setenv("RAG_RETRIEVAL_CACHE_TTL_SECONDS", "12")
    monkeypatch.setenv("RAG_RETRIEVAL_CACHE", "0")
    monkeypatch.setenv("KNOWLEDGE_SOURCE", "local")
    settings = AgentConfig.from_env()
    kb = build_knowledge_base(settings)
    assert kb.index_cache_dir == tmp_path / "独立缓存"
    assert not kb._retrieval_cache.enabled
    assert kb._retrieval_cache.max_entries == 7 and kb._retrieval_cache.ttl_seconds == 12
    monkeypatch.setenv("TAGENT_VECTOR_CACHE", "0")
    assert AgentConfig.from_env().vector_cache_dir is None


def test_reordered_memo_keys_are_rejected_before_rebuilding_the_index(tmp_path):
    import numpy as np

    kb = make_kb(tmp_path, CountingEmbeddings())
    kb.warm_up()
    memo = kb._vector_memo_path()
    with np.load(memo, allow_pickle=False) as saved:
        data = {name: saved[name] for name in saved.files}
    assert len(data["keys"]) > 1
    data["keys"] = data["keys"][::-1]
    with memo.open("wb") as handle:
        np.savez(handle, **data)  # 合法NPZ、CRC正确；但文本与向量的对应顺序被换了
    (kb._index_cache_path() / "index.faiss").write_bytes(b"force index rebuild")
    embeddings = CountingEmbeddings()
    again = make_kb(tmp_path, embeddings)
    again.warm_up()
    assert embeddings.documents_embedded == len(again.chunks())
    assert again.retrieve("仿真")[1]
