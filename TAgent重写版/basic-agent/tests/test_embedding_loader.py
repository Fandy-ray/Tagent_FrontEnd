"""嵌入模型先只读本地缓存：断网也能起、也能检索本地教材。离线运行（不真的加载模型）。"""

from __future__ import annotations

import shutil
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


def make_kb(tmp_path, embeddings, book="# 排队论\n\n到达率与服务率。\n\n## 仿真\n\n仿真时钟推进。\n"):
    from app.rag.knowledge_base import KnowledgeBase

    book_file = tmp_path / "book.md"
    if not book_file.exists() or book_file.read_text(encoding="utf-8") != book:
        book_file.write_text(book, encoding="utf-8")
    return KnowledgeBase(knowledge_file=book_file, embeddings=embeddings, index_cache_dir=tmp_path / "cache")


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


def test_a_changed_book_rebuilds_and_drops_the_old_cache(tmp_path):
    make_kb(tmp_path, CountingEmbeddings()).warm_up()
    again = CountingEmbeddings()
    make_kb(tmp_path, again, book="# 新教材\n\n系统动力学。\n").warm_up()

    assert again.documents_embedded > 0
    assert len([p for p in (tmp_path / "cache").iterdir() if not p.name.startswith(".")]) == 1


def test_a_corrupt_cache_is_rebuilt_not_fatal(tmp_path):
    make_kb(tmp_path, CountingEmbeddings()).warm_up()
    [entry] = [p for p in (tmp_path / "cache").iterdir() if not p.name.startswith(".")]
    (entry / "index.faiss").write_bytes(b"not an index")

    rebuilt = CountingEmbeddings()
    kb = make_kb(tmp_path, rebuilt)
    kb.warm_up()
    # 索引文件坏了照样重建；逐块的向量还在，所以不用再嵌入一遍
    assert rebuilt.documents_embedded == 0
    assert kb.retrieve("仿真")[1]
    assert (entry / "index.faiss").read_bytes() != b"not an index"


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
    [memo] = (tmp_path / "cache").glob(".chunk-vectors-*.npz")
    memo.write_bytes(b"broken")
    [entry] = [p for p in (tmp_path / "cache").iterdir() if not p.name.startswith(".")]
    shutil.rmtree(entry)  # 逼它重建

    again = CountingEmbeddings()
    kb = make_kb(tmp_path, again)
    kb.warm_up()
    assert again.documents_embedded > 0 and kb.retrieve("仿真")[1]


def test_the_vector_memo_keeps_only_the_chunks_in_use(tmp_path):
    import numpy as np

    make_kb(tmp_path, CountingEmbeddings(), book="# 甲\n\n第一版内容。\n").warm_up()
    make_kb(tmp_path, CountingEmbeddings(), book="# 乙\n\n第二版内容。\n").warm_up()
    [memo] = (tmp_path / "cache").glob(".chunk-vectors-*.npz")
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
