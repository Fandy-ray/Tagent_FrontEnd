# basic-agent 分层重构方案

把 `basic-agent/` 从 20 个扁平模块重构成 Spring Boot 式的分层包结构。

**状态**：方案，未实施。
**基线**：`master` @ `a27288d`，99 个测试可收集通过。
**入口约束**：`python main.py` 必须继续可用（`scripts/start.ps1:301`、`deploy/systemd/tagent-basic-agent.service`）。

---

## 1. 结论

可以做，而且底子比想象中好。现在已经有 blueprint 分组、pydantic schema、registry 仓储、client factory —— 缺的不是零件，是**归位**和**方向约束**。

真正要解决的是 6 个耦合点，其中前两个是核心，剩下四个是顺带的整理。

---

## 2. 现状诊断

### 2.1 controller 调 controller（核心问题一）

`internal_routes.py` 直接 import 了另外三个 controller 的函数：

```
internal_routes.py:5   from agent_routes import _optional_text, _required_text
internal_routes.py:6   from exam_routes import generate_exam_response, review_exam_response
internal_routes.py:8   from openai_routes import chat_completion_response
```

相当于 `InternalController` 去 `new AgentController()` 再调它的 private 方法。`/rag/query`、`/quiz/generate` 这几条路由的响应体在 `agent_routes.py` 和 `internal_routes.py` 里各写了一遍，已经开始复制粘贴。

**根因**：业务逻辑写在了 controller 方法里，而不是 service 里。两个 controller 需要同一段逻辑时，只能互相 import。

**正解**：逻辑下沉到 service，两个 controller 各自调 service；共用的参数校验放 `api/validators.py`；共用的响应包装放 `api/response.py`。

### 2.2 God Service（核心问题二）

`rag_utils.py` 一个文件 1179 行，`LangChainRAGSimulator` 一个类 630 行，干了 5 件互不相干的事：

| 职责 | 行数 | 该属于 |
|---|---|---|
| RAG 检索 + 对话 | ~90 | ChatService |
| 单题出题 / 判分 | ~80 | QuizService |
| 整卷生成（三段并发） | ~130 | ExamService |
| 整卷判分（本地 + LLM 分批） | ~230 | ExamService |
| 知识库加载 / 切块 / 采样 | ~110 | KnowledgeBase |

外加 40 多个模块级函数，其中 **Markdown 清洗独占 179 行**（`rag_utils.py:987-1165`），跟 RAG 毫无关系，纯粹是文本工具。

### 2.3 层次倒挂

业务异常定义在仓储模块里：

```
exam_store.py:19-70   ExamServiceError / InvalidExamRequestError / ModelMismatchError
                      / ExamGoneError / ExamBusyError / UpstreamLLMError / UpstreamTimeoutError
```

然后 controller（`exam_routes.py:9`）、service（`rag_utils.py:43`）、基础设施（`llm_json.py:29`）全都反向 import 一个"缓存模块"来拿异常类。异常属于领域，不属于任何一层。

### 2.4 `route_utils.py` 是杂物袋

一个文件 5 种职责：错误响应格式化、JSON body 解析、消息校验、双 token 鉴权、服务定位（`get_agent_service` / `select_provider` / `invalidate_provider`）、时间戳转换。

### 2.5 不是 Python 包

`basic-agent` 带连字符，不能当包名；所有 import 都是平级的 `from exam_store import ...`，测试靠 `sys.path` hack 才能跑：

```
tests/conftest.py:5        sys.path.insert(0, ...)
test_main_routes.py:8      sys.path.insert(0, ...)
test_model_clients.py:8    sys.path.insert(0, ...)
test_model_config.py:11    sys.path.insert(0, ...)
test_rag_concurrency.py:7  sys.path.insert(0, ...)
```

5 个文件重复同一个 hack。

### 2.6 配置散落 + prompt 硬编码

`os.getenv` 分布在 5 个模块（`app_factory` 2 处、`main` 3 处、`llm_json` 1 处、`model_config` 2 处、`rag_utils` 1 处），没有统一的配置对象。prompt 模板（`rag_utils.py:80-207`）和业务代码混在一起。

---

## 3. 目标结构

