"""期刊官网「RichHTML」排版全文 → 能检索的文字。

PDF 里表格的行列、公式的上下标都抽不回来（见 references.clean_paper_text 只好把它们换成占位）；
《系统仿真学报》2022 年以后的文章在官网还有一份网页版全文，表格是真的 <table>，公式是 MathML。
有网页版的就用网页版：表格转成 Markdown 表格，公式转成 LaTeX（行内 \\(…\\)、单独成行 \\[…\\]）。

页面是期刊平台统一生成的，结构固定：正文在 id="art_content" 里，节标题是 class 带 title-biaoti 的
h2 / h3，表格在 class 带 figure_table 的块里（中文表题在 content-zw-biao-title-cn），图在
class="content-zw-img" 的块里（中文图题在 content-zw-img-shuoming-title-cn），参考文献从
「参考文献」那个节标题开始。结构变了就返回空串，调用方退回用 PDF。
"""

from __future__ import annotations

import html as html_lib
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

_CJK = r"\u4e00-\u9fff"


# ====================== MathML → LaTeX ======================

_ACCENTS = {"¯": "\\bar", "‾": "\\bar", "ˉ": "\\bar", "-": "\\bar", "^": "\\hat", "ˆ": "\\hat",
            "~": "\\tilde", "˜": "\\tilde", "→": "\\vec", "˙": "\\dot", "¨": "\\ddot"}
