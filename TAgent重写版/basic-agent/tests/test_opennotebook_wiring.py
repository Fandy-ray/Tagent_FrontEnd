import json
import os
from unittest.mock import patch

from app.config import AgentConfig, normalize_notebook_url
from app.container import Services, build_knowledge_base
from app.rag.composite_kb import CompositeKnowledgeBase
from app.rag.opennotebook_kb import OpenNotebookKnowledgeBase


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.reason_phrase = "OK"
        self.headers = headers or {"content-type": "application/json"}
        if isinstance(payload, (dict, list)):
            self.text = json.dumps(payload, ensure_ascii=False)
        else:
            self.text = str(payload)
        self.content = self.text.encode()

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method.upper(), path, kwargs.get("json")))
        response = self.routes.get((method.upper(), path))
        if response is None:
            return FakeResponse({"detail": "not found"}, 404)
        return response


class FakeSource:
    def __init__(self, name, text, fail=False):
        self.name = name
        self.text = text
        self.fail = fail

    def describe(self):
        return {"kind": self.name}

    def warm_up(self):
        if self.fail:
            raise RuntimeError(f"{self.name} down")

    def retrieve(self, query, notebook_ids=None):
        if self.fail:
            raise RuntimeError(f"{self.name} down")
        doc = type("Doc", (), {"page_content": f"{self.name}:{query}:{self.text}"})()
        return f"{self.name}:{self.text}", [doc]

    def search(self, query, *, k=3, notebook_ids=None):
        if self.fail:
            raise RuntimeError(f"{self.name} down")
        return [type("Doc", (), {"page_content": self.text})()]

    def chunks(self, notebook_ids=None):
        if self.fail:
            raise RuntimeError(f"{self.name} down")
        return [type("Doc", (), {"page_content": self.text, "metadata": {"h1": self.name}})()]

    def sample_exam_context(self, topic=None, notebook_ids=None):
        if self.fail:
            raise RuntimeError(f"{self.name} down")
        return f"{self.name}:{topic or 'all'}:{self.text}"


def test_opennotebook_retrieve_and_chunks():
    client = FakeClient(
        {
            ("POST", "/api/search"): FakeResponse(
                {
                    "results": [
                        {"title": "排队论", "content": "到达率 λ，服务率 μ。"},
                        {"title": "仿真", "text": "离散事件仿真按事件推进。"},
                    ]
                }
            ),
            ("GET", "/api/notes"): FakeResponse(
                [{"title": "笔记A", "content": "笔记正文"}]
            ),
            ("GET", "/api/sources"): FakeResponse(
                {"sources": [{"name": "教材", "full_text": "来源正文"}]}
            ),
        }
    )
    kb = OpenNotebookKnowledgeBase(base_url="http://127.0.0.1:5055", client=client)

    context, documents = kb.retrieve("排队")
    assert "到达率" in context
    assert len(documents) == 2
    assert kb.search("排队", k=2)[0].page_content.startswith("到达率")

    chunks = kb.chunks()
    assert [doc.metadata["h1"] for doc in chunks] == ["笔记A", "教材"]
    assert "到达率" in kb.sample_exam_context("排队")


