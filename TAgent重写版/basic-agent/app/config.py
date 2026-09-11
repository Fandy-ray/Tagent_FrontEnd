"""集中式配置：所有环境变量与数据文件路径在此收口。

分层规则：任何层都可以 import 本模块；本模块不 import 任何业务模块。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


# basic-agent/ 的绝对路径。本文件在 basic-agent/app/config.py，故上溯两级。
#
# 数据文件（config/、text_db/、book1.md）都挂在 basic-agent/ 根下。
# 不要在其他模块里用 Path(__file__).parent 去定位它们——模块一旦下移一层，
# 相对路径就会指向错误目录，而且服务照样能起、测试也未必报错，
# 只是知识库变成空的。一律从这里取。
BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_MODEL_PROVIDERS_PATH = BASE_DIR / "config" / "model_providers.json"
DEFAULT_TEXT_DB_DIR = BASE_DIR / "text_db"
DEFAULT_KNOWLEDGE_FILE = BASE_DIR / "book1.md"


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


# OpenNotebook 起的是两个进程：8502 是 Streamlit 页面，5055 才是 REST API。
# app/rag/opennotebook_kb.py 打的全是 /api/*，只有 5055 认。
NOTEBOOK_UI_PORT = 8502
NOTEBOOK_API_PORT = 5055


def normalize_notebook_url(raw: str, *, rewrite_ui_port: bool = True) -> str:
    """把人从浏览器里抄来的地址换算成 OpenNotebook 的接口基址。

    要纠正两件事：
    1. `/notebooks` 是页面路径，接口基址不带它；
    2. 8502 是 Streamlit 页面端口，拿它打 /api/* 会收到一坨 HTML。

    第 2 条尤其要命：CompositeKnowledgeBase 遇到失败的来源是**静默跳过**的，
    配错端口的表现不是报错，而是"答疑一切正常，但笔记本里的内容一条都检索不到"。
    所以这里直接把 8502 改写成 5055。已经明确给了 API 地址的走
    rewrite_ui_port=False，不猜。
    """
    value = (raw or "").strip().rstrip("/")
    if not value:
        return ""

    lowered = value.lower()
    for suffix in ("/notebooks", "/notebook"):
        if lowered.endswith(suffix):
            value = value[: -len(suffix)]
            break

    value = value.rstrip("/")
    if not value:
        return ""

    # 没写 scheme 时 urlsplit 会把 "localhost:8502" 的 localhost 当成 scheme。
    parts = urlsplit(value if "://" in value else f"http://{value}")
    try:
        port = parts.port
    except ValueError:
        return value
    if not parts.hostname:
        return value

    if rewrite_ui_port and port == NOTEBOOK_UI_PORT:
        port = NOTEBOOK_API_PORT

    # hostname 已经去掉了 IPv6 的方括号，拼回去要补上。
    netloc = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    if port is not None:
        netloc = f"{netloc}:{port}"
    # 别把 URL 里的账号密码悄悄丢了。
    if parts.username:
        credentials = parts.username
        if parts.password:
            credentials = f"{credentials}:{parts.password}"
        netloc = f"{credentials}@{netloc}"

    return urlunsplit((parts.scheme or "http", netloc, parts.path.rstrip("/"), "", ""))


@dataclass(frozen=True)
class AgentConfig:
    """服务级配置。由 from_env() 在启动时构造一次，之后只读。"""

    host: str = "127.0.0.1"
    port: int = 5000
    use_waitress: bool = True
    waitress_threads: int = 8

    admin_token: str = ""
    internal_token: str = ""
    max_content_length: int = 1024 * 1024

    model_providers_path: Path = DEFAULT_MODEL_PROVIDERS_PATH
    text_db_dir: Path = DEFAULT_TEXT_DB_DIR
    knowledge_file: Path = DEFAULT_KNOWLEDGE_FILE

    # local = 只读 book1.md；notebook = 只读 OpenNotebook；
    # composite = 两边一起检索。没配 OPEN_NOTEBOOK_URL 时一律 local。
    knowledge_source: str = "local"
    # 已经过 normalize_notebook_url，指向 REST API（默认 5055），不是 Streamlit 页面。
    notebook_url: str = ""
    notebook_token: str = ""

    exam_max_concurrent_llm: int = 2
    llm_max_orphan_tasks: int = 2

    @classmethod
    def from_env(cls) -> "AgentConfig":
        # 显式给了 API 地址就照用；只给了浏览器地址才去猜端口。
        notebook_url = normalize_notebook_url(
            _env("OPEN_NOTEBOOK_API_URL", "NOTEBOOK_API_URL"), rewrite_ui_port=False
        ) or normalize_notebook_url(_env("OPEN_NOTEBOOK_URL", "NOTEBOOK_URL"))
        requested = _env("KNOWLEDGE_SOURCE").strip().lower()
        if requested in {"local", "notebook", "composite"}:
            knowledge_source = requested
        elif notebook_url:
            knowledge_source = "composite"
        else:
            knowledge_source = "local"
        if knowledge_source in {"notebook", "composite"} and not notebook_url:
            knowledge_source = "local"
        return cls(
            host=_env("BASIC_AGENT_HOST", "AGENT_HOST", default="127.0.0.1"),
            port=int(_env("BASIC_AGENT_PORT", "AGENT_PORT", default="5000")),
            use_waitress=os.getenv("USE_WAITRESS", "1") == "1",
            admin_token=os.getenv("AGENT_ADMIN_TOKEN", ""),
            internal_token=os.getenv("AGENT_INTERNAL_TOKEN", ""),
            model_providers_path=Path(
                os.getenv("MODEL_PROVIDERS_PATH") or DEFAULT_MODEL_PROVIDERS_PATH
            ),
            text_db_dir=DEFAULT_TEXT_DB_DIR,
            knowledge_file=DEFAULT_KNOWLEDGE_FILE,
            knowledge_source=knowledge_source,
            notebook_url=notebook_url,
            notebook_token=_env(
                "OPEN_NOTEBOOK_PASSWORD", "OPEN_NOTEBOOK_TOKEN", "NOTEBOOK_TOKEN"
            ),
            exam_max_concurrent_llm=int(os.getenv("EXAM_MAX_CONCURRENT_LLM", "2")),
            llm_max_orphan_tasks=int(os.getenv("LLM_MAX_ORPHAN_TASKS", "2")),
        )


# ====================== LLM 调用超时与预算（压测所得，勿凭直觉改） ======================
#
# 以下数值全部来自 A/B 压测，改动前先看注释里的实测数据。
#
# ！！读这一段之前先看清楚数据的出处 ！！
#
# 本段及 exam_service.py 里带具体秒数的结论，都来自**交接包导入之前**的一轮压测
# （各 3~5 轮 A/B，同材料同模型）。那轮用的是哪个模型、什么时候测的，仓库里没记——
# git 历史在 d8cf81a 被压成了一次性导入，查不回去。所以这些秒数只能当**相对结论**
# 用（并行快过串行、长上下文更慢、精简 prompt 反而更慢），不能当**绝对水位**用。
#
# 2026-09-11 在 DeepSeek（deepseek-chat）上复测的绝对值，比老数据快一个数量级：
#     整卷出卷 8~9s（老数据并行中位 68.4s）
#     闪卡出卷 6~10s
#     整卷判卷 ~11s
# 样本只有 2 轮，不足以取代上面那轮 3~5 轮的 A/B，**没有**据此改任何超时与预算：
# 超时是给尾部留的余量，按快的那次收紧只会在慢的那次炸掉。
#
# 但下面这些按老数据定的尺寸，前提已经不一定成立，后来人要调时心里有数：
#     EXAM_LLM_TIMEOUT / EXAM_LLM_BUDGET、FLASH_*_SHARDS 的分片数、
#     exam_service.py 里出卷三段的 max_tokens
# 真要重新定尺寸，请照老注释的做法重跑 A/B（同材料同模型、各 3~5 轮取中位），
# 把模型名和日期一起写进注释——别再留一组无出处的秒数给下一个人。

QUIZ_GENERATION_TIMEOUT_SECONDS = 20
EXAM_SAMPLE_K = 10

# 分三段出卷后同一份参考材料要发三次，上下文越长每段前置处理越久。
# 实测 6000 字上下文时单段要 ~58s，压到 4500 字可明显回落。
EXAM_CONTEXT_CHAR_LIMIT = 4500

# 单段耗时波动近 1.8 倍（同 prompt 同输出量重复 4 次：46.0/46.0/54.9/83.5s），
# 按单次测量定超时必然时好时坏，故按尾部再留余量：
# 单段 150s，总预算 480s（3 段最坏 3×155=465s）。
#
# 别再想着"精简 prompt 提速"——A/B 压测（各 3 轮）结果是反的：
#   填空 55.3s → 87.0s，选择 31.8s → 69.4s，解答 18.2s → 33.8s
#   且填空的考点重复从 0 涨到 2.67（10 道里近 3 道撞车）
# 详细的规则收窄了模型的搜索空间，反而更快也更稳；压成干条目后它要自己揣摩。
# 三段中位合计约 105s，真要提速应从"三段并行"入手，不是改 prompt。
EXAM_LLM_TIMEOUT = 150
EXAM_LLM_BUDGET = 480
EXAM_MIN_ATTEMPT_TIMEOUT = 30

GRADE_LLM_TIMEOUT = 55
GRADE_LLM_BUDGET = 190
# 判分分批上限。一次只让模型面对少量同类题：ID 集合小、评分准则单一，
# 比"一次评十几道混合题"稳得多。最坏 3 批（2 批解答 + 1 批填空复核）。
GRADE_ESSAY_BATCH = 2
GRADE_CLOZE_BATCH = 10
GRADE_MIN_ATTEMPT_TIMEOUT = 20


# ====================== 闪卡（填空 + 选择，分片并发） ======================
#
# 闪卡不是"整卷的填空段"，而是把那一段再拆细：整卷的填空段一次要 8~10 张、
# 配 4500 字上下文（老那轮压测里中位 55.3s，出处见本段开头的警示）；闪卡把
# 两个变量同时砍到三分之一——每片 3~4 张卡配 ~1600 字材料，三片并发发出。
#
# 分片数是按那组老数据定的。2026-09-11 在 DeepSeek 上实测，闪卡 6~10s、整卷
# 8~9s，两者已经拉不开差距——**拆闪卡的理由现在是交互形态（只出能本地判定的
# 题型、随时开随时停），不再是快**。前端文案已据此去掉了所有秒数，这里同理：
# 不要再把"目标 20~30s"当成对用户的承诺写进 UI。
#
# 依据与整卷"三段并行"是同一条：单次调用的输出 token 量与上下文长度才是
# 主要耗时来源（见上面 EXAM_CONTEXT_CHAR_LIMIT 的注释：6000 字上下文单段
# 要 ~58s，压到 4500 明显回落）。不要靠精简 prompt 提速，那条路已经被证伪。
# 闪卡一组里两种卡：填空（打字或翻面自评）+ 选择（点一下当场判）。
# 两类各自占几片 —— 加起来就是并发数，和整卷的三段并行同一个量级。
FLASH_CLOZE_SHARDS = 2
FLASH_CHOICE_SHARDS = 1
FLASH_SHARD_COUNT = FLASH_CLOZE_SHARDS + FLASH_CHOICE_SHARDS
FLASH_SHARD_CARD_RANGE = (3, 4)
# 三片并发看不到彼此，撞考点在所难免，去重后张数会掉。低于这个数才算失败，
# 不要设成 shard_count * card_range[0]，那样一旦去掉两张就整次报错。
FLASH_DECK_MIN_CARDS = 6
FLASH_CONTEXT_CHAR_LIMIT = 1600  # 每片
FLASH_LLM_TIMEOUT = 90
FLASH_LLM_BUDGET = 200
FLASH_MIN_ATTEMPT_TIMEOUT = 25

# 三个知识库实现拼接出卷上下文时用的分隔符。闪卡要按它把整段上下文切回
# 独立片段再分发给各片，所以提到这里共享，而不是各自硬编码。
EXAM_CONTEXT_SEPARATOR = "\n\n---\n\n"
