"""答疑返回出处：教材第几章第几页、哪篇论文、笔记本里哪条来源，随回答一起给前端。"""

from __future__ import annotations

import json
import tempfile
import types
from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.container import Services
from app.factory import create_app
from app.rag.citations import (
    SNIPPET_CHARS,
    annotate_book_locations,
    citations_from_documents,
    split_reference_source,
)
from app.rag.knowledge_base import KnowledgeBase
from app.rag.references import reference_documents
from app.repository.learning_store import LearningStore
from app.repository.provider_repository import ModelProviderRegistry
from app.service.chat_service import ChatService

BOOK = Path(__file__).resolve().parents[1] / "book1.md"


def paper(text="M/M/1 排队系统的稳态分析。", **metadata):
    return Document(
        page_content=f"{text}\n——摘自《呼叫中心排班》（系统仿真学报, 2022, 34(7): 1651-1661）",
        metadata={
            "h1": "参考文献",
            "h2": "呼叫中心排班",
            "source": "reference",
            "file": "callcenter.md",
            "parent": "callcenter.md#0",
            "citation": "系统仿真学报, 2022, 34(7): 1651-1661",
            "href": "https://www.china-simulation.com/CN/abstract/1.shtml",
            **metadata,
        },
    )


def book(text="到达率与服务率。", **metadata):
    return Document(page_content=text, metadata={"h1": "", "h2": "", "h3": "总结", "source": "textbook", **metadata})


def notebook(ident="source:abc", **metadata):
    return Document(
        page_content="笔记本里的一段",
        metadata={
            "id": ident,
            "h1": "第三章讲义",
            "source": "opennotebook",
            "notebook_id": "notebook:1",
            "notebook_name": "系统仿真",
            **metadata,
        },
    )


# ====================== 三种材料 ======================


def test_each_kind_of_material_gets_its_own_fields():
    found = citations_from_documents([book(chapter=2, page=26), paper(), notebook()])
    assert found[0] == {
        "id": "textbook:2:26",
        "kind": "textbook",
        "title": "课程教材",
        "chapter": 2,
        "page": 26,
        "snippet": "到达率与服务率。",
    }
    assert found[1]["kind"] == "paper"
    assert found[1]["title"] == "呼叫中心排班"
    assert found[1]["citation"] == "系统仿真学报, 2022, 34(7): 1651-1661"
    assert found[1]["href"].startswith("https://www.china-simulation.com/")
    # 块末尾的「——摘自」是给模型看的，片段里不重复
    assert found[1]["snippet"] == "M/M/1 排队系统的稳态分析。"
    assert found[2] == {
        "id": "source:abc",
        "kind": "notebook",
        "source_id": "source:abc",
        "title": "第三章讲义",
        "notebook_id": "notebook:1",
        "notebook_name": "系统仿真",
        "snippet": "笔记本里的一段",
    }


def test_same_page_or_same_paper_is_listed_once_in_retrieval_order():
    found = citations_from_documents(
        [
            paper(parent="callcenter.md#3"),
            book(chapter=2, page=26),
            paper(text="另一块", parent="callcenter.md#7"),
            book(text="同一页的另一块", chapter=2, page=26),
            book(chapter=2, page=27),
        ]
    )
    assert [item["id"] for item in found] == ["reference:callcenter.md", "textbook:2:26", "textbook:2:27"]


def test_textbook_chunk_without_a_location_still_counts():
    found = citations_from_documents([book()])
    assert found[0]["kind"] == "textbook"
    assert "chapter" not in found[0] and "page" not in found[0]


def test_only_web_links_are_passed_on():
    assert citations_from_documents([paper(href="javascript:alert(1)")])[0]["href"] == ""
    assert citations_from_documents([paper(href="")])[0]["href"] == ""


def test_long_snippets_are_cut_and_whitespace_folded():
    snippet = citations_from_documents([book(text="排队\n\n  论" * 200)])[0]["snippet"]
    assert len(snippet) == SNIPPET_CHARS + 1 and snippet.endswith("…")
    assert "\n" not in snippet and "  " not in snippet


def test_material_of_unknown_kind_is_not_passed_off_as_the_textbook():
    unknown = Document(page_content="来路不明的一段", metadata={"h1": "OpenNotebook"})
    assert citations_from_documents([unknown, book(chapter=1, page=3)]) == citations_from_documents(
        [book(chapter=1, page=3)]
    )