```
basic-agent/
├── main.py                          启动类（保持原位，部署脚本零改动）
├── app/
│   ├── factory.py                   create_app()          ← app_factory.py
│   ├── config.py                    @Configuration，所有 getenv 收口
│   ├── container.py                 依赖装配：build_services(config)
│   │
│   ├── api/                         @RestController
│   │   ├── __init__.py              register_blueprints(app)
│   │   ├── health.py                ← health_routes.py
│   │   ├── openai_compat.py         ← openai_routes.py
│   │   ├── agent.py                 ← agent_routes.py
│   │   ├── exam.py                  ← exam_routes.py
│   │   ├── admin.py                 ← admin_routes.py
│   │   ├── internal.py              ← internal_routes.py（不再 import 兄弟 controller）
│   │   ├── deps.py                  唯一允许碰 current_app.extensions 的地方
│   │   ├── validators.py            参数校验（合并 route_utils + agent_routes 私有函数）
│   │   ├── security.py              require_admin_token / require_internal_token
│   │   ├── response.py              统一 {code,msg,data,model} 包装
│   │   └── error_handler.py         @ControllerAdvice ← app_factory 里的 5 个 errorhandler
│   │
│   ├── service/                     @Service
│   │   ├── chat_service.py          answer / stream_answer
│   │   ├── quiz_service.py          generate_quiz / review_quiz
│   │   ├── exam_service.py          generate_exam / review_exam
│   │   └── provider_service.py      provider 增删改 + 缓存失效编排
│   │
│   ├── rag/
│   │   ├── knowledge_base.py        知识库加载、切块、检索、采样
│   │   └── graph.py                 LangGraph 状态图 + RAGState
│   │
│   ├── repository/                  @Repository
│   │   ├── provider_repository.py   JSON 文件读写 ← model_config 的持久化部分
│   │   └── exam_cache.py            ← exam_store.ExamCache + LLMGate
│   │
│   ├── schema/                      DTO / Entity
│   │   ├── exam.py                  ← exam_schema.py（整体搬，内部已经很干净）
│   │   ├── quiz.py                  ← rag_utils.py:212-237
│   │   └── provider.py              ← ModelProvider / OpenAICompatibleConfig
│   │
│   ├── infra/                       外部系统客户端
│   │   ├── model_client_factory.py  ← model_clients.py
│   │   ├── llm_json.py              ← llm_json.py
│   │   └── upstream_errors.py       上游异常 → 领域异常的翻译
│   │
│   ├── prompts/
│   │   ├── exam_prompts.py          ← rag_utils.py:80-207
│   │   ├── quiz_prompts.py          ← rag_utils.py 内联的 system prompt
│   │   └── chat_prompts.py          ← _build_prompt_messages 里的模板
│   │
│   ├── errors/                      领域异常，不属于任何层
│   │   ├── api_errors.py            ← agent_errors.py
│   │   └── exam_errors.py           ← exam_store.py:19-70
│   │
│   └── util/
│       ├── markdown_sanitizer.py    ← rag_utils.py:987-1165（179 行）
│       └── text.py                  ← _content_text 等
│
├── tools/                           离线脚本，不是服务的一部分
│   ├── pdf_ocr.py
│   ├── pdf.py
│   ├── state_graph_demo.py          ← state_graph.py（现在是个 demo，import 时就执行）
│   └── smoke_rag_query.py           ← test.py（手工冒烟脚本，名字会被 pytest 误收）
│
├── config/model_providers.json      不动
├── text_db/ · book1.md              不动
└── tests/
    ├── conftest.py                  删掉 sys.path hack
    ├── api/ · service/ · repository/ · schema/
```

`test.py` 要改名。它是打 `/rag/query` 的手工冒烟脚本（25 行，依赖 `requests`，需要服务已启动），但 `pyproject.toml` 的 `python_files = ["test_*.py"]` 之外 pytest 默认还会认 `test.py` 这类文件名，放在 `testpaths = ["."]` 根目录下容易被误收集。搬到 `tools/smoke_rag_query.py`。

---

## 4. 迁移映射

### 4.1 整体搬家（改 import 即可）

| 现在 | 去处 | 备注 |
|---|---|---|
| `health_routes.py` | `app/api/health.py` | 10 行，无脑搬 |
| `agent_errors.py` | `app/errors/api_errors.py` | |
| `exam_schema.py` | `app/schema/exam.py` | 637 行但内聚性好，不拆 |
| `model_clients.py` | `app/infra/model_client_factory.py` | |
| `llm_json.py` | `app/infra/llm_json.py` | 只改异常 import 来源 |
| `pdf.py` · `pdf_ocr.py` | `tools/` | 服务运行时用不到 |
| `state_graph.py` | `tools/state_graph_demo.py` | import 时就跑 `graph_builder.compile()`，是脚本不是模块 |

### 4.2 需要拆分

**`exam_store.py`（4188 字节）→ 两处**

