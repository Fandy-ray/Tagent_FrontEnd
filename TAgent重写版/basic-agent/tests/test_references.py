"""参考文献：抽文字、并进本地知识库、启动时下载。全部离线（下载用替身，不连期刊官网）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx
import pytest
from langchain_core.embeddings import Embeddings

from app.rag.knowledge_base import KnowledgeBase
from app.rag.references import (
    EXTRACT_VERSION,
    Reference,
    clean_paper_text,
    extract_version,
    load_manifest,
    parse_reference_markdown,
    reference_documents,
    reference_markdown,
    retrieval_windows,
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


def write_current_md(tmp_path, key):
    """按现在这一版规则抽好的 .md（带版本标记）。"""
    ref = Reference(key=key, title=f"论文{key}", citation="系统仿真学报", page="", pdf="")
    (tmp_path / f"{key}.md").write_text(reference_markdown(ref, BODY), encoding="utf-8")


def fake_extraction(monkeypatch):
    monkeypatch.setattr(fetch_references, "extract_pdf_pages", lambda path: [BODY])


@pytest.fixture(autouse=True)
def site_is_up(monkeypatch):
    """单测一律不连真网络：「敲门」默认通，要测不通的用例自己改。"""
    monkeypatch.setattr(fetch_references, "site_reachable", lambda url, **kwargs: True)


def test_missing_papers_are_downloaded_and_existing_ones_skipped(tmp_path, monkeypatch):
    write_manifest(tmp_path, "a", "b")
    write_current_md(tmp_path, "a")
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
    write_current_md(tmp_path, "a")
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
    # 论文按检索窗口算向量（见 references.WINDOW_SIZE）
    windows = {w for d in reference_documents(tmp_path / "refs") for w in retrieval_windows(d)}

    again = FakeEmbeddings()
    make_kb(tmp_path, again).warm_up()
    assert again.documents_embedded == len(windows)


# ====================== 表格、公式、图题（PDF 那条路） ======================


PROSE = "仿真技术的出现解决了复杂呼叫中心的管理研究问题"  # 一行正文（双栏排版一行二十来个字）


def test_a_table_becomes_one_placeholder_and_the_prose_after_it_stays():
    pages = [page(
        PROSE + "，如表 1 所示。",
        "表 1  订单基本数据", "Tab. 1  Order basic data",
        "订单", "产品", "数量", "A1", "3", "B2", "5",
        "此外，智慧仓储系统中原有机器人的配置为三十二台，",
        "初始位置集中在充电区。",
    )]
    text = clean_paper_text(pages)
    # 表题 + 表里的中文项目名称（问到表里的东西时靠它们查得到）；数字、编号拆开了对不上行列，不留
    assert "（原文表 1：订单基本数据，涉及：产品、数量，数据见原文）" in text
    assert "订单\n" not in text and "B2" not in text and "Order basic data" not in text
    assert "此外，智慧仓储系统中原有机器人的配置为三十二台，初始位置集中在充电区。" in text


def test_a_display_formula_split_into_short_lines_is_dropped():
    pages = [page(
        PROSE + "，其数学表达式为",
        "Δps", "=", "ì", "í", "0 , if ( )p", "s", "min ≥ ℓ",
        "im ), i ∈ 1,2,⋯,n (18)",
        "种群中第 i 个个体按式(19)进行变异操作得到新的个体。",
    )]
    text = clean_paper_text(pages)
    assert "ì" not in text and "Δps" not in text and "(18)" not in text
    flat = re.sub(r"\s", "", text)
    assert "其数学表达式为" in flat and "种群中第i个个体按式(19)进行变异操作得到新的个体。" in flat


def test_a_paragraph_tail_before_a_formula_is_not_swallowed_with_it():
    """段尾短行后面紧跟公式碎片时，不能把段尾和公式一起当成「一串碎片」扔掉。"""
    pages = [page("耐心时间，顾客实际时间 W 在虚拟等待时间与耐", "心值取最小值", "W", "= min", "{D,T}", PROSE + "。")]
    assert "心值取最小值" in clean_paper_text(pages)


def test_short_paragraph_tails_and_inline_variables_are_kept():
    """段尾的短行（「心值取最小值」「，因此」）和折行的变量名不能当公式碎片扔掉。"""
    pages = [page(
        "耐心时间，顾客实际时间 W 在虚拟等待时间与耐",
        "心值取最小值",
        "[2]",
        "，因此",
        "其中，令服务率偏差 Δps",
        "表示所有时段的最低服务率与目标约束的偏差。",
    )]
    flat = re.sub(r"\s", "", clean_paper_text(pages))
    assert "在虚拟等待时间与耐心值取最小值，因此" in flat
    assert "令服务率偏差Δps表示所有时段" in flat
    assert "[2]" not in flat


def test_wrapped_prose_starting_with_table_reference_is_not_a_caption():
    # 「表 3 所示」恰好折在行首、整行又很短：看着像表题，其实是正文
    pages = [page(PROSE + "，实验结果如", "表 3 所示", "，两种方法都满足约束。", PROSE + "。")]
    text = clean_paper_text(pages)
    assert "原文表" not in text and "实验结果如表3所示，两种方法都满足约束。" in re.sub(r"\s", "", text)


def test_figure_captions_become_their_own_paragraph():
    pages = [page(PROSE + "，流程如图 1 所示。", "图 1  等待提示机制下呼叫中心服务流程",
                  "Fig. 1  Service process", "当顾客到达时，如果等待队列中存在空闲的坐席人员，则无需等待。")]
    text = clean_paper_text(pages)
    assert "\n\n（原文图 1：等待提示机制下呼叫中心服务流程）\n\n" in text
    assert "当顾客到达时" in text


def test_numeric_table_rows_without_a_caption_are_dropped():
    pages = [page(PROSE + "。", "Δps /% 1.39 2.01 3.67 1.05 1.43 1.38", PROSE + "。")]
    assert "1.39" not in clean_paper_text(pages)


# ====================== 网页版全文 ======================

from xml.etree import ElementTree as ET  # noqa: E402

from app.rag.reference_html import html_to_text, mathml_to_latex  # noqa: E402


def latex(mathml: str) -> str:
    return mathml_to_latex(ET.fromstring(mathml))


def test_mathml_to_latex_covers_the_journal_s_constructs():
    assert latex("<math><msub><mi>α</mi><mn>0</mn></msub></math>") == "α_0"
    assert latex("<math><msup><mi>p</mi><mi>b</mi></msup></math>") == "p^b"
    assert latex("<math><mfrac><mi>a</mi><mi>b</mi></mfrac></math>") == "\\frac{a}{b}"
    assert latex("<math><mover><mi>λ</mi><mo>¯</mo></mover></math>") == "\\bar{λ}"
    assert latex("<math><munder><mi mathvariant='normal'>min</mi><mi>x</mi></munder></math>") == "\\mathrm{min}_x"
    assert latex("<math><mfenced open='{' close=''><mtable><mtr><mtd><mn>0</mn></mtd></mtr>"
                 "<mtr><mtd><mn>1</mn></mtd></mtr></mtable></mfenced></math>") == \
        "\\begin{cases}\\begin{matrix}0 \\\\ 1\\end{matrix}\\end{cases}"


RICH_PAGE = """
<div class="zhaiyao-cn-content"><p><span>针对带有等待提示的呼叫中心进行联合排班方法研究。</span></p>
<p class="keyword_cn"><kwd>等待提示</kwd> ; <kwd>仿真优化</kwd></p></div>
<div id="art_content" class="col-xs-9 trnn">
<h2 class="title-biaoti outline_anchor" level="1"> 1 提示时间评估方法 </h2>
<div class="paragraph"><div class="content-zw-1"><p>顾客到达服从参数为<span class="formulaText"><inline-formula>
<math xmlns:mml="http://www.w3.org/1998/Math/MathML"><mi>λ</mi></math></inline-formula></span>的泊松过程<sup>[<a>1</a>]</sup>。</p></div></div>
<div class="content-zw-1"><disp-formula id="DF1"><math><mi>W</mi><mo>=</mo><mfrac><mi>a</mi><mi>b</mi></mfrac></math></disp-formula></div>
<h3 style="position: absolute; opacity: 0; filter:Alpha(opacity=0);">图1</h3>
<div class="content-zw-img" id="F1"><div class="content-zw-img-img figure"><img src="x.jpg"><p class="tishi"><a>新窗口打开</a>| <a>下载原图ZIP</a></p></div>
<div class="content-zw-img-shuoming"><p class="content-zw-img-shuoming-title-cn"><b>图1&nbsp;&nbsp; <strong>服务流程</strong></b></p></div></div>
<div class="zw-zsbg figure_table outline_anchor"><div class="shitibiao"><p class="content-zw-biao-title-cn"><strong>表2</strong>&nbsp;&nbsp; <span>相关实验参数</span></p></div>
<div class="table-responsive"><table><thead><tr><th>重拨概率</th><th>服务率</th></tr></thead>
<tbody><tr><td><math><mi>τ</mi></math></td><td><math><mi>μ</mi></math></td></tr><tr><td>0.2</td><td>0.5</td></tr></tbody></table></div></div>
<p class="biaotishi1"> <a href="T1.html">新窗口打开</a>| <a href="T1.csv.zip">下载CSV</a> </p>
<div class="content-zw-1"><p>每道操作对机器的选择(<i>X<sub>ijk</sub></i> )满足</p></div>
<div class="content-zw-1"><disp-formula><math><munder><mo>∑</mo><mrow><mi>k</mi><mo>∈</mo><mi>M</mi></mrow></munder><msub><mi>X</mi><mi>k</mi></msub><mo>=</mo><mn>1</mn></math></disp-formula></div>
<h2 class="title-biaoti"> <span class="outline_anchor" level="1">参考文献 </span></h2><p>[1] 某某. 某文[J]. 2018.</p>
</div>
"""


def test_the_rich_html_page_becomes_clean_text():
    text = html_to_text(RICH_PAGE)
    assert text.startswith("摘要：针对带有等待提示的呼叫中心进行联合排班方法研究。")
    assert "关键词：等待提示；\n仿真优化" in text
    assert "\n\n1 提示时间评估方法\n\n" in text
    assert "顾客到达服从参数为 \\(λ\\) 的泊松过程。" in text  # 行内公式，引用上标去掉
    assert "\\[W=\\frac{a}{b}\\]" in text  # 单独成行的公式
    assert "（原文图 1：服务流程）" in text
    assert "表 2：相关实验参数\n\n| 重拨概率 | 服务率 |\n|---|---|\n| \\(τ\\) | \\(μ\\) |\n| 0.2 | 0.5 |" in text
    assert "新窗口打开" not in text and "下载CSV" not in text and "某文" not in text  # 按钮、参考文献都不要
    assert "( X_{ijk} )" in text  # HTML 上下标写的变量
    assert "\\[\\sum_{k∈M}X_k=1\\]" in text  # 求和号的上下限
    assert "art_content" not in text


def test_an_unrecognised_page_gives_nothing_so_the_pdf_is_used():
    assert html_to_text("<html><body>维护中</body></html>") == ""


# ====================== 下载脚本：网页版优先、旧版本重抽 ======================


def write_manifest_with_html(tmp_path, key="p"):
    paper = {"key": key, "title": f"论文{key}", "citation": "系统仿真学报", "pdf": f"https://example.com/{key}.pdf",
             "html": f"https://example.com/{key}.shtml"}
    (tmp_path / "manifest.json").write_text(json.dumps({"papers": [paper]}, ensure_ascii=False), encoding="utf-8")


RICH_PAGE_LONG = RICH_PAGE.replace("进行联合排班方法研究。", "进行联合排班方法研究。" + BODY)


def test_the_web_version_is_preferred_over_the_pdf(tmp_path, monkeypatch):
    write_manifest_with_html(tmp_path)
    monkeypatch.setattr(fetch_references, "download_page", lambda ref, timeout: RICH_PAGE_LONG)
    monkeypatch.setattr(fetch_references, "download_pdf", lambda ref, timeout: pytest.fail("有网页版就不该下 PDF"))
    counts = fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=lambda _: None)
    text = (tmp_path / "p.md").read_text(encoding="utf-8")
    assert counts["downloaded"] == 1 and "（网页版）" in text and "| 重拨概率 | 服务率 |" in text


def test_a_broken_web_version_falls_back_to_the_pdf(tmp_path, monkeypatch):
    write_manifest_with_html(tmp_path)
    monkeypatch.setattr(fetch_references, "download_page", lambda ref, timeout: "<html>维护中</html>")
    monkeypatch.setattr(fetch_references, "download_pdf", lambda ref, timeout: b"%PDF-1.4")
    fake_extraction(monkeypatch)
    messages = []
    fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=messages.append)
    assert "（pdf）" in (tmp_path / "p.md").read_text(encoding="utf-8")
    assert any("改用 PDF" in m for m in messages)


def test_an_outdated_extraction_is_redone_from_local_files_without_the_network(tmp_path, monkeypatch):
    write_manifest(tmp_path, "a")
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "a.md").write_text("# 论文a\n\n> 来源：旧版本抽的，没有版本标记\n\n" + BODY, encoding="utf-8")
    monkeypatch.setattr(fetch_references, "site_reachable", lambda url, **kwargs: pytest.fail("不该连网"))
    monkeypatch.setattr(fetch_references, "download_pdf", lambda ref, timeout: pytest.fail("不该重新下载"))
    fake_extraction(monkeypatch)
    counts = fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=lambda _: None)
    assert counts["reextracted"] == 1
    assert extract_version((tmp_path / "a.md").read_text(encoding="utf-8")) == EXTRACT_VERSION


def test_a_hand_written_md_next_to_a_dropped_pdf_is_not_overwritten(tmp_path, monkeypatch):
    write_manifest(tmp_path)
    (tmp_path / "notes.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "notes.md").write_text("# 我的读书笔记\n\n" + BODY, encoding="utf-8")
    fake_extraction(monkeypatch)
    fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=lambda _: None)
    assert (tmp_path / "notes.md").read_text(encoding="utf-8").startswith("# 我的读书笔记")


def test_the_marker_line_never_reaches_the_index(tmp_path):
    ref = Reference(key="k", title="某篇论文", citation="系统仿真学报", page="", pdf="")
    (tmp_path / "k.md").write_text(reference_markdown(ref, BODY, origin="网页版"), encoding="utf-8")
    assert not any("抽取 v" in d.page_content for d in reference_documents(tmp_path))


def test_a_web_version_missed_once_is_tried_again_next_start(tmp_path, monkeypatch):
    """网页版这次没下到（网络抖了一下）就先用 PDF；下次启动还要再试网页版，不能就此一直用 PDF。"""
    write_manifest_with_html(tmp_path)
    monkeypatch.setattr(fetch_references, "download_pdf", lambda ref, timeout: b"%PDF-1.4")
    fake_extraction(monkeypatch)

    def flaky(ref, timeout):
        raise RuntimeError("read timed out")

    monkeypatch.setattr(fetch_references, "download_page", flaky)
    fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=lambda _: None)
    assert "（pdf）" in (tmp_path / "p.md").read_text(encoding="utf-8")

    monkeypatch.setattr(fetch_references, "download_page", lambda ref, timeout: RICH_PAGE_LONG)
    fetch_references.run(tmp_path, deadline_seconds=60, timeout=5, out=lambda _: None)
    assert "（网页版）" in (tmp_path / "p.md").read_text(encoding="utf-8")


def test_the_real_page_text_is_decoded_without_errors(monkeypatch):
    """取网页正文后不能再去设置编码（httpx 会报错，实测踩过）。"""
    real_client = httpx.Client

    def client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda request: httpx.Response(200, content=RICH_PAGE_LONG.encode("utf-8"),
                                           headers={"Content-Type": "text/html;charset=UTF-8"})
        )
        return real_client(**kwargs)

    monkeypatch.setattr(fetch_references.httpx, "Client", client)
    ref = Reference(key="k", title="t", citation="", page="", pdf="", html="https://example.com/k.shtml")
    assert "art_content" in fetch_references.download_page(ref, timeout=5)


# ====================== 小窗口检索、整块返回 ======================


def test_a_sentence_deep_inside_a_chunk_is_found_and_the_whole_chunk_comes_back(tmp_path):
    """嵌入模型只读每段前 128 个字：块尾的内容要靠小窗口才查得到，查到后返回整块。"""
    kb = make_kb(tmp_path, FakeEmbeddings())
    tail = "块尾这一句讲的是排队系统的稳态条件与服务强度。"
    add_paper(tmp_path, body=BODY + tail)
    kb.ensure_index()
    [parent] = [d for d in kb.chunks() if d.metadata.get("source") == "reference" and tail in d.page_content]
    last_window = retrieval_windows(parent)[-1]
    hits = kb.search(last_window, k=1)  # 假嵌入：文字一样向量就一样
    assert hits[0].page_content == parent.page_content
    assert len(parent.page_content) > len(last_window)


class TopicEmbeddings(FakeEmbeddings):
    """按话题给向量：含「排队论」的文字向量完全一样——同一块切出的几个窗口一定并列第一。"""

    @staticmethod
    def _vector(text):
        return [1.0 if "排队论" in text else 0.0, 1.0 if "库存论" in text else 0.0] + [0.0] * 6


def test_search_returns_each_chunk_once(tmp_path):
    kb = make_kb(tmp_path, TopicEmbeddings())
    add_paper(tmp_path, key="a")
    add_paper(tmp_path, key="b", body=BODY.replace("排队论", "库存论"))
    kb.ensure_index()
    hits = kb.search("排队论", k=3)
    keys = [d.metadata.get("parent") or d.page_content for d in hits]
    assert len(keys) == len(set(keys)) == 3


def test_sampling_sees_each_chunk_once_not_each_window(tmp_path):
    """抽题、闪卡按块随机取：一块切成几个窗口不能让论文被抽中的机会翻几倍。"""
    kb = make_kb(tmp_path, FakeEmbeddings())
    add_paper(tmp_path)
    chunks = kb.ensure_index()
    parents = [d.metadata["parent"] for d in chunks if d.metadata.get("source") == "reference"]
    assert len(parents) == len(set(parents))
    assert len(kb.vectorstore.index_to_docstore_id) > len(chunks)  # 索引里是窗口，比块多


def test_image_tables_and_captionless_figures_do_not_swallow_the_text_after_them():
    """表格是图片（没有 <table>）、图没有图注时，不能一路吞到下一张表或图，把中间的正文删掉。"""
    page = """<div id="art_content">