def test_nothing_retrieved_means_no_citations():
    assert citations_from_documents([]) == []
    assert citations_from_documents(None) == []


# ====================== 论文的出处 ======================


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            "系统仿真学报, 2022, 34(7): 1651-1661。https://www.china-simulation.com/CN/abstract/1.shtml",
            ("系统仿真学报, 2022, 34(7): 1651-1661", "https://www.china-simulation.com/CN/abstract/1.shtml"),
        ),
        ("系统仿真学报, 2016, 28(1): 129-138", ("系统仿真学报, 2016, 28(1): 129-138", "")),
        ("https://example.com/a。", ("", "https://example.com/a")),
        ("自己写的。补充说明", ("自己写的", "")),
        ("", ("", "")),
    ],
)
def test_split_reference_source(source, expected):
    assert split_reference_source(source) == expected


def test_reference_chunks_carry_citation_and_link(tmp_path):
    (tmp_path / "callcenter.md").write_text(
        "# 呼叫中心排班\n\n> 来源：系统仿真学报, 2022, 34(7): 1651-1661。https://www.china-simulation.com/x\n\n"
        + "排队论研究随机服务系统。" * 60,
        encoding="utf-8",
    )
    (tmp_path / "mine.md").write_text("# 自己整理的\n\n" + "仿真时钟推进。" * 80, encoding="utf-8")
    by_file = {doc.metadata["file"]: doc for doc in reference_documents(tmp_path)}
    assert by_file["callcenter.md"].metadata["citation"] == "系统仿真学报, 2022, 34(7): 1651-1661"
    assert by_file["callcenter.md"].metadata["href"] == "https://www.china-simulation.com/x"
    assert by_file["callcenter.md"].page_content.endswith("——摘自《呼叫中心排班》（系统仿真学报, 2022, 34(7): 1651-1661）")
    assert by_file["mine.md"].metadata["citation"] == ""
    assert by_file["mine.md"].metadata["href"] == ""


# ====================== 教材定位 ======================


SAMPLE_BOOK = """--- Page 1 ---
空白封面

--- Page 2 ---
### **章节标题：第1章 概述**
系统仿真是什么。

--- Page 3 ---
### **二、图2.1：示意图**
图号不是小节号。
#### 步长为 0.01 的情况
四级标题里的数值也不是。

--- Page 21 ---
## **2.3 分布假设与检验**
卡方检验。
### **标题：2.4 随机数**
线性同余法。
"""


def test_book_chunks_get_printed_page_and_chapter():
    body = [
        Document(page_content="系统仿真是什么。", metadata={}),
        Document(page_content="图号不是小节号。", metadata={}),
        Document(page_content="四级标题里的数值也不是。", metadata={}),
        Document(page_content="卡方检验。", metadata={}),
        Document(page_content="线性同余法。", metadata={}),
    ]
    annotate_book_locations(SAMPLE_BOOK, body)
    # 页标记比书上印的页码大 1；图号、四级标题里的小数都不改章号
    assert [(d.metadata.get("chapter"), d.metadata.get("page")) for d in body] == [
        (1, 1),
        (1, 2),
        (1, 2),
        (2, 20),
        (2, 20),
    ]


def test_cover_page_and_unfindable_chunks_get_no_location():
    cover = Document(page_content="空白封面", metadata={})
    missing = Document(page_content="原文里没有这句", metadata={})
    annotate_book_locations(SAMPLE_BOOK, [cover, missing])
    assert cover.metadata == missing.metadata == {"source": "textbook"}


def test_repeated_text_is_located_in_reading_order():
    text = "--- Page 5 ---\n总结\n\n--- Page 9 ---\n总结\n"
    first, second = Document(page_content="总结", metadata={}), Document(page_content="总结", metadata={})
    annotate_book_locations(text, [first, second])
    assert (first.metadata["page"], second.metadata["page"]) == (4, 8)


