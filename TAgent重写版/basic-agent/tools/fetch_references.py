"""下载参考文献并抽成文字：一键启动在起 basic-agent 之前会跑一次。

    uv run python tools/fetch_references.py            # 在 basic-agent 目录下
    uv run python tools/fetch_references.py --deadline 300

- 篇目在 references/manifest.json；已经有 .md 的跳过，所以只有第一次要等。
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
    MANIFEST_NAME,
    MIN_TEXT_CHARS,
    Reference,
    clean_paper_text,
    extract_pdf_pages,
    load_manifest,
    reference_markdown,
    write_bytes_atomically,
    write_text_atomically,
)


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


def download_pdf(reference: Reference, *, timeout: float) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Referer": reference.page or reference.pdf}
    errors: list[Exception] = []
    # 先直连，再走环境变量里的代理：国内期刊站走境外代理会 403
    for trust_env in (False, True):
        try:
            with httpx.Client(
                trust_env=trust_env,
                timeout=httpx.Timeout(timeout, connect=min(CONNECT_TIMEOUT, timeout)),
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(reference.pdf)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise ValueError(f"返回的不是 PDF（{response.headers.get('content-type', '?')}）")
            return response.content
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(exc)
    if all(isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)) for exc in errors):
        raise NetworkUnreachable(str(errors[-1]) or type(errors[-1]).__name__)
    raise RuntimeError(str(errors[-1]))


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
    return reference_markdown(reference, body)


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
    missing = [r for r in references if not (directory / f"{r.key}.md").exists() and not (directory / f"{r.key}.pdf").exists()]
    if missing and not site_reachable(missing[0].pdf):
        network_down.set()
        out("    [!] 连不上期刊官网，这次先不下载，下次启动再下")

    def prepare(reference: Reference) -> str:
        markdown = directory / f"{reference.key}.md"
        pdf = directory / f"{reference.key}.pdf"
        if markdown.exists() and markdown.stat().st_size > 0:
            return "ready"
        downloaded = False
        try:
            if not pdf.exists():
                if network_down.is_set() or time.monotonic() - started > deadline_seconds:
                    return "postponed"
                try:
                    write_bytes_atomically(pdf, download_pdf(reference, timeout=timeout))
                except NetworkUnreachable as exc:
                    if not network_down.is_set():
                        network_down.set()
                        out(f"    [!] 连不上期刊官网（{exc}），这次先不下了")
                    return "postponed"
                downloaded = True
            text = pdf_to_markdown(pdf, reference)
            if text is None:
                out(f"    [!] 《{reference.title}》抽不出文字（可能是扫描版），这篇先不用")
                return "failed"
            write_text_atomically(markdown, text)
            return "downloaded" if downloaded else "ready"
        except Exception as exc:  # noqa: BLE001 —— 一篇失败不影响别的，也不影响启动
            out(f"    [!] 《{reference.title}》没下好：{exc}")
            return "failed"

    counts = {"ready": 0, "downloaded": 0, "converted": 0, "failed": 0, "postponed": 0}
    # 第一次要下 14 篇：一篇篇下要 40 秒，4 篇并发约十来秒（期刊站对单个来源不做限速）
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for status in pool.map(prepare, references):
            counts[status] += 1
    counts["ready"] += counts["downloaded"]

    # 自己放进来的 PDF（不在清单上）：抽成同名 .md
    listed = {reference.key for reference in references}
    for pdf in sorted(directory.glob("*.pdf")):
        if pdf.stem in listed or (directory / f"{pdf.stem}.md").exists():
            continue
        try:
            text = pdf_to_markdown(pdf, None)
            if text is None:
                out(f"    [!] {pdf.name} 抽不出文字（可能是扫描版），跳过")
                counts["failed"] += 1
                continue
            write_text_atomically(directory / f"{pdf.stem}.md", text)
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
    if counts["downloaded"] or counts["converted"]:
        summary += f"（这次新下载 {counts['downloaded']} 篇、新抽取 {counts['converted']} 篇）"
    if counts["postponed"]:
        summary += f"，{counts['postponed']} 篇这次没下，下次启动再下"
    if counts["failed"]:
        summary += f"，{counts['failed']} 篇失败（见上）"
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