<div class="zw-zsbg figure_table outline_anchor"><div class="shitibiao"><p class="content-zw-biao-title-cn"><strong>表1</strong> <span>图片表格</span></p></div><img src="t1.jpg"></div>
<div class="paragraph"><div class="content-zw-1"><p>这一段正文夹在两张表中间。</p></div></div>
<div class="content-zw-img" id="F1"><div class="content-zw-img-img figure"><img src="x.jpg"></div></div>
<div class="paragraph"><div class="content-zw-1"><p>这一段正文跟在没有图注的图后面。</p></div></div>
<div class="content-zw-img" id="F2"><div class="content-zw-img-shuoming"><p class="content-zw-img-shuoming-title-cn"><b>图2 <strong>紧挨着表格的图</strong></b></p></div></div>
<div class="zw-zsbg figure_table outline_anchor"><div class="shitibiao"><p class="content-zw-biao-title-cn"><strong>表2</strong> <span>真表格</span></p></div><table><tr><th>甲</th><th>乙</th></tr><tr><td>1</td><td>2</td></tr></table><p>注：表中数据为机器号</p><p class="biaotishi1"><a>新窗口打开</a>| <a>下载CSV</a></p></div>
<h4 class="title-biaoti-1 outline_anchor" level="3"> 3.1.3 变异算子 </h4>
<div class="paragraph"><div class="content-zw-1"><p>变异算子对新解进行变异。</p></div></div>
</div>"""
    text = html_to_text(page)
    assert "这一段正文夹在两张表中间。" in text and "这一段正文跟在没有图注的图后面。" in text
    assert "（原文表 1：图片表格，数据见原文）" in text  # 图片表格只留表题
    assert "（原文图 2：紧挨着表格的图）" in text
    assert "表 2：真表格\n\n| 甲 | 乙 |" in text  # 紧跟在图后面的表没被图吞掉
    assert "注：表中数据为机器号" in text and "下载CSV" not in text
    assert "\n\n3.1.3 变异算子\n\n变异算子对新解进行变异。" in text  # 三级标题（h4）单独成段


def test_search_still_returns_k_chunks_when_one_chunk_has_many_windows(tmp_path):
    """一块论文的窗口全挤在最前面时，也要凑够 k 块，不能只给一块。"""
    kb = make_kb(tmp_path, TopicEmbeddings())
    add_paper(tmp_path, key="a", body=BODY * 4)  # 好几块、每块好几个窗口，向量全一样
    add_paper(tmp_path, key="b", body=BODY.replace("排队论", "库存论"))
    kb.ensure_index()
    hits = kb.search("排队论", k=3)
    assert len(hits) == 3 and len({d.metadata.get("parent") or d.page_content for d in hits}) == 3
