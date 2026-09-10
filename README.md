# TAgent 交接包

面向「系统建模与仿真」课程的教学智能体：**课程答疑（RAG 流式问答）+ 知识笔记本 + 智能测评（出卷判卷）**。

浏览器只访问前端 `5173`。交接包**不含任何 API Key**，模型要用自己的 Key 登记。

## 三个服务

| 服务 | 地址 | 怎么起 | 作用 |
|---|---|---|---|
| **OpenNotebook** | 页面 `8502` / 接口 `5055` | 启动脚本（Docker） | 笔记本：管理笔记与来源 |
| **basic-agent** | `127.0.0.1:5001` | 启动脚本 | 检索、答疑、出卷、判卷 |
| **tagentnote** | `127.0.0.1:5173` | 启动脚本 | 前端，浏览器开这个 |

启动脚本按系统选：**Windows 双击 `start.bat`，macOS 双击 `start.command`**
（Linux 跑 `TAgent重写版/scripts/start.sh`，与 macOS 是同一个脚本）。三个服务都由它一起拉起。
OpenNotebook 起不来时脚本会说明原因并继续启动另外两个 —— 此时答疑只用本地教材 `book1.md`。

> **8502 是页面，5055 才是接口。** basic-agent 打的是 `/api/*`，只有 5055 认。
> 填成 8502 不会报错，只会让笔记本里的内容一条都检索不到、答疑静悄悄退回本地教材。
> 填了浏览器地址也没关系，脚本会自动换算成 5055。

## 快速开始

### 1. 装好 Docker Desktop 并确认它能启动

OpenNotebook 跑在 Docker 里（`opennotebook/docker-compose.yml`）。<https://www.docker.com/products/docker-desktop/>

> **Docker Desktop 报「未检测到虚拟化支持」？** 多数情况 BIOS 是好的，缺的是 Windows 组件。
> 以**管理员**身份运行 `wsl --install --no-distribution`，然后**重启电脑**。
> 自查：`wsl --status`，若报 `WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED` 就是这个原因。

国内建议先配镜像加速（镜像有 GB 级）：Docker Desktop → Settings → Docker Engine，
在 JSON 里加一行 `registry-mirrors`，见 `opennotebook/readme.md` 第三步。

### 2. 双击 `start.bat`（macOS 双击 `start.command`）

首次运行会自动装 Python 与 Node 依赖、生成本机密钥，需要几分钟。脚本是**幂等**的，重复执行会跳过已完成的步骤。

它会依次完成：检查环境与端口 → **起 OpenNotebook 容器并等接口就绪** → `uv sync` → 准备 `.env.runtime` → 准备前端依赖与 `.env` → 起 basic-agent → **自动校验知识来源** → 起前端。

看到这一段就说明笔记本接通了：

```text
==> 检查知识来源
    source = composite
    notebook_reachable = true（http://localhost:5055）
```

停止：双击 `stop.bat` / `stop.command`。

> **macOS 第一次跑要先给执行权限。** 从 Windows 打包的 zip 解压后 `.command` 常会丢掉可执行位，
> 表现是双击没反应。在交接包目录开一个「终端」，跑一次即可：
>
> ```bash
> chmod +x start.command stop.command
> ```
>
> 若弹「无法打开，因为它来自身份不明的开发者」：右键该文件 → 打开 → 打开。
> 也可以完全不用双击，直接在终端里跑 `./start.command` 或 `bash TAgent重写版/scripts/start.sh`。

**常用参数**（在 PowerShell / 终端里传，双击不需要）：

| Windows | macOS / Linux | 说明 |
|---|---|---|
| `-Lan` | `--lan` | 前端监听 `0.0.0.0`，供局域网访问。明文 HTTP，仅适合短期演示 |
| `-SkipInstall` | `--skip-install` | 跳过 `uv sync` 与 `npm install`，省几十秒 |
| `-SkipNotebook` | `--skip-notebook` | 不启动 OpenNotebook（自己用别的方式起好了） |
| `-WithTts` | `--with-tts` | 连 `aliyun-tts-bridge` 一起起（做播客用，需要阿里云 DashScope Key） |
| `-PypiMirror <URL>` | `--pypi-mirror <URL>` | 装 Python 依赖失败时改用哪个 PyPI 镜像重试，默认阿里云 |
| `-AgentTimeout <秒>` | `--agent-timeout <秒>` | 等 basic-agent 就绪的超时，默认 300 |
| `-NotebookTimeout <秒>` | `--notebook-timeout <秒>` | 等 OpenNotebook 接口就绪的超时，默认 180 |
| — | `--no-open` | 启动完成后不自动打开浏览器（macOS/Linux 默认会开） |