- `:19-70` 七个异常类 → `app/errors/exam_errors.py`
- `:73-160` `StoredExam` / `ExamCache` / `LLMGate` → `app/repository/exam_cache.py`

**`model_config.py`（494 行）→ 三处**

- `ModelProviderRegistry` 的文件读写（`:151-254`，含原子写 tempfile）→ `app/repository/provider_repository.py`
- `ModelProvider` / `OpenAICompatibleConfig` dataclass（`:24-57`）→ `app/schema/provider.py`
- 校验与归一化（`_normalize_provider` `:256-311`、`_normalize_base_url` `:377`、`_normalize_temperature` `:387`、`parse_ephemeral_provider` `:405`）→ `app/service/provider_service.py`

**`route_utils.py`（4424 字节）→ 四处**

| 函数 | 去处 |
|---|---|
| `error_response` | `app/api/error_handler.py` |
| `json_body` · `validate_messages` | `app/api/validators.py` |
| `require_admin_token` · `require_internal_token` | `app/api/security.py` |
| `select_provider` · `get_agent_service` · `invalidate_provider` | `app/api/deps.py` |
| `timestamp_to_epoch` | `app/util/text.py` |

**`app_factory.py` → 三处**

- `create_app` 主体 → `app/factory.py`
- 5 个 `@app.errorhandler` → `app/api/error_handler.py::register_error_handlers(app)`
- `os.getenv` 配置 → `app/config.py`
- 服务实例化（`registry` / `agent_service`）→ `app/container.py`

### 4.3 `rag_utils.py` 逐段拆解

1179 行拆到 9 个文件。**行号对应重构前的 `rag_utils.py`。**

| 源行号 | 内容 | 目标文件 |
|---|---|---|
| `55-78` | 超时/预算/批次常量 | `app/config.py`（**注释必须整段带走**，见 §6.4） |
| `80-207` | JSON spec + 6 个 prompt builder + `_covered_block` | `app/prompts/exam_prompts.py` |
| `208-210` | `_chunked` | `app/util/text.py` |
| `212-237` | `QuizQuestion` / `QuizReview` / `QuizResult` / `QuizReviewResult` | `app/schema/quiz.py` |
| `238-246` | `RAGState` | `app/rag/graph.py` |
| `276-314` | `answer` / `stream_answer` | `app/service/chat_service.py` |
| `315-393` | `generate_quiz` / `review_quiz` | `app/service/quiz_service.py` |
| `394-592` | `_sample_exam_chunks` / `generate_exam` / `_grade_batches` | `app/service/exam_service.py` |
| `594-748` | `review_exam` | `app/service/exam_service.py` |
| `750-767` | `generate_quiz_question` / `review_quiz_answer` / `run_simulation` | **删除**（已确认全仓零调用方，含测试） |
| `768-790` | `create_llm` / `invalidate_provider` / `close` / `warm_up` | 各 service 的生命周期方法 |
| `791-806` | `_retrieve_node` / `_answer_node` | `app/rag/graph.py` |
| `807-855` | `_retrieve_context` / `_ensure_knowledge_base` / `_ensure_knowledge_chunks` / `_build_text_database` | `app/rag/knowledge_base.py` |
| `856-878` | `_build_prompt_messages` / `_last_user_message` / `_provider_for_legacy_llm` | `app/prompts/chat_prompts.py`（第三个删） |
| `879-892` | `_content_text` | `app/util/text.py` |
| `893-908` | `_invoke_quiz_model` | `app/service/quiz_service.py` |
| `909-980` | `_display_document` / `_select_quiz_documents` / `_join_*` / `_fallback_quiz_from_reference` / `_first_heading` | `app/rag/knowledge_base.py` |
| `981-986` · `1166-1179` | `_is_timeout_error` / `_translate_upstream_error` | `app/infra/upstream_errors.py` |
| `987-1165` | Markdown 清洗全家桶（表格修复、LaTeX 配对、截断） | `app/util/markdown_sanitizer.py` |

拆完 `rag_utils.py` 消失，`LangChainRAGSimulator` 这个名字也一并退休 —— 它现在既不 simulate 也不只做 RAG。

---

## 5. 分阶段执行

每个阶段结束都跑一遍全量测试，绿了才提交。**不要合并阶段。**

```bash
cd basic-agent && .venv/Scripts/python.exe -m pytest -q
```

### 阶段 0 · 建包与安全网（约 30 分钟）