_LIMIT_OPS = {"min", "max", "lim", "sup", "inf", "arg min", "arg max", "argmin", "argmax"}
# 求和、连乘、积分这类大运算符：上下限写成下标、上标（\\sum_{k∈M}），不是 \\underset
_BIG_OPS = {"∑": "\\sum", "∏": "\\prod", "∫": "\\int", "⋃": "\\bigcup", "⋂": "\\bigcap"}
_ESCAPE = {"{": "\\{", "}": "\\}", "%": "\\%", "#": "\\#", "&": "\\&", "_": "\\_"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _group(text: str) -> str:
    return text if len(text) == 1 else f"{{{text}}}"


def mathml_to_latex(element: ET.Element) -> str:
    tag = _local(element.tag)
    kids = [mathml_to_latex(child) for child in element]
    text = (element.text or "").strip()

    if tag in {"math", "mrow", "mstyle", "mpadded", "semantics", "mphantom", "menclose"}:
        return "".join(kids)
    if tag == "annotation":
        return ""
    if tag == "mi":
        # 多字母的「正体」标识符是函数名（sin、min）；单字母照原样
        if len(text) > 1 and element.get("mathvariant") == "normal":
            return f"\\mathrm{{{text}}}"
        return text
    if tag == "mn":
        return text
    if tag == "mo":
        return _ESCAPE.get(text, text)
    if tag == "mtext":
        return f"\\text{{{text}}}" if text.strip() else " "
    if tag == "mspace":
        return " "
    if tag == "msub" and len(kids) >= 2:
        return f"{_group(kids[0])}_{_group(kids[1])}"
    if tag == "msup" and len(kids) >= 2:
        return f"{_group(kids[0])}^{_group(kids[1])}"
    if tag == "msubsup" and len(kids) >= 3:
        return f"{_group(kids[0])}_{_group(kids[1])}^{_group(kids[2])}"
    if tag == "mfrac" and len(kids) >= 2:
        return f"\\frac{{{kids[0]}}}{{{kids[1]}}}"
    if tag == "msqrt":
        return f"\\sqrt{{{''.join(kids)}}}"
    if tag == "mroot" and len(kids) >= 2:
        return f"\\sqrt[{kids[1]}]{{{kids[0]}}}"
    if tag == "mover" and len(kids) >= 2:
        accent = _ACCENTS.get(kids[1].strip())
        return f"{accent}{{{kids[0]}}}" if accent else f"\\overset{{{kids[1]}}}{{{kids[0]}}}"
    if tag == "munder" and len(kids) >= 2:
        base = _BIG_OPS.get(kids[0].strip(), kids[0])
        if base != kids[0] or kids[0].replace("\\mathrm", "").strip("{} ") in _LIMIT_OPS:
            return f"{base}_{_group(kids[1])}"
        return f"\\underset{{{kids[1]}}}{{{kids[0]}}}"
    if tag == "munderover" and len(kids) >= 3:
        return f"{_BIG_OPS.get(kids[0].strip(), kids[0])}_{_group(kids[1])}^{_group(kids[2])}"
    if tag == "mfenced":
        opening = element.get("open", "(")
        closing = element.get("close", ")")
        separator = (element.get("separators") or ",")[:1]
        body = separator.join(kids)
        fence = {"{": "\\{", "}": "\\}"}
        if opening == "{" and not closing:
            return f"\\begin{{cases}}{body}\\end{{cases}}"  # 分段函数：左花括号 + 表格
        return f"\\left{fence.get(opening, opening) or '.'}{body}\\right{fence.get(closing, closing) or '.'}"
    if tag == "mtable":
        return "\\begin{matrix}" + " \\\\ ".join(kids) + "\\end{matrix}"
    if tag == "mtr":
        return " & ".join(kids)
    if tag == "mtd":
        return "".join(kids)
    return "".join(kids) or text


def _formula(fragment: str) -> str:
    """一段 <math>…</math> → LaTeX。解析不了就退回去掉标签的纯文字，不丢内容。"""
    source = fragment.replace("&nbsp;", " ")
    try:
        latex = mathml_to_latex(ET.fromstring(source))
    except ET.ParseError:
        latex = html_lib.unescape(re.sub(r"<[^>]+>", "", fragment))
    # cases 里的 matrix 是多余的一层
    latex = latex.replace("\\begin{cases}\\begin{matrix}", "\\begin{cases}").replace(
        "\\end{matrix}\\end{cases}", "\\end{cases}"
    )
    return re.sub(r"\s+", " ", latex).strip()


# ====================== 表格 ======================


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._cell: list[str] | None = None
        self._span = 1

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            self._cell = []
            span = int(dict(attrs).get("colspan") or 1)
            self._span = max(1, min(span, 20))
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self.rows:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip().replace("|", "/")
            self.rows[-1].extend([text] + [""] * (self._span - 1))
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _markdown_table(table_html: str) -> str:
    parser = _TableParser()
    parser.feed(table_html)
    rows = [row for row in parser.rows if any(cell for cell in row)]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join(lines)


# ====================== 整页 ======================


def _text(fragment: str) -> str:
    text = re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()
    # 去标签留下的空格：中文标点两侧、两个汉字之间都不该有
    text = re.sub(r"\s+([，。、；：？！）」』”])", r"\1", text)
    text = re.sub(r"([（「『“])\s+", r"\1", text)
    return re.sub(f"([{_CJK}])\\s+(?=[{_CJK}])", r"\1", text)


def _caption_text(block: str, css_class: str) -> str:
    match = re.search(rf'<p class="{css_class}"[^>]*>(.*?)</p>', block, re.S)
    if not match:
        return ""
    caption = _text(match.group(1))
    # 「表1 可行班次」→「表 1：可行班次」
    return re.sub(r"^([表图])\s*(\d+)\s*", r"\1 \2：", caption)


def _abstract(page: str) -> str:
    """摘要和关键词在正文前面另一块里（class="zhaiyao-cn"），检索时最有用，单独取出来。"""
    match = re.search(r'<div class="zhaiyao-cn-content">(.*?)</div>', page, re.S)
    if not match:
        return ""
    block = match.group(1)
    keywords = re.findall(r"<kwd>(.*?)</kwd>", block, re.S)
    block = re.sub(r'<p class="keyword_cn">.*?</p>', "", block, flags=re.S)
    block = re.sub(r"<math\b.*?</math>", lambda m: f"\\({_formula(m.group(0))}\\)", block, flags=re.S)
    text = f"摘要：{_text(block)}"
    if keywords:
        text += "\n\n关键词：" + "；".join(_text(k) for k in keywords)
    return re.sub(r"([。！？；])(?=\S)", "\\1\n", text)


def html_to_text(page: str) -> str:
    """整页 HTML → 正文（不含题目与出处，那两样由调用方加）。认不出版式就返回空串。"""
    start = page.find('id="art_content"')
    if start < 0:
        return ""
    body = page[page.find(">", start) + 1 :]
    end = re.search(r'<h2 class="title-biaoti"[^>]*>\s*(?:<span[^>]*>)?\s*参考文献', body)
    if end:
        body = body[: end.start()]

    # 公式：单独成行的 \[ \]，行内的 \( \)
    body = re.sub(
        r"<disp-formula\b[^>]*>(.*?)</disp-formula>",
        lambda m: "\n\n\\[" + "".join(_formula(f) for f in re.findall(r"<math\b.*?</math>", m.group(1), re.S)) + "\\]\n\n",
        body,
        flags=re.S,
    )
    body = re.sub(r"<math\b.*?</math>", lambda m: f"\\({_formula(m.group(0))}\\)", body, flags=re.S)

    # 表格：表题 + Markdown 表格
    def table(match: re.Match) -> str:
        block = match.group(0)
        caption = _caption_text(block, "content-zw-biao-title-cn") or "表"
        grid = "".join(_markdown_table(t) for t in re.findall(r"<table\b.*?</table>", block, re.S))
        return f"\n\n{caption}\n\n{grid}\n\n" if grid else f"\n\n（原文{caption}，数据见原文）\n\n"

    body = re.sub(
        r'<div class="zw-zsbg figure_table[^"]*">.*?</table>\s*(?:</div>\s*)*',
        table,
        body,
        flags=re.S,
    )

    # 图：只留图题
    def figure(match: re.Match) -> str:
        caption = _caption_text(match.group(0), "content-zw-img-shuoming-title-cn")
        return f"\n\n（原文{caption}）\n\n" if caption else "\n\n"

    body = re.sub(
        r'<div class="content-zw-img"[^>]*>.*?<div class="content-zw-img-shuoming">.*?</div>\s*</div>',
        figure,
        body,
        flags=re.S,
    )

    # 引用上标「[1-3]」、隐藏的锚点标题
    body = re.sub(r"<sup>\s*\[.*?\]\s*</sup>", "", body, flags=re.S)
    body = re.sub(r'<h3 style="position: absolute;[^"]*"[^>]*>.*?</h3>', "", body, flags=re.S)
    # 节标题、段落各自成段
    body = re.sub(r"<h[23][^>]*>(.*?)</h[23]>", lambda m: f"\n\n{_text(m.group(1))}\n\n", body, flags=re.S)
    body = re.sub(r"</p>|<br\s*/?>", "\n\n", body)

    # 表格、图下面的操作按钮（「新窗口打开 | 下载CSV」，分在几个 <a> 里，中间夹着竖线）
    body = re.sub(r'<p class="(?:tishi|biaotishi1)">.*?</p>', "", body, flags=re.S)
    body = re.sub(r"<a\b[^>]*>\s*(?:新窗口打开|下载原图ZIP|生成PPT|下载CSV)\s*</a>\s*\|?", "", body)
    # 有的变量不是 MathML，是 HTML 的上下标：<i>X<sub>ijk</sub></i> → X_{ijk}
    body = re.sub(r"<sub>(.*?)</sub>", lambda m: "_{" + _text(m.group(1)) + "}", body, flags=re.S)
    body = re.sub(r"<sup>(.*?)</sup>", lambda m: "^{" + _text(m.group(1)) + "}", body, flags=re.S)

    paragraphs = []
    abstract = _abstract(page)
    if abstract:
        paragraphs.append(abstract)
    for chunk in re.split(r"\n\s*\n", body):
        if chunk.lstrip().startswith("|"):  # Markdown 表格原样留着
            paragraphs.append("\n".join(line.strip() for line in chunk.strip().splitlines()))
            continue
        text = _text(chunk)
        if not text:
            continue
        # 每句一行（和 PDF 那条路一样，切块时边界落在句子之间）；公式里的符号不动
        text = re.sub(r"([。！？；])(?=\S)", "\\1\n", text)
        paragraphs.append(text)
    return "\n\n".join(paragraphs).strip()