@pytest.mark.skipif(not BOOK.exists(), reason="没有教材")
def test_real_textbook_is_located_chapter_by_chapter():
    chunks = KnowledgeBase._build_text_database(BOOK)
    assert all(c.metadata["source"] == "textbook" for c in chunks)
    located = [c for c in chunks if "page" in c.metadata and "chapter" in c.metadata]
    assert len(located) >= len(chunks) * 0.99
    pages = [c.metadata["page"] for c in located]
    chapters = [c.metadata["chapter"] for c in located]
    assert pages == sorted(pages)
    assert chapters == sorted(chapters)  # 2026-10-08 实测 1→9 章依次出现，没有回跳
    assert set(chapters) == set(range(1, 10))


# ====================== 答疑接口 ======================


class KB:
    def retrieve(self, query, notebook_ids=None):
        return "材料", [book(chapter=3, page=70), paper()]


class Model:
    def stream(self, messages):
        yield types.SimpleNamespace(content="欧拉法", response_metadata={})
        yield types.SimpleNamespace(content="", response_metadata={"finish_reason": "stop"})

    def invoke(self, messages):
        return types.SimpleNamespace(content="欧拉法")


class Factory:
    def get(self, _provider, **_kwargs):
        return Model()


PROVIDER = types.SimpleNamespace(served_model_id="m")
QUESTION = [{"role": "user", "content": "什么是欧拉法？"}]


def test_stream_hands_over_citations_before_the_first_words():
    events = []
    service = ChatService(KB(), Factory())
    for token, _reason in service.stream_answer(QUESTION, PROVIDER, on_citations=lambda c: events.append(c)):
        events.append(token)
    assert [c["kind"] for c in events[0]] == ["textbook", "paper"]
    assert events[1:] == ["欧拉法", ""]


def test_non_stream_answer_returns_citations():
    result = ChatService(KB(), Factory()).answer(QUESTION, PROVIDER)
    assert [c["id"] for c in result["citations"]] == ["textbook:3:70", "reference:callcenter.md"]


@pytest.fixture
def client(tmp_path):
    registry = ModelProviderRegistry(Path(tempfile.mkdtemp()) / "providers.json")
    registry.create_provider(
        {
            "name": "m",
            "served_model_id": "m",
            "base_url": "http://127.0.0.1:9/v1",
            "upstream_model": "u",
            "auth_mode": "none",
            "api_key": "",
            "enabled": True,
        }
    )
    store = LearningStore(tmp_path / "tagent.sqlite3")
    services = Services(
        chat=ChatService(KB(), Factory()),
        quiz=None,
        exam=None,
        essay=None,
        knowledge_base=None,
        client_factory=None,
        store=store,
    )
    app = create_app({"TESTING": True, "AGENT_ADMIN_TOKEN": "t"}, registry=registry, services=services)
    yield app.test_client()
    store.close()


def frames(body: str) -> list:
    return [
        json.loads(line[5:])
        for line in body.splitlines()
        if line.startswith("data:") and line[5:].strip() != "[DONE]"
    ]


def test_streamed_reply_sends_one_citation_frame_before_the_text(client):
    body = client.post(
        "/v1/chat/completions", json={"model": "m", "stream": True, "messages": QUESTION}
    ).get_data(as_text=True)
    sent = frames(body)
    with_citations = [i for i, frame in enumerate(sent) if "citations" in frame]
    with_text = [i for i, frame in enumerate(sent) if frame["choices"][0]["delta"].get("content")]
    assert len(with_citations) == 1
    assert with_citations[0] < with_text[0]
    frame = sent[with_citations[0]]
    # 仍是一帧合法的 OpenAI chunk：delta 为空，别的客户端照常跳过
    assert frame["object"] == "chat.completion.chunk"
    assert frame["choices"][0]["delta"] == {}
    assert [c["kind"] for c in frame["citations"]] == ["textbook", "paper"]
    assert "".join(f["choices"][0]["delta"].get("content", "") for f in sent) == "欧拉法"


def test_plain_json_reply_carries_citations(client):
    payload = client.post(
        "/v1/chat/completions", json={"model": "m", "stream": False, "messages": QUESTION}
    ).get_json()
    assert payload["choices"][0]["message"]["content"] == "欧拉法"
    assert [c["id"] for c in payload["citations"]] == ["textbook:3:70", "reference:callcenter.md"]


def test_rag_query_carries_citations(client):
    payload = client.post("/rag/query", json={"model": "m", "user_question": "什么是欧拉法？"}).get_json()
    assert [c["kind"] for c in payload["data"]["citations"]] == ["textbook", "paper"]
