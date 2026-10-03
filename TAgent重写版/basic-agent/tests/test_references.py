"""参考文献：抽文字、并进本地知识库、启动时下载。全部离线（下载用替身，不连期刊官网）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest
from langchain_core.embeddings import Embeddings

from app.rag.knowledge_base import KnowledgeBase
from app.rag.references import (
    Reference,
    clean_paper_text,
    load_manifest,
    parse_reference_markdown,
    reference_documents,
    reference_markdown,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import fetch_references  # noqa: E402


BODY = "排队论研究随机到达与随机服务的系统。" * 30  # 够 MIN_TEXT_CHARS


# ====================== 抽文字 ======================


def page(*lines: str) -> str:
    return "\n".join(lines)


HEADER = ("第 34 卷第 7 期", "2022 年 7 月", "V ol. 34 No. 7", "系统仿真学报", "http: // www.china-simulation.com")


def test_running_headers_doubled_bold_and_citation_marks_are_removed():
    pages = [
        page("系统仿真学报系统仿真学报©", *HEADER, "摘要摘要：：针对呼叫中心", "进行联合排班研究。",
             "中图分类号：N945 文献标志码：A", "DOI: 10.16182/x",
             "Abstract: A joint shift scheduling method is studied for call center with delay information"),
        page(*HEADER, "0", "引言引言", "仿真技术近似待优化的度量", "指标[5]。Atlason 等", "[7-8]", "利用仿真方法。", "•• 1659"),
        page(*HEADER, "1 模型模型", "到达过程服从泊松分布。", "收稿日期：2021-03-31", "E-mail：someone@example.com"),
    ]
    text = clean_paper_text(pages)

    assert "第 34 卷" not in text and "系统仿真学报" not in text and "china-simulation" not in text
    assert "摘要：针对呼叫中心进行联合排班研究。" in text  # 加粗重复去掉、折行接回
    assert "中图分类号" not in text and "DOI" not in text and "收稿日期" not in text and "E-mail" not in text
    assert "Abstract" not in text  # 中文论文里的英文摘要
    assert "[5]" not in text and "[7-8]" not in text and "1659" not in text
    assert "\n引言\n" in f"\n{text}\n"  # 「0」被当页码去掉后，「引言」仍单独成段
    assert "仿真技术近似待优化的度量指标。" in text
    assert "\n\n1 模型\n\n" in text


def test_the_reference_list_at_the_end_is_cut_off():
    body = [f"第{i}句正文。" for i in range(20)]
    pages = [page(*body), page("5 结论", "结论正文。", "参考文献参考文献：：", "[1] 某某. 某文[J]. 2018.")]
    text = clean_paper_text(pages)
    assert "结论正文。" in text
    assert "某文" not in text and "参考文献" not in text


def test_an_english_body_paper_keeps_its_english_text():
    english = "The norms based on the design of urban roads in China are mainly the specifications"
    pages = [page("摘要：信号控制交叉口进口道存在掉头需求。", english, english + " again"),
             page(english + " three", english + " four", "References", "[1] Some reference title here, 2018.")]
    text = clean_paper_text(pages)
    assert "The norms based on the design" in text
    assert "Some reference title" not in text


# ====================== .md 的题目与出处 ======================


def test_markdown_header_round_trip():
    ref = Reference(key="k", title="某篇论文", citation="系统仿真学报, 2022, 34(7): 1-2", page="https://example.com/a", pdf="")
    title, citation, body = parse_reference_markdown(reference_markdown(ref, BODY), "k")
    assert title == "某篇论文"
    assert citation.startswith("系统仿真学报, 2022, 34(7): 1-2")
    assert body == BODY


def test_markdown_without_header_uses_the_file_name():
    title, citation, body = parse_reference_markdown(BODY, "my-notes")
    assert (title, citation, body) == ("my-notes", "", BODY)


def test_reference_chunks_carry_the_paper_title(tmp_path):
    ref = Reference(key="k", title="某篇论文", citation="系统仿真学报, 2022, 34(7): 1-2", page="", pdf="")
    (tmp_path / "k.md").write_text(reference_markdown(ref, BODY), encoding="utf-8")
    (tmp_path / "README.md").write_text(BODY, encoding="utf-8")  # 说明文件不算论文
    (tmp_path / ".k.md.123.tmp").write_text(BODY, encoding="utf-8")  # 写到一半的临时文件不算
    (tmp_path / "short.md").write_text("太短", encoding="utf-8")  # 抽不出正文的不算
    (tmp_path / "k.pdf").write_bytes(b"%PDF-1.4")  # PDF 由下载脚本先抽成 .md，知识库不直接读

    documents = reference_documents(tmp_path)
    assert documents and {d.metadata["file"] for d in documents} == {"k.md"}
    assert all(d.page_content.endswith("\n——摘自《某篇论文》（系统仿真学报, 2022, 34(7): 1-2）") for d in documents)
    # 标签在末尾：嵌入模型只读前 128 个字，开头留给正文
    assert not any(d.page_content.startswith("——摘自") for d in documents)
    assert all(d.metadata["h2"] == "某篇论文" and d.metadata["source"] == "reference" for d in documents)


def test_no_directory_means_no_reference_chunks(tmp_path):
    assert reference_documents(None) == []
    assert reference_documents(tmp_path / "missing") == []


# ====================== 并进本地知识库 ======================


class FakeEmbeddings(Embeddings):
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


def make_kb(tmp_path, embeddings, *, references=True):
    book = tmp_path / "book.md"
    if not book.exists():
        book.write_text("# 排队论\n\n到达率与服务率。\n\n## 仿真\n\n仿真时钟推进。\n", encoding="utf-8")
    refs = tmp_path / "refs"
    refs.mkdir(exist_ok=True)
    return KnowledgeBase(
        knowledge_file=book,
        embeddings=embeddings,
        index_cache_dir=tmp_path / "cache",
        references_dir=refs if references else None,
    )


def add_paper(tmp_path, key="paper", body=BODY):
    ref = Reference(key=key, title=f"论文{key}", citation="系统仿真学报, 2022", page="", pdf="")
    (tmp_path / "refs" / f"{key}.md").write_text(reference_markdown(ref, body), encoding="utf-8")


def test_papers_are_indexed_alongside_the_book(tmp_path):
    kb = make_kb(tmp_path, FakeEmbeddings())
    add_paper(tmp_path)
    chunks = kb.ensure_index()
    assert any(c.metadata.get("source") == "reference" for c in chunks)
    assert any(c.metadata.get("h1") == "排队论" for c in chunks)
    assert kb.describe()["references"] == 1


def test_adding_or_changing_a_paper_rebuilds_the_index_once(tmp_path):
    first = FakeEmbeddings()
    make_kb(tmp_path, first).warm_up()

    add_paper(tmp_path)
    second = FakeEmbeddings()
    make_kb(tmp_path, second).warm_up()
    assert second.documents_embedded > 0  # 新加了论文：重建

    third = FakeEmbeddings()
    make_kb(tmp_path, third).warm_up()
    assert third.documents_embedded == 0  # 没变：走缓存

    add_paper(tmp_path, body=BODY + "又补了一段。" * 50)
    fourth = FakeEmbeddings()
    make_kb(tmp_path, fourth).warm_up()
    assert fourth.documents_embedded > 0  # 改了内容：重建


def test_turning_references_off_keeps_the_old_cache_key(tmp_path):
    """TAGENT_REFERENCES=0 时缓存键和没有这个功能之前一样：老的索引缓存照样能用。"""
    import hashlib

    from app.rag.knowledge_base import EMBEDDING_MODEL, INDEX_CACHE_FORMAT

    kb = make_kb(tmp_path, FakeEmbeddings(), references=False)
    add_paper(tmp_path)
    digest = hashlib.sha256()
    digest.update(INDEX_CACHE_FORMAT.encode())
    digest.update(EMBEDDING_MODEL.encode())
    digest.update(kb.knowledge_file.read_bytes())
    assert kb._index_cache_path() == tmp_path / "cache" / digest.hexdigest()[:16]
    assert not any(c.metadata.get("source") == "reference" for c in kb.ensure_index())


# ====================== 篇目清单 ======================


def test_the_repository_manifest_is_valid():
    directory = Path(__file__).resolve().parent.parent / "references"
    papers = load_manifest(directory)
    assert len(papers) >= 14
    assert len({p.key for p in papers}) == len(papers)
    assert all(p.pdf.startswith("https://www.china-simulation.com/") and p.title for p in papers)


def test_a_bad_key_is_rejected(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"papers": [{"key": "../evil", "title": "t", "pdf": "https://x"}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_manifest(tmp_path)


# ====================== 启动时下载 ======================


def write_manifest(tmp_path, *keys):
    papers = [{"key": k, "title": f"论文{k}", "citation": "系统仿真学报", "pdf": f"https://example.com/{k}.pdf"} for k in keys]
    (tmp_path / "manifest.json").write_text(json.dumps({"papers": papers}, ensure_ascii=False), encoding="utf-8")


def fake_extraction(monkeypatch):
    monkeypatch.setattr(fetch_references, "extract_pdf_pages", lambda path: [BODY])


@pytest.fixture(autouse=True)
def site_is_up(monkeypatch):
    """单测一律不连真网络：「敲门」默认通，要测不通的用例自己改。"""
    monkeypatch.setattr(fetch_references, "site_reachable", lambda url, **kwargs: True)


def test_missing_papers_are_downloaded_and_existing_ones_skipped(tmp_path, monkeypatch):
    write_manifest(tmp_path, "a", "b")
    (tmp_path / "a.md").write_text("已经有了", encoding="utf-8")
    fetched = []
    monkeypatch.setattr(fetch_references, "download_pdf", lambda ref, timeout: fetched.append(ref.key) or b"%PDF-1.4")
    fake_extraction(monkeypatch)

    counts = fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=lambda _: None)

    assert fetched == ["b"]
    assert counts["ready"] == 2 and counts["downloaded"] == 1
    assert (tmp_path / "b.pdf").exists()
    title, _, body = parse_reference_markdown((tmp_path / "b.md").read_text(encoding="utf-8"), "b")
    assert title == "论文b" and body


def test_a_failed_download_does_not_stop_the_others(tmp_path, monkeypatch):
    write_manifest(tmp_path, "bad", "good")

    def download(ref, timeout):
        if ref.key == "bad":
            raise RuntimeError("403 Forbidden")
        return b"%PDF-1.4"

    monkeypatch.setattr(fetch_references, "download_pdf", download)
    fake_extraction(monkeypatch)
    messages = []
    counts = fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=messages.append)

    assert counts["failed"] == 1 and counts["ready"] == 1
    assert (tmp_path / "good.md").exists() and not (tmp_path / "bad.pdf").exists()
    assert any("论文bad" in m and "403" in m for m in messages)


def test_downloads_stop_starting_after_the_deadline(tmp_path, monkeypatch):
    write_manifest(tmp_path, "a", "b")
    monkeypatch.setattr(fetch_references, "download_pdf", lambda ref, timeout: pytest.fail("不该再下"))
    counts = fetch_references.run(tmp_path, deadline_seconds=-1, timeout=5, out=lambda _: None)
    assert counts["postponed"] == 2


def test_a_pdf_dropped_in_by_hand_is_converted(tmp_path, monkeypatch):
    write_manifest(tmp_path)
    (tmp_path / "my-paper.pdf").write_bytes(b"%PDF-1.4")
    fake_extraction(monkeypatch)
    counts = fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=lambda _: None)
    assert counts["converted"] == 1
    title, _, _ = parse_reference_markdown((tmp_path / "my-paper.md").read_text(encoding="utf-8"), "x")
    assert title == "my-paper"


def test_a_non_pdf_response_is_rejected(monkeypatch):
    """期刊站出错时会回一张 HTML 页面，不能把它当 PDF 存下来。"""
    real_client = httpx.Client

    def client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(200, html="<html>维护中</html>"))
        return real_client(**kwargs)

    monkeypatch.setattr(fetch_references.httpx, "Client", client)
    ref = Reference(key="k", title="t", citation="", page="", pdf="https://example.com/k.pdf")
    with pytest.raises(RuntimeError, match="不是 PDF"):
        fetch_references.download_pdf(ref, timeout=5)


def test_direct_connection_is_tried_before_the_proxy(monkeypatch):
    """期刊站走代理会 403：先直连（trust_env=False），失败了才按环境变量走代理。"""
    real_client = httpx.Client
    attempts = []

    def client(**kwargs):
        attempts.append(kwargs["trust_env"])
        status = 403 if not kwargs["trust_env"] else 200
        kwargs["transport"] = httpx.MockTransport(
            lambda request: httpx.Response(status, content=b"%PDF-1.4 body")
        )
        return real_client(**kwargs)

    monkeypatch.setattr(fetch_references.httpx, "Client", client)
    ref = Reference(key="k", title="t", citation="", page="", pdf="https://example.com/k.pdf")
    assert fetch_references.download_pdf(ref, timeout=5).startswith(b"%PDF")
    assert attempts == [False, True]


def test_an_unreachable_site_postpones_everything_without_trying(tmp_path, monkeypatch):
    """丢包的网络里一篇篇等超时要两分钟：先敲门，不通就整步跳过（实测 120 秒 → 10 秒）。"""
    write_manifest(tmp_path, "a", "b", "c")
    monkeypatch.setattr(fetch_references, "site_reachable", lambda url, **kwargs: False)
    monkeypatch.setattr(fetch_references, "download_pdf", lambda ref, timeout: pytest.fail("不该再下"))
    messages = []
    counts = fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=messages.append)
    assert counts["postponed"] == 3 and counts["failed"] == 0
    assert any("连不上期刊官网" in m for m in messages)


def test_the_knock_is_skipped_when_nothing_is_missing(tmp_path, monkeypatch):
    """论文都在时启动这一步要一眨眼结束，不能每次去连期刊站。"""
    write_manifest(tmp_path, "a")
    (tmp_path / "a.md").write_text("已经有了", encoding="utf-8")
    monkeypatch.setattr(fetch_references, "site_reachable", lambda url, **kwargs: pytest.fail("不该连网"))
    assert fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=lambda _: None)["ready"] == 1


def test_one_unreachable_download_stops_the_rest_from_starting(tmp_path, monkeypatch):
    write_manifest(tmp_path, *[f"p{i}" for i in range(6)])
    tried = []

    def download(ref, timeout):
        tried.append(ref.key)
        raise fetch_references.NetworkUnreachable("timed out")

    monkeypatch.setattr(fetch_references, "download_pdf", download)
    counts = fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, workers=1, out=lambda _: None)
    assert tried == ["p0"] and counts["postponed"] == 6


def test_connect_failures_on_both_routes_mean_the_network_is_down(monkeypatch):
    real_client = httpx.Client

    def client(**kwargs):
        def refuse(request):
            raise httpx.ConnectTimeout("timed out", request=request)

        kwargs["transport"] = httpx.MockTransport(refuse)
        return real_client(**kwargs)

    monkeypatch.setattr(fetch_references.httpx, "Client", client)
    ref = Reference(key="k", title="t", citation="", page="", pdf="https://example.com/k.pdf")
    with pytest.raises(fetch_references.NetworkUnreachable):
        fetch_references.download_pdf(ref, timeout=5)


def test_adding_a_paper_only_embeds_that_paper(tmp_path):
    """加一篇论文不再把教材 2000 多块重新嵌入一遍（本机 61~69 秒）。"""
    make_kb(tmp_path, FakeEmbeddings()).warm_up()
    add_paper(tmp_path)
    paper_chunks = {d.page_content for d in reference_documents(tmp_path / "refs")}

    again = FakeEmbeddings()
    make_kb(tmp_path, again).warm_up()
    assert again.documents_embedded == len(paper_chunks)