1. 建 `app/` 包骨架 + 所有 `__init__.py`
2. `main.py` 改成 `from app.factory import create_app`
3. `pyproject.toml` 加 `[tool.pytest.ini_options] pythonpath = ["."]`，删掉 5 个文件里的 `sys.path.insert`
4. **不移动任何业务文件**，只验证包结构和测试路径成立

验收：99 个测试全绿，`python main.py` 能起来，`/health` 返回 200。

### 阶段 1 · 无逻辑变更的搬家（约 1 小时）

按 §4.1 搬 7 个文件，按 §4.2 拆 `exam_store` / `model_config` / `route_utils` / `app_factory`。

**只改 import 路径和文件位置，一行逻辑都不动。** 这一步的 diff 应该全是 `from X import Y` → `from app.x.y import Y`。

验收：99 个测试全绿（测试文件只改 import）。

### 阶段 2 · 解 controller 互调（约 1.5 小时）

1. 把 `agent_routes` / `internal_routes` 里重复的响应组装抽到 `app/api/response.py`
2. `_required_text` / `_optional_text` → `app/api/validators.py`
3. `chat_completion_response` / `generate_exam_response` / `review_exam_response` 里的业务部分下沉到对应 service，controller 只留"解析 → 调 service → 包装响应"
4. 删掉 `internal.py` 对其他 controller 的 import

验收：`grep -n "from app.api" app/api/*.py` 只应命中 `deps` / `validators` / `security` / `response`，不应命中任何具体路由模块。

### 阶段 3 · 拆 God Service（约 3 小时，风险最高）

按 §4.3 的表逐段拆。建议顺序（从依赖最少的开始）：

1. `util/markdown_sanitizer.py`（179 行，纯函数，零依赖）
2. `util/text.py` + `infra/upstream_errors.py`
3. `prompts/`（纯字符串）
4. `schema/quiz.py`
5. `rag/knowledge_base.py` + `rag/graph.py`
6. `service/chat_service.py`
7. `service/quiz_service.py`
8. `service/exam_service.py`（最大，放最后）

每拆一个跑一次测试。**测试 fixture 要同步改**，见 §6.1。

### 阶段 4 · 配置收口 + 显式依赖注入（约 1 小时）

1. `app/config.py` 定义 `AgentConfig` dataclass，`from_env()` 收拢全部 `os.getenv`
2. `app/container.py` 显式装配：`build_services(config) -> Services`
3. service 构造函数接收依赖，不再自己 `os.getenv` / 自己 new `ModelClientFactory`
4. `current_app.extensions` 只在 `app/api/deps.py` 里出现

验收：`grep -rn "os.getenv" app/ | grep -v config.py` 应该是空的。

---

## 6. 风险清单

### 6.1 测试与 God Class 强耦合 ⚠️ 最高风险

三处测试绕过构造函数直接造对象：

```
tests/test_exam_model_routing.py:76    sim = object.__new__(rag_utils.LangChainRAGSimulator)
tests/test_review_exam_wiring.py:141   sim = object.__new__(rag_utils.LangChainRAGSimulator)
tests/test_review_exam_wiring.py:238   sim = object.__new__(rag_utils.LangChainRAGSimulator)
```

两处按模块属性打桩：

```
tests/test_exam_model_routing.py:88    monkeypatch.setattr(rag_utils, "call_json_llm", ...)
tests/test_exam_model_routing.py:101   monkeypatch.setattr(rag_utils, "call_json_llm", ...)
```

一处直接 import 6 个私有函数：

```
test_rag_concurrency.py:12   from rag_utils import (LangChainRAGSimulator, _clean_generated_markdown,
                             _clean_reference_for_display, _join_quiz_context,
                             _join_quiz_display, _select_quiz_documents)
```

拆成 3 个 service 后，`object.__new__` 那套 fixture 必须重写；monkeypatch 目标要改成 `app.service.exam_service.call_json_llm`。

**缓解**：阶段 3 拆分时，**先给 `ExamService` 写一个真正的构造函数并让测试用它**，再动内部实现。顺序反了会同时改测试和实现，出问题分不清是哪边。

### 6.2 `__file__` 相对路径会断 ⚠️

三处用 `Path(__file__).resolve().parent` 定位数据文件，文件下移一层后全部指向错误目录：

```
model_config.py:17    DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "model_providers.json"
rag_utils.py:257      self.text_db_dir = Path(__file__).parent / "text_db"
rag_utils.py:837      self._build_text_database(Path(__file__).parent / "book1.md")
```

**必须在阶段 0 就改掉**：在 `app/config.py` 里定义一个 `BASE_DIR = Path(__file__).resolve().parent.parent`，所有数据路径从 config 取。漏掉这条，服务能起但知识库是空的，而且测试可能不报错。