`.command` 也认 PowerShell 那套写法（`-Lan`、`-SkipInstall`…），照着上面抄哪一列都行。

`stop.bat` / `stop.command` 会连 OpenNotebook 容器一起停（`docker compose stop`，笔记数据保留）。
只想停前后端、容器继续跑：`stop.bat -KeepNotebook` / `./stop.command --keep-notebook`。

### 3. 登记模型（必做）

**用自己的 DeepSeek Key，不要用别人的。** 没登记的话前端顶栏是「选择模型」，答疑和出题都会失败。

管理 token 在 `TAgent重写版/.env.runtime` 的 `AGENT_ADMIN_TOKEN`（启动脚本自动生成）。

macOS / Linux（在交接包根目录跑）：

```bash
TOKEN=$(grep '^AGENT_ADMIN_TOKEN=' TAgent重写版/.env.runtime | cut -d= -f2-)
curl -X POST http://127.0.0.1:5001/admin/model-providers \
  -H "X-Agent-Admin-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"DeepSeek","served_model_id":"deepseek",
       "base_url":"https://api.deepseek.com","upstream_model":"deepseek-chat",
       "auth_mode":"bearer","api_key":"你自己的-sk-xxx","temperature":0.1}'
```

Windows：

```powershell
$token = (Get-Content 'TAgent重写版\.env.runtime' | Where-Object { $_ -match '^AGENT_ADMIN_TOKEN=' }) -replace '^AGENT_ADMIN_TOKEN=',''
$body = @{
  name = 'DeepSeek'; served_model_id = 'deepseek'
  base_url = 'https://api.deepseek.com'; upstream_model = 'deepseek-chat'
  auth_mode = 'bearer'; api_key = '你自己的-sk-xxx'; temperature = 0.1
} | ConvertTo-Json

Invoke-RestMethod -Uri 'http://127.0.0.1:5001/admin/model-providers' -Method Post `
  -Headers @{ 'X-Agent-Admin-Token' = $token } -ContentType 'application/json' -Body $body
```

只要支持标准 Chat Completions 协议（通义千问、OpenAI、vLLM、LM Studio…），都按同样方式登记，不用改代码。

> ⚠️ **Key 是明文存在 `basic-agent/config/model_providers.json` 里的。** 接口返回时会掩码（`****xxxx`），但磁盘上没有加密——当前 basic-agent 代码里没有任何加解密逻辑（`AGENT_PROVIDER_ENCRYPTION_KEY` 是 open-webui 时期留下的，现在没人读）。这个文件已在 `.gitignore` 中，**不要提交、不要连同项目目录打包外传**。

登记完刷新 <http://localhost:5173> 即可。

### 4. 让 OpenNotebook 复用同一个 Key（可选，推荐）

登记过一次之后，OpenNotebook 不用再单独填 DeepSeek Key —— 让它走 basic-agent 的**透传通道**即可。

在 <http://localhost:8502> 里 **Models → Add Configuration → OpenAI Compatible**，填：

| 字段 | 值 |
|---|---|
| Base URL | `http://host.docker.internal:5001/v1/raw` |
| Model | `deepseek`（你注册时的 `served_model_id`） |
| API Key | 随便填，比如 `local`（这条通道不校验，真 Key 在 basic-agent 那边） |

然后 **Sync Models**，把 `deepseek` 指派为 Chat Model。

> **一定要填 `/v1/raw`，不能填 `/v1`。**
> `/v1/chat/completions` 是 TAgent 自己的 RAG 答疑通道，每次调用都会把 `book1.md`
> 和笔记本内容注入 prompt。OpenNotebook 拿它做摘要、来源转换、播客脚本时，
> 会被塞进一堆无关的系统仿真教材，输出直接跑偏。
> `/v1/raw/chat/completions` 什么都不加，原样转发给上游。

