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