### 6.3 部署入口不能动

`scripts/start.ps1:301` 用 `Start-Process $AgentPy -ArgumentList 'main.py'`，`deploy/systemd/tagent-basic-agent.service` 用 `ExecStart=.../python main.py`，工作目录都是 `basic-agent/`。

`main.py` 必须留在 `basic-agent/` 根目录。如果哪个阶段想把它挪进 `app/`，就得同步改这两个文件 —— 不值得，别挪。

### 6.4 调参注释是资产，不是噪音

`rag_utils.py:55-78` 的注释记录了压测结论，其中这段尤其重要：

> 别再想着"精简 prompt 提速"——A/B 压测（各 3 轮）结果是反的：
> 填空 55.3s → 87.0s，选择 31.8s → 69.4s，解答 18.2s → 33.8s

`generate_exam` 的 docstring（`rag_utils.py:448-460`）也记了串行 193.7s → 并行 68.4s 的对比数据。

搬到 `app/config.py` 时**整段带走**。这类结论重新测一遍要几小时。

### 6.5 `stream_answer` 是生成器，跨层要小心

`openai_routes.py` 的 SSE 流式响应用 `stream_with_context` 包住 service 的生成器（`rag_utils.py:297-313`）。生成器跨越 service 边界时，Flask 的 request context 必须还活着。阶段 2 下沉这段逻辑时，`stream_with_context` 要留在 controller 层，service 只返回裸生成器。

### 6.6 Flask 版本

`pyproject.toml` 锁的是 `flask==2.3.3`。`app.json.ensure_ascii`（`app_factory.py:29`）是 2.2+ 的 API，重构后仍可用，但如果顺手升 Flask 要单独验证 —— 别和这次重构混在一个 PR 里。

---

## 7. 哪些 Spring Boot 习惯不要照搬

| Spring Boot 做法 | 在这里 | 原因 |
|---|---|---|
| `XxxService` 接口 + `XxxServiceImpl` | **不做** | Python 有 duck typing，只有一个实现时接口是纯噪音 |
| 引入 DI 框架（`dependency-injector` 等） | **不做** | `app/container.py` 里一个工厂函数就够，3 个 service 不值得上框架 |
| `@Transactional` / Entity-Repository ORM | **不做** | 这里的"仓储"是 JSON 文件和内存 dict，没有事务概念 |
| 每层一个独立 package + 严格单向依赖 | **做** | 这条是这次重构的核心价值 |
| `@ControllerAdvice` 集中异常处理 | **做** | Flask 的 `errorhandler` 就是同一个东西，只是要从启动类里挪出来 |
| `application.yml` 配置外置 | **做** | 对应 `app/config.py` + `.env`，现在 getenv 散在 5 个模块 |
| DTO 与 Entity 分离 | **已经有** | `exam_schema.py` 里 `PrivateExam` / `PublicExam` / `Draft*` 三套模型，比多数 Java 项目做得干净 |

---

## 8. 工作量与收益

| 阶段 | 预估 | 风险 | 可独立提交 |
|---|---|---|---|
| 0 建包 | 0.5h | 低 | 是 |
| 1 搬家 | 1h | 低 | 是 |
| 2 解 controller 互调 | 1.5h | 中 | 是 |
| 3 拆 God Service | 3h | **高** | 建议按 8 个子步骤分别提交 |
| 4 配置收口 | 1h | 低 | 是 |

**合计约 7 小时**，可以分 5 次做完，每次结束代码都是可运行、测试全绿的状态。

如果时间有限，**阶段 0 + 1 + 2 就能拿到大部分收益**（包结构成立、controller 之间不再互相 import、异常归位），阶段 3 可以往后放。

---

## 9. 分层依赖规则

重构完成后，import 方向必须是单向的：

```
api  →  service  →  repository
 │        │            │
 │        ├──────→  infra
 │        ├──────→  prompts
 │        ↓            ↓
 └────→ schema  ←──────┘
          ↑
        errors · util   （任何层都可依赖，它们不依赖任何层）
```

三条硬规则：

1. **`service/` 里不出现 `flask`** —— 不 import `request`、`current_app`、`jsonify`。service 收普通参数，返回普通对象。
2. **`repository/` 不 import `service/`**，也不 import `infra/`。
3. **`api/` 不 import `repository/`** —— 要数据就经过 service。

阶段 4 结束后可以加一条 CI 检查：

```bash
grep -rn "^from flask\|^import flask" basic-agent/app/service/ && echo "违反规则 1" && exit 1
```