#### Embedding（可选，装了检索更准）

basic-agent 没有 `/v1/embeddings`，DeepSeek 官方也不提供 embeddings API，
所以这块没法走上面的透传通道，只能在 OpenNotebook 里单独配。

**但不配也能跑。** TAgent 检索时先试向量检索，失败就退回全文检索：

```python
try:    body["type"] = "vector"   # 没配 embedding 时 OpenNotebook 返回 400
except: body["type"] = "text"     # 自动退回，仍能检索到内容
```

实测确认过这条兜底有效（`vector` → HTTP 400，`text` → HTTP 200）。所以：

| | 不配 embedding | 配了 embedding |
|---|---|---|
| 能不能用 | 能 | 能 |
| 检索方式 | 关键词匹配 | 语义相似 |
| 代价 | 0 | 装 Ollama，约 1.5 GB + 模型 670 MB |

想配的话，两条路选一条：

**A. Ollama（本地、免费、离线）** —— OpenNotebook readme 推荐的做法。
先去 <https://ollama.com/download> 装好（装完它会自己在后台跑服务，不用手动 `ollama serve`），
再新开一个终端拉模型：

```bash
ollama pull mxbai-embed-large
```

然后在 OpenNotebook 里 Models → Add Configuration → Ollama，
Base URL 填 `http://host.docker.internal:11434`
（**不是** `localhost:11434` —— 容器里的 localhost 是容器自己）。

**B. 阿里云百炼（不用装东西）** —— 它的 `text-embedding-v3` 走 OpenAI 兼容接口。
在 OpenNotebook 里选 OpenAI Compatible，Base URL 填
`https://dashscope.aliyuncs.com/compatible-mode/v1`，Model 填 `text-embedding-v3`，
API Key 填你的 DashScope Key。如果你本来就要配播客 TTS，这条更省事。


## 功能

- **答疑** `/qa` — 流式输出，可中途停止与重新生成；右上角选笔记本，**选哪一本就只检索哪一本**，不选则本地教材与全部笔记一起检索；回答可一键「加入笔记本」写回 OpenNotebook。
- **笔记本** `/notebook` — iframe 嵌入 OpenNotebook，带连接检测与失败提示。
- **测评** `/exam` — 按选中的笔记本/来源出卷（填空 + 选择 + 大题），提交后判分并给逐题解析。

会话历史只存在于当前页面停留期间，刷新即清空——后端还没有会话存储接口。

## 环境要求

- Python 3.12（`uv` 会自动装，无需预装）
- Node.js ≥ 18（推荐 22 LTS）、npm
- uv：Windows `python -m pip install uv`；macOS `brew install uv`
  （没有 Homebrew 就 `curl -LsSf https://astral.sh/uv/install.sh | sh`，装完新开一个终端）
- Docker Desktop（macOS 上 Apple 芯片选 Apple Silicon 版；OrbStack / colima 也行）
- 首次初始化约 2 GiB 可用空间

依赖由 `basic-agent/uv.lock` 与 `tagentnote/package-lock.json` 固定。**不要复制别人电脑的 `.venv` 或 `node_modules`**，新机器必须按锁文件重装。

### 国内网络：PyPI 镜像有个坑

