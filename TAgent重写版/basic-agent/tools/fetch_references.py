"""下载参考文献并抽成文字：一键启动在起 basic-agent 之前会跑一次。

    uv run python tools/fetch_references.py            # 在 basic-agent 目录下
    uv run python tools/fetch_references.py --deadline 300

- 篇目在 references/manifest.json；已经有 .md 的跳过，所以只有第一次要等。
- 官网有网页版全文（RichHTML，清单里的 html）的先用网页版：表格、公式完整；不行再用 PDF。
- 抽取规则升级了（references.EXTRACT_VERSION），旧的 .md 用本机已有的原文重抽，不重新下载。
- 目录里别人自己放的 PDF（不在清单上的）也一并抽成 .md。
- 期刊官网走代理会被拒（403），先直连，连不上再按环境变量里的代理试一次。
- 任何一篇失败都只提示、不报错退出：启动不能因为下不到论文就起不来，下次启动再补。
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.references import (  # noqa: E402 —— 先把 basic-agent 放进 sys.path
    EXTRACT_VERSION,
    MANIFEST_NAME,
    MIN_TEXT_CHARS,
    Reference,
    clean_paper_text,
    extract_pdf_pages,
    extract_version,
    has_extract_mark,
    load_manifest,
    reference_markdown,
    write_bytes_atomically,
    write_text_atomically,
)
from app.rag.reference_html import html_to_text  # noqa: E402


DEFAULT_DIR = Path(__file__).resolve().parent.parent / "references"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Safari/605.1.15"
)
# 握手单独限时：有的网络（会场 / 校园网）不回拒绝、直接丢包，握手不限时就要等满整段超时，
# 实测 8 篇连不上时启动被拖了 120 秒（直连 30 秒 + 走代理 30 秒，4 篇一批）
CONNECT_TIMEOUT = 5.0


class NetworkUnreachable(RuntimeError):
    """直连、走代理都握不上手：网络不通，剩下的不必一篇篇再等。"""


def _fetch(url: str, *, referer: str, timeout: float, check) -> httpx.Response:
    """先直连、再走环境变量里的代理（国内期刊站走境外代理会 403）；check 不过也换下一条路再试。"""
    headers = {"User-Agent": USER_AGENT, "Referer": referer or url}
    errors: list[Exception] = []
    for trust_env in (False, True):
        try:
            with httpx.Client(
                trust_env=trust_env,
                timeout=httpx.Timeout(timeout, connect=min(CONNECT_TIMEOUT, timeout)),
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(url)
            response.raise_for_status()
            check(response)
            return response
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(exc)
    if all(isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)) for exc in errors):
        raise NetworkUnreachable(str(errors[-1]) or type(errors[-1]).__name__)
    raise RuntimeError(str(errors[-1]))


def download_pdf(reference: Reference, *, timeout: float) -> bytes:
    def check(response: httpx.Response) -> None:
        if not response.content.startswith(b"%PDF"):
            raise ValueError(f"返回的不是 PDF（{response.headers.get('content-type', '?')}）")

    return _fetch(reference.pdf, referer=reference.page, timeout=timeout, check=check).content


def download_page(reference: Reference, *, timeout: float) -> str:
    """官网的网页版全文（RichHTML）。"""

    def check(response: httpx.Response) -> None:
        if "art_content" not in response.text:
            raise ValueError("返回的不是网页版全文")

    return _fetch(reference.html, referer=reference.page, timeout=timeout, check=check).text


def _current(markdown: Path, reference: Reference | None = None) -> bool:
    """.md 在，而且是按现在这一版规则抽的。

    有网页版的论文，上次只是因为没下到网页（网络抖了一下）才用了 PDF 的，也不算数，下次再试网页版；
    网页下到了却认不出版式（本机有 .html）就不再试，免得每次启动都白下一遍。
    """
    if not markdown.exists() or markdown.stat().st_size == 0:
        return False
    text = markdown.read_text(encoding="utf-8")
    if extract_version(text) < EXTRACT_VERSION:
        return False
    if reference is not None and reference.html and "（网页版）" not in text[:400]:
        return markdown.with_suffix(".html").exists()
    return True


def site_reachable(url: str, *, timeout: float = CONNECT_TIMEOUT) -> bool:
    """下载之前先敲一下期刊站的门：不通就这次都不下。

    只靠下载本身的超时不够：走代理时连上的是代理，代理再去连期刊站，丢包的网络里要等满读超时，
    实测 8 篇连不上时还要 70 秒。这里直连、走代理各最多等几秒，网络不通时整步十秒内结束。
    """
    parts = urlsplit(url)
    home = f"{parts.scheme}://{parts.netloc}/"
    for trust_env in (False, True):
        try:
            with httpx.Client(
                trust_env=trust_env, timeout=timeout, headers={"User-Agent": USER_AGENT}
            ) as client:
                client.get(home)
            return True  # 有回应就算通（状态码不论：首页 403 也说明网络是通的）
        except httpx.HTTPError:
            continue
    return False


def pdf_to_markdown(pdf: Path, reference: Reference | None) -> str | None:
    body = clean_paper_text(extract_pdf_pages(pdf))
    if len(body) < MIN_TEXT_CHARS:
        return None  # 多半是扫描版，整页是图片
    if reference is None:
        reference = Reference(key=pdf.stem, title=pdf.stem, citation="", page="", pdf="")
    return reference_markdown(reference, body, origin="pdf")


def page_to_markdown(page: Path, reference: Reference) -> str | None:
    body = html_to_text(page.read_text(encoding="utf-8"))
    if len(body) < MIN_TEXT_CHARS:
        return None  # 版式认不出来：退回 PDF
    return reference_markdown(reference, body, origin="网页版")


def run(
    directory: Path,
    *,
    deadline_seconds: float,
    timeout: float,
    workers: int = 4,
    out=print,
) -> dict[str, int]:
    try:
        references = load_manifest(directory)
    except FileNotFoundError:
        references = []
    started = time.monotonic()
    # 一篇握不上手就当网络不通：没开始的都留到下次启动，免得每篇再等一轮握手超时
    network_down = threading.Event()

    def source_missing(reference: Reference) -> bool:
        """这篇要联网：.md 不是最新的，而本机又没有该用的原文（有网页版的要网页版，没有的要 PDF）。"""
        if _current(directory / f"{reference.key}.md", reference):
            return False
        wanted = directory / f"{reference.key}.{'html' if reference.html else 'pdf'}"
        return not wanted.exists()

    missing = [reference for reference in references if source_missing(reference)]
    if missing and not site_reachable(missing[0].html or missing[0].pdf):
        network_down.set()
        out("    [!] 连不上期刊官网，这次先不下载，下次启动再下")

    def give_up_network(exc: Exception) -> None:
        if not network_down.is_set():
            network_down.set()
            out(f"    [!] 连不上期刊官网（{exc}），这次先不下了")

    def can_download() -> bool:
        return not network_down.is_set() and time.monotonic() - started <= deadline_seconds

    def prepare(reference: Reference) -> str:
        markdown = directory / f"{reference.key}.md"
        pdf = directory / f"{reference.key}.pdf"
        page = directory / f"{reference.key}.html"
        if _current(markdown, reference):
            return "ready"
        existed = markdown.exists()
        downloaded = False

        def done() -> str:
            return "downloaded" if downloaded else ("reextracted" if existed else "ready")

        # 1. 有网页版先用网页版：表格、公式都完整
        if reference.html:
            try:
                if not page.exists() and can_download():
                    write_text_atomically(page, download_page(reference, timeout=timeout))
                    downloaded = True
                if page.exists():
                    text = page_to_markdown(page, reference)
                    if text is not None:
                        write_text_atomically(markdown, text)
                        return done()
                    out(f"    [!] 《{reference.title}》网页版认不出正文，改用 PDF")
            except NetworkUnreachable as exc:
                give_up_network(exc)
            except Exception as exc:  # noqa: BLE001 —— 网页版不行还有 PDF
                out(f"    [!] 《{reference.title}》网页版没取到（{exc}），改用 PDF")

        # 2. PDF
        try:
            if not pdf.exists():
                if not can_download():
                    return "postponed"
                try:
                    write_bytes_atomically(pdf, download_pdf(reference, timeout=timeout))
                except NetworkUnreachable as exc:
                    give_up_network(exc)
                    return "postponed"
                downloaded = True
            text = pdf_to_markdown(pdf, reference)
            if text is None:
                out(f"    [!] 《{reference.title}》抽不出文字（可能是扫描版），这篇先不用")
                return "failed"
            write_text_atomically(markdown, text)
            return done()
        except Exception as exc:  # noqa: BLE001 —— 一篇失败不影响别的，也不影响启动
            out(f"    [!] 《{reference.title}》没下好：{exc}")
            return "failed"

    counts = {"ready": 0, "downloaded": 0, "reextracted": 0, "converted": 0, "failed": 0, "postponed": 0}
    # 第一次要下 14 篇：一篇篇下要 40 秒，4 篇并发约十来秒（期刊站对单个来源不做限速）
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for status in pool.map(prepare, references):
            counts[status] += 1
    counts["ready"] += counts["downloaded"] + counts["reextracted"]

    # 自己放进来的 PDF（不在清单上）：抽成同名 .md。已经有 .md 的，只有当初是本脚本抽的
    # （带抽取版本标记）、而且版本旧了才重抽——手写的同名 .md 不碰
    listed = {reference.key for reference in references}
    for pdf in sorted(directory.glob("*.pdf")):
        markdown = directory / f"{pdf.stem}.md"
        if pdf.stem in listed or _current(markdown):
            continue
        if markdown.exists() and not has_extract_mark(markdown.read_text(encoding="utf-8")):
            continue
        try:
            text = pdf_to_markdown(pdf, None)
            if text is None:
                out(f"    [!] {pdf.name} 抽不出文字（可能是扫描版），跳过")
                counts["failed"] += 1
                continue
            write_text_atomically(markdown, text)
            counts["converted"] += 1
            counts["ready"] += 1
        except Exception as exc:  # noqa: BLE001
            out(f"    [!] {pdf.name} 抽文字失败：{exc}")
            counts["failed"] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载参考文献并抽成文字")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="参考文献目录")
    parser.add_argument("--deadline", type=float, default=60.0, help="下载最多花多少秒，剩下的下次再下")
    parser.add_argument("--timeout", type=float, default=30.0, help="单篇下载超时（秒）")
    args = parser.parse_args(argv)

    if not args.dir.is_dir():
        print(f"    没有参考文献目录 {args.dir}，跳过")
        return 0
    try:
        counts = run(args.dir, deadline_seconds=args.deadline, timeout=args.timeout)
    except (ValueError, KeyError, TypeError) as exc:  # json.JSONDecodeError 是 ValueError
        # 清单是仓库里的文件，写错了要让人看见，但别在启动输出里甩一屏 traceback
        print(f"    [!] references/{MANIFEST_NAME} 写错了：{exc!r}")
        return 1
    summary = f"    参考文献 {counts['ready']} 篇就绪"
    if counts["downloaded"] or counts["converted"] or counts["reextracted"]:
        summary += (
            f"（这次新下载 {counts['downloaded']} 篇、按新规则重抽 {counts['reextracted']} 篇、"
            f"新抽取 {counts['converted']} 篇）"
        )
    if counts["postponed"]:
        summary += f"，{counts['postponed']} 篇这次没下，下次启动再下"
    if counts["failed"]:
        summary += f"，{counts['failed']} 篇失败（见上）"
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
