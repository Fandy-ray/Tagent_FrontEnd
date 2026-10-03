"""参考文献：《系统仿真学报》等论文的下载、抽文字、切块。

出题、答疑、论文批改检索材料时，除了教材 book1.md，还会用到 references/ 目录里的论文。

全文**不进仓库**：仓库是公开的，期刊论文的版权在期刊，不能转载。仓库里只有
references/manifest.json 这份篇目清单；启动脚本运行 tools/fetch_references.py，
从期刊官网把还没有的论文下到本机、抽成同名 .md，知识库只读 .md / .txt。
抽文字放在下载这一步做一次，不在每次启动建索引时做：14 篇 PDF 每次都抽要多花十几秒。
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.documents import Document


log = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
# 知识库只读这两种；PDF 由 tools/fetch_references.py 先抽成 .md
TEXT_SUFFIXES = (".md", ".txt")
# 抽出来不到这么多字，多半是扫描版（整页是图片），不当论文用
MIN_TEXT_CHARS = 300
# 论文切块的写法一变就改这个值：它会进向量索引的缓存键（见 KnowledgeBase._index_cache_path）
REFERENCE_CHUNK_FORMAT = "refs-800-50-label-at-end"

_CJK = r"\u4e00-\u9fff"
_CJK_CHAR = re.compile(f"[{_CJK}]")
_CJK_PUNCT = "，。、；：？！“”‘’（）《》【】"
# 期刊每页的页眉页脚：出现在很多页上的行按频次去掉，下面这些即使只出现一次也去掉
_RUNNING_HEADER = re.compile(
    r"^(第\s*\d+\s*卷第\s*\d+\s*期|\d{4}\s*年\s*\d+\s*月|V\s?ol\.\s*\d+|[A-Z][a-z]{2}\.\s*\d{4}"
    r"|系统仿真学报\s*©?|Journal of System Simulation|http\S*|\d{1,4})$"
)
# 首页的出版信息与页脚：分类号、DOI、收稿日期、基金、作者简介、邮箱
_META_LINE = re.compile(
    r"^(中图分类号|文献标志码|文章编号|DOI|doi|收稿日期|修回日期|基金项目|第一作者|通讯作者|通信作者|作者简介|E-?mail|Email)"
)
# 另起一段的地方：摘要、关键词，以及只剩一个词的节标题（「0」常被当成页码去掉，只剩「引言」）
_PARAGRAPH_START = re.compile(r"^(摘\s*要|关键词)\s*[:：]|^(引言|前言|结论|结束语|结语|总结)$")
# 正文里的引用标记：[5]、[7-8]、[2,13]
_CITE_MARK = re.compile(r"\[\d+(?:\s*[-–,，]\s*\d+)*\]")
# PDF 里加粗的字常被抽成两遍：「摘要摘要：：」「1 引言引言」
_DOUBLED = re.compile(f"([{_CJK}]{{2,40}})\\1")
# 节标题：「1 引言」「2.1 模型建立」「0 引言」
_SECTION_HEADING = re.compile(r"^\d+(?:\.\d+)*\s+\S")


@dataclass(frozen=True)
class Reference:
    key: str
    title: str
    citation: str
    page: str
    pdf: str


def load_manifest(directory: Path) -> list[Reference]:
    """读篇目清单。清单坏了直接抛：那是仓库里的文件写错了，要让人看见。"""
    data = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    papers = []
    for item in data.get("papers", []):
        key = str(item["key"]).strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", key):
            raise ValueError(f"manifest.json 里的 key 只能用英文、数字、点、下划线和连字符：{key!r}")
        papers.append(
            Reference(
                key=key,
                title=str(item["title"]).strip(),
                citation=str(item.get("citation", "")).strip(),
                page=str(item.get("page", "")).strip(),
                pdf=str(item["pdf"]).strip(),
            )
        )
    return papers


def extract_pdf_pages(path: Path) -> list[str]:
    from pypdf import PdfReader

    # pypdf 遇到这本刊物字体字典里的重复键会刷一堆警告，内容本身抽得出来
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def clean_paper_text(pages: list[str]) -> str:
    """把 PDF 逐页抽出的文字整理成能检索的正文。

    去掉页眉页脚、英文摘要和参考文献列表、引用标记、加粗重复，再把被排版折断的行接回去，
    每句一行（切块时按行切，块的边界就落在句子之间）。
    """
    page_lines = [[line.strip() for line in page.splitlines() if line.strip()] for page in pages]
    # 在三成以上的页上都出现的行是页眉页脚（单页的文章不做这一步）
    seen_on = Counter(line for lines in page_lines for line in set(lines))
    repeated = {
        line
        for line, count in seen_on.items()
        if len(page_lines) >= 3 and count >= max(2, len(page_lines) * 0.3)
    }

    candidates: list[str] = []
    for lines in page_lines:
        for line in lines:
            if line in repeated:
                continue
            line = _DOUBLED.sub(r"\1", line).replace("：：", "：")
            if _RUNNING_HEADER.match(line) or _META_LINE.match(line):
                continue
            candidates.append(line)

    # 这本刊也登英文正文的论文（只有摘要是中文）：那种不能把英文行当噪声扔掉
    chinese_paper = sum(bool(_CJK_CHAR.search(line)) for line in candidates) >= len(candidates) * 0.4
    kept = [
        line
        for line in candidates
        # 中文论文里纯英文的长行：英文摘要、英文图题、英文参考文献，检索用不上
        if not chinese_paper or _CJK_CHAR.search(line) or len(re.findall(r"[A-Za-z]", line)) < 20
    ]

    # 参考文献列表在文末，从最后一个「参考文献」标题处截断（只认后半篇里的，免得正文提到就截）
    for index in range(len(kept) - 1, len(kept) // 2 - 1, -1):
        if re.match(r"^(参考文献|References)\s*[:：]?\s*$", kept[index], re.IGNORECASE):
            kept = kept[:index]
            break

    paragraphs: list[str] = []
    current = ""
    for line in kept:
        if (_SECTION_HEADING.match(line) and len(line) <= 40) or _PARAGRAPH_START.match(line):
            if current:
                paragraphs.append(current)
            if _PARAGRAPH_START.match(line) and not re.search(r"[:：]", line):
                paragraphs.append(line)  # 「引言」这类单独成行的标题
                current = ""
            elif _SECTION_HEADING.match(line):
                paragraphs.append(line)
                current = ""
            else:
                current = line  # 「摘要：……」开头的一段
            continue
        current = _join(current, line)
    if current:
        paragraphs.append(current)

    body = "\n\n".join(_tidy(paragraph) for paragraph in paragraphs if paragraph.strip())
    return body.strip()


def _join(left: str, right: str) -> str:
    if not left:
        return right
    # 中文之间直接接上；两边都是英文 / 数字才补空格
    if _CJK_CHAR.match(left[-1]) or left[-1] in _CJK_PUNCT or _CJK_CHAR.match(right[0]) or right[0] in _CJK_PUNCT:
        return left + right
    return f"{left} {right}"


def _tidy(paragraph: str) -> str:
    text = _CITE_MARK.sub("", paragraph)
    text = re.sub(r"•+\s*\d*", "", text)  # 页脚的「•• 1659」
    # 排版留下的空格：中文与中文标点之间不该有空格
    text = re.sub(f"\\s+([{_CJK_PUNCT}])", r"\1", text)
    text = re.sub(f"([{_CJK_PUNCT}])\\s+", r"\1", text)
    text = re.sub(f"([{_CJK}])\\s+([{_CJK}])", r"\1\2", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # 每句一行：切块时按行切，块的边界落在句子之间
    return re.sub(r"([。！？；])(?=\S)", "\\1\n", text).strip()


def reference_markdown(reference: Reference, body: str) -> str:
    source = f"{reference.citation}。{reference.page}" if reference.page else reference.citation
    return f"# {reference.title}\n\n> 来源：{source}\n\n{body.strip()}\n"


def parse_reference_markdown(text: str, fallback_title: str) -> tuple[str, str, str]:
    """（题目, 出处, 正文）。第一行 `# 题目`、紧跟的 `> 来源：…` 是可选的，没有就用文件名。"""
    lines = text.strip().splitlines()
    title, citation = fallback_title, ""
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip() or fallback_title
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    if lines and lines[0].startswith(">"):
        citation = re.sub(r"^>\s*(来源[:：])?\s*", "", lines[0]).strip()
        lines = lines[1:]
    return title, citation, "\n".join(lines).strip()


def reference_files(directory: Path | None) -> list[Path]:
    """知识库要读的文字稿，按文件名排好（缓存键要用，顺序必须稳定）。"""
    if directory is None or not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and path.name.lower() != "readme.md"
        and not path.name.startswith(".")
    )


def reference_documents(directory: Path | None) -> list[Document]:
    """切成和教材一样大小的块，每块**末尾**带上「——摘自《题目》（出处）」，回答时知道出自哪篇。

    放末尾不放开头：嵌入模型只读每块的前 128 个字，标签放开头要占掉将近一半，
    按内容找论文就不准了。12 个按内容提问的实测：开头 10/12 题第一条找对，末尾 11/12（前三条 11/12 → 12/12）。
    """
    # 放在函数里导入：启动脚本每次都跑 tools/fetch_references.py，论文都在时它应当一眨眼就结束，
    # 顶层导入 langchain 要多花 4 秒
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "，", " ", ""],
    )
    documents: list[Document] = []
    for path in reference_files(directory):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("参考文献读不了，跳过：%s（%s）", path.name, exc)
            continue
        title, citation, body = parse_reference_markdown(text, path.stem)
        if len(body) < MIN_TEXT_CHARS:
            log.warning("参考文献正文太短，跳过：%s", path.name)
            continue
        label = f"——摘自《{title}》" + (f"（{citation.split('。')[0]}）" if citation else "")
        for chunk in splitter.split_text(body):
            documents.append(
                Document(
                    page_content=f"{chunk}\n{label}",
                    metadata={"h1": "参考文献", "h2": title, "source": "reference", "file": path.name},
                )
            )
    return documents


def write_text_atomically(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def write_bytes_atomically(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