def test_opennotebook_falls_back_to_text_search():
    client = FakeClient(
        {
            ("POST", "/api/search"): FakeResponse(
                {"detail": "Vector search requires an embedding model."}, 400
            )
        }
    )
    # 第一次 vector 失败后，适配器会改 type=text 再打一次同一路径
    calls = {"n": 0}

    def request(method, path, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse("need embedding", 400)
        return FakeResponse({"results": [{"content": "文本检索命中"}]})

    client.request = request
    kb = OpenNotebookKnowledgeBase(base_url="http://notebook", client=client)
    context, documents = kb.retrieve("仿真")
    assert context == "文本检索命中"
    assert documents[0].page_content == "文本检索命中"


def test_composite_skips_failed_source():
    composite = CompositeKnowledgeBase(
        FakeSource("local", "本地教材"),
        FakeSource("notebook", "笔记", fail=True),
    )
    context, documents = composite.retrieve("延迟")
    assert context.startswith("local:")
    assert documents[0].page_content.startswith("local:")
    assert composite.sample_exam_context("延迟").startswith("local:")
    assert composite.describe()["kind"] == "composite"


def test_composite_warm_up_raises_when_every_source_fails():
    composite = CompositeKnowledgeBase(
        FakeSource("local", "教材", fail=True),
        FakeSource("notebook", "笔记", fail=True),
    )
    try:
        composite.warm_up()
    except RuntimeError as exc:
        assert "所有知识来源预热失败" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_services_warm_up_does_not_kill_process():
    class Boom:
        def warm_up(self):
            raise RuntimeError("所有知识来源预热失败")

    Services(
        chat=None,
        quiz=None,
        exam=None,
        essay=None,
        knowledge_base=Boom(),
        client_factory=None,
    ).warm_up()


def test_build_knowledge_base_respects_source():
    local = build_knowledge_base(AgentConfig())
    assert local.describe()["kind"] == "local"

    notebook = build_knowledge_base(
        AgentConfig(knowledge_source="notebook", notebook_url="http://127.0.0.1:5055")
    )
    assert notebook.describe() == {"kind": "notebook", "url": "http://127.0.0.1:5055"}

    both = build_knowledge_base(
        AgentConfig(knowledge_source="composite", notebook_url="http://127.0.0.1:5055")
    )
    assert both.describe()["kind"] == "composite"
    assert [item["kind"] for item in both.describe()["sources"]] == ["local", "notebook"]


def test_normalize_maps_browser_url_to_rest_api():
    # 8502 是 Streamlit 页面，/api/* 在 5055。抄浏览器地址过来也要能用。
    assert normalize_notebook_url("http://localhost:8502/notebooks") == "http://localhost:5055"
    assert normalize_notebook_url("http://localhost:8502/") == "http://localhost:5055"
    assert normalize_notebook_url("localhost:8502") == "http://localhost:5055"
    assert normalize_notebook_url("https://notes.example.com:8502") == "https://notes.example.com:5055"


def test_normalize_leaves_other_ports_alone():
    assert normalize_notebook_url("http://127.0.0.1:5055") == "http://127.0.0.1:5055"
    assert normalize_notebook_url("http://notebook.internal") == "http://notebook.internal"
    assert normalize_notebook_url("") == ""


def test_normalize_keeps_explicit_api_url_verbatim():
    # 已经明确是接口地址的，哪怕端口就是 8502 也不许改写。
    assert (
        normalize_notebook_url("http://localhost:8502", rewrite_ui_port=False)
        == "http://localhost:8502"
    )


def test_api_url_env_wins_over_browser_url():
    env = {
        "OPEN_NOTEBOOK_API_URL": "http://127.0.0.1:9000",
        "OPEN_NOTEBOOK_URL": "http://localhost:8502/notebooks",
        "KNOWLEDGE_SOURCE": "",
    }
    with patch.dict(os.environ, env, clear=False):
        settings = AgentConfig.from_env()
    assert settings.notebook_url == "http://127.0.0.1:9000"


def test_search_hydrates_note_when_hit_has_no_content():
    client = FakeClient(
        {
            ("POST", "/api/search"): FakeResponse(
                {"results": [{"id": "note:abc", "title": "实验二我要做什么"}]}
            ),
            ("GET", "/api/notes/note:abc"): FakeResponse(
                {"id": "note:abc", "title": "实验二我要做什么", "content": "活动扫描法"}
            ),
        }
    )
    kb = OpenNotebookKnowledgeBase(base_url="http://localhost:8502", client=client)
    context, documents = kb.retrieve("实验")
    assert "活动扫描法" in context
    assert documents[0].metadata["h1"] == "实验二我要做什么"


def test_config_defaults_to_composite_when_notebook_url_set():
    env = {
        "OPEN_NOTEBOOK_API_URL": "",
        "OPEN_NOTEBOOK_URL": "http://localhost:8502/notebooks",
        "OPEN_NOTEBOOK_PASSWORD": "secret",
        "KNOWLEDGE_SOURCE": "",
    }
    with patch.dict(os.environ, env, clear=False):
        settings = AgentConfig.from_env()
    assert settings.knowledge_source == "composite"
    assert settings.notebook_url == "http://localhost:5055"
    assert settings.notebook_token == "secret"


def test_retrieve_keeps_only_selected_notebook():
    client = FakeClient(
        {
            ("GET", "/api/notebooks"): FakeResponse(
                [
                    {"id": "notebook:net", "name": "计算机网络"},
                    {"id": "notebook:test", "name": "测试"},
                ]
            ),
            ("GET", "/api/notes?notebook_id=notebook:net"): FakeResponse(
                [{"id": "note:net1", "title": "实验二", "content": "活动扫描法"}]
            ),
            ("GET", "/api/sources?notebook_id=notebook:net&limit=100"): FakeResponse([]),
            ("GET", "/api/notes/note:net1"): FakeResponse(
                {"id": "note:net1", "title": "实验二", "content": "活动扫描法"}
            ),
            ("POST", "/api/search"): FakeResponse(
                {
                    "results": [
                        {"id": "note:net1", "title": "实验二", "content": "活动扫描法"},
                        {"id": "note:test1", "title": "测试本", "content": "不该出现"},
                    ]
                }
            ),
        }
    )
    kb = OpenNotebookKnowledgeBase(base_url="http://127.0.0.1:5055", client=client)
    context, documents = kb.retrieve("实验", notebook_ids=["notebook:net"])
    assert "活动扫描法" in context
    assert "不该出现" not in context
    assert documents[0].metadata["notebook_id"] == "notebook:net"
    assert documents[0].metadata["notebook_name"] == "计算机网络"


def test_composite_skips_local_when_notebook_selected():
    composite = CompositeKnowledgeBase(
        FakeSource("local", "本地教材"),
        FakeSource("notebook", "只看笔记"),
    )
    context, _documents = composite.retrieve("延迟", notebook_ids=["notebook:net"])
    assert context.startswith("notebook:")
    assert "本地教材" not in context


def test_config_stays_local_without_notebook_url():
    env = {
        "OPEN_NOTEBOOK_API_URL": "",
        "OPEN_NOTEBOOK_URL": "",
        "KNOWLEDGE_SOURCE": "composite",
    }
    with patch.dict(os.environ, env, clear=False):
        settings = AgentConfig.from_env()
    assert settings.knowledge_source == "local"