`uv.lock` 里每个包都写死了 `https://files.pythonhosted.org/...` 的下载地址，而
**`uv sync --frozen` 只认这些地址，镜像设置一概不生效**（`UV_DEFAULT_INDEX`、
`UV_INDEX_URL`、`-i` 全被忽略，见 [astral-sh/uv#19625](https://github.com/astral-sh/uv/issues/19625)）。
所以"先 export 镜像再 `uv sync --frozen`"是没用的，表现就是卡两分钟后
`operation timed out`。

管用的办法是**去掉 `--frozen`** 让 uv 照镜像重新解析一次——包版本仍由
`pyproject.toml` 里的 `==` 钉死，变的只是 `uv.lock` 里记录的下载地址：

```bash
cd TAgent重写版/basic-agent
UV_DEFAULT_INDEX="https://mirrors.aliyun.com/pypi/simple/" uv sync
```

**两边的启动脚本都已经自动处理**（`start.sh` 与 `start.ps1` 同一套逻辑）：
官方源失败时自动改用镜像重解析，并把原 `uv.lock` 备份成 `uv.lock.bak`；
若你已经设了 `UV_DEFAULT_INDEX` / `UV_INDEX_URL`，它会直接走镜像，不再白等官方源。
换镜像：`--pypi-mirror <URL>`（macOS/Linux）、`-PypiMirror <URL>`（Windows）。

npm 那边两个脚本默认都走 npmmirror，失败再退回官方源；手动装的话：

```bash
npm config set registry https://registry.npmmirror.com
```

## 目录结构

```text
TAgent交接版/
  start.bat / stop.bat      Windows 双击入口（放在本层或 TAgent重写版 里都能用）
  start.command / stop.command  macOS 双击入口（同上；首次可能要 chmod +x）
  怎么跑.txt                最简启动备忘
  README.md                 本文件
  TAgent重写版/             后端
    basic-agent/            Flask 服务：RAG、模型注册表、出卷判卷
      app/rag/              knowledge_base(本地教材) / opennotebook_kb / composite_kb
      app/api/openai_compat.py       /v1  答疑通道（走 RAG）
      app/api/openai_passthrough.py  /v1/raw  透传通道（不走 RAG，给 OpenNotebook 用）
      config/               model_providers.json（含 Key，禁止提交）
    scripts/                start.ps1 / stop.ps1（Windows），start.sh / stop.sh（macOS/Linux）
    docs/ 文档/             重构报告、代码手册、项目汇报
    .env.runtime            本机密钥，自动生成，禁止提交
  deploy/                   装成开机自启服务（见 deploy/README.md）
    linux/                  systemd 单元 + install.sh / uninstall.sh
    macos/                  launchd plist + install.sh / uninstall.sh
    windows/                任务计划程序 install.ps1 / uninstall.ps1 / watchdog.ps1
  opennotebook/             OpenNotebook 的 Docker Compose 部署（见 VENDOR.md）
    docker-compose.yml      surrealdb + open_notebook(+ 可选 tts bridge)
    notebook_data/          **你的笔记实际存在这里**，首次启动时创建
    surreal_data/           数据库文件，同上
  tagentnote/               前端（SvelteKit + Vite）
    src/lib/apis/           agent.ts(打 basic-agent) / opennotebook.ts(打 5055)
    .env                    从 .env.example 自动生成
```

## 手动启动

不想用脚本时（对应「怎么跑.txt」）：

```bash
# 后端
cd TAgent重写版/basic-agent
uv sync
uv run python main.py          # 读上一级的 .env.runtime

# 前端（另开一个终端）
cd tagentnote
npm install
npm run dev
```

前端必须跑 `npm run dev`，**不能用 `npm run build`**：`/agent-api` 代理只存在于 Vite dev server，生产构建里没有它，所有后端请求都会 404。

后端端口必须是 **5001**——`tagentnote/vite.config.ts` 的代理写死了 `http://127.0.0.1:5001`。改一边就得改另一边。

## 部署成常驻服务（开机自启）

上面那套是**手动跑**：关掉窗口或重启电脑就没了。要长期挂着（课程演示机、
实验室服务器），用 `deploy/` 下的安装脚本装成系统服务，开机自启、崩了自动拉回来：

| 系统 | 一条命令 | 用的机制 |
|---|---|---|
| Linux | `sudo deploy/linux/install.sh` | systemd |
| macOS | `deploy/macos/install.sh` | launchd LaunchAgent |
| Windows | `deploy\windows\install.ps1` | 任务计划程序 + 看门狗 |

装之前**先手动跑通一次**。各系统的详细步骤、运维命令和排查表见
[deploy/README.md](deploy/README.md)。卸载脚本只删服务定义，代码、依赖、密钥、
笔记数据一概不动。

## 验证

```bash
cd TAgent重写版/basic-agent
uv run pytest -q                    # 113 passed
```

```bash
cd tagentnote
npm run check                       # 0 errors
npm run build
```

服务起来后的自检：

- <http://localhost:5001/health> — basic-agent 活着
- <http://localhost:5001/knowledge> — 看 `source` 和 `notebook_reachable`
- <http://localhost:5001/v1/models> — 看模型登记成功没有

## 排查

| 现象 | 原因 |
|---|---|
| 前端顶栏是「选择模型」 | 还没登记模型，见上面第 3 步 |
| 页面请求全 502 | basic-agent 没起来，或端口不是 5001 |
| 答疑能答但笔记本内容检索不到 | `notebook_reachable` 是 false。8502 是页面，接口在 5055 |
| 笔记本明明起着，`notebook_reachable` 还是 false | 多半有个旧的 basic-agent 残留进程在占着 5001。`stop.bat` 后确认 5001 已释放再重启 |
| `/admin/model-providers` 返回 503 | `AGENT_ADMIN_TOKEN` 是空的。跑一次 `start.bat` 会自动补 |
| 提示端口被占 | 先 `stop.bat`；脚本不会去结束不认识的进程 |
| Docker 引擎不可用 | Docker Desktop 没启动，或 WSL2 组件没装（见上面第 1 步）|
| Docker Desktop 一直卡在 `Starting the Docker Engine...` | 先别管界面，开个终端跑 `docker ps`。能通就说明引擎其实是好的，只是面板没刷新，`start.bat` 照样能用 |
| 拉镜像超时 | 配 Docker 镜像加速，见 `opennotebook/readme.md` 第三步 |
| OpenNotebook 的摘要里混进了系统仿真教材 | Base URL 填成 `/v1` 了，要填 `/v1/raw`，见上面第 4 步 |
| OpenNotebook 建不了向量索引 | 没配 embedding。不影响使用（会退回全文检索），想要语义检索见第 4 步 |
| 证书相关报错 | 网络拦截了 `https://api.deepseek.com`，需要代理 |
| macOS 双击 `.command` 没反应 | 丢了可执行权限。`chmod +x start.command stop.command`；提示「身份不明的开发者」就右键 → 打开 |
| macOS 提示端口 `5001` 被 `ControlCenter` 占用 | 那是「隔空播放接收器」（它占 5000/7000，偶尔波及邻近端口）。系统设置 → 通用 → 隔空播放与接力，关掉它 |
| macOS 上 `zsh: command not found: uv` | uv 装在 `~/.local/bin` 但没进 PATH。新开一个终端，或 `export PATH="$HOME/.local/bin:$PATH"` |
| `uv sync` 报 `operation timed out` / `Failed to download` | `--frozen` 无视镜像，见上面「国内网络」一节。启动脚本会自动改走镜像重试，还不行就 `-PypiMirror` / `--pypi-mirror` 换一个 |
| 拉 Docker 镜像 `context deadline exceeded` | 配镜像加速（`opennotebook/readme.md` 第三步）。注意 `docker-compose.yml` 里 `pull_policy: always` 会每次重拉，实在拉不动就把那两行注释掉 |

运行日志在 `TAgent重写版/logs/runtime/`。

## 安全

以下内容**禁止提交**（已在 `.gitignore` 中）：

- `TAgent重写版/.env.runtime` — 管理 token、内部 token
- `TAgent重写版/basic-agent/config/model_providers.json` — **明文 API Key**
- `.venv`、`node_modules`、`.run/`、`logs/`

管理通道与内部通道用不同 token，都以 `hmac.compare_digest` 定长比较；token 未配置时返回 `503` 而不是放行。日志对 `api_key`、`token`、`secret`、`password` 递归脱敏。

API Key 在磁盘上**没有加密**（见上），所以 `model_providers.json` 要当成密码文件对待。

## 已知缺口

- 答疑回答没有逐条出处：后端只返回正文，前端只标注「本次检索范围」是哪个笔记本。
- 会话历史不落盘。
- API Key 明文落盘，没有加密（见「安全」一节）。
- `文档/` 与 `docs/` 里部分内容仍描述 open-webui 时期的架构。

## 许可证

见 `TAgent重写版/LICENSE`。
