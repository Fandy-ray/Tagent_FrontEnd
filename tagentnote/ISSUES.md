# TAgentNote 集成问题清单

- 整理日期：2026-08-20
- 范围：本地克隆 `frontend` 分支、代码审阅、`npm install` / `npm run dev` 联调
- Gitee Issues：仓库当前为 **0 条**；本文件同步给 tagent 组联调
- 远程：https://gitee.com/kevin-zhengscuter/tagentnote/issues

## 本周前端已处理（演示交互版）

以下问题已在本仓库改完，部署后请再点一遍主路径确认：

| ID | 处理 |
|----|------|
| ISS-01 | 笔记本增加连接检测与失败提示 |
| ISS-02 | 答疑页接入 `agent.ts` Mock RAG；停止/重生成生效 |
| ISS-03 | 统一默认 URL，补 `.env.example` |
| ISS-04 / ISS-05 | 修正 README 安装步骤与国内镜像说明 |
| ISS-06 | 正式测评改为 `/exam`，copy 路由重定向 |
| ISS-07 / ISS-08 | 欢迎页改为演示表述，去掉 Google Fonts |
| ISS-09 | 修复 `$state`、`onclick`、建议列表 a11y、测评 modelId |
| ISS-10 / ISS-11 | favicon 与 `lang=zh-CN` |
| 播客 | 本前端已隐藏语音/朗读入口。OpenNoteBook 内播客仍需 tagent 组在对端 UI 关闭 |

部署后仍需和 tagent 组确认：OpenNoteBook 是否允许 iframe、端口是否 8502、对端播客入口是否已隐藏、`.doc` 来源上传失败（ISS-12）。

---

## P0 · 阻塞联调 / 核心能力缺口

### ISS-01 笔记本页依赖独立 OpenNoteBook，iframe 无失败降级

- 模块：笔记本 `/notebook`
- 现象：本仓库不包含 OpenNoteBook。笔记本页用 iframe 嵌入外部服务，默认 `http://localhost:8502/notebooks`。未启动后端时页面空白，无健康检查、无错误提示。
- 证据：
  - `src/routes/notebook/+page.svelte` 仅渲染 iframe
  - README 写明需另启 OpenNoteBook，教程：https://gitee.com/kevin-zhengscuter/fixed_open_notebook
- 建议：
  1. 在 README 增加「双进程启动」说明（前端 5173 + OpenNoteBook 8502）
  2. iframe `onerror` / 超时检测，展示「请先启动 OpenNoteBook」与配置指引
  3. 确认 OpenNoteBook 允许被本域 iframe 嵌入（`X-Frame-Options` / CSP `frame-ancestors`）

### ISS-02 答疑与测评仍是前端 Mock，未接入真实 Agent / RAG

- 模块：答疑 `/qa`、测评 `/exam-copy`
- 现象：欢迎页写「RAG 增强检索 · LangGraph 智能体」，实际问答由页面内 `createMockAnswer` 生成；测评走 `MockExamPanel`。`src/lib/apis/agent.ts` 里的 `queryAgentRag` / `getAgentModels` **没有任何页面引用**，存在两套互不连通的 Mock。
- 证据：
  - `src/routes/qa/+page.svelte`：`createMockAnswer`，文案写明「尚未调用真实模型 API」
  - `src/lib/apis/agent.ts`：仅被自身导出
  - `src/routes/exam-copy/+page.svelte`：只挂载 `MockExamPanel`
- 建议：页面统一走 `agent.ts`（或真实后端），删除重复 Mock；欢迎页文案与实现对齐，未接通前标明「演示模式」。

### ISS-03 OpenNoteBook 地址文档与代码不一致，且缺少 `.env.example`

- 模块：配置
- 现象：
  - README 示例：`PUBLIC_OPENNOTEBOOK_URL=http://localhost:8502`（无 `/notebooks`）
  - 代码默认：`http://localhost:8502/notebooks`
  - `.gitignore` 允许提交 `.env.example`，仓库中不存在该文件
- 证据：`README.md` 环境变量一节；`src/routes/notebook/+page.svelte` 第 6–7 行
- 建议：统一默认 URL；补 `.env.example`；README 写清带不带路径后缀。

---

## P1 · 开发体验 / 产品结构

### ISS-04 README 快速开始多写一层 `cd tagentnote`

- 模块：文档
- 现象：克隆后工作目录已是仓库根。按 README 再执行 `cd tagentnote` 会报 `no such file or directory`。`npm install` 仍会继续跑，但首次启动容易误判失败。
- 证据：本机终端；`README.md`「安装与运行」
- 建议：改为「确认当前目录含 `package.json` 后执行 `npm install`」。

### ISS-05 国内使用官方 npm 源时，install 会长时间卡在 audit

- 模块：开发环境
- 现象：`npm install` 依赖下完后，仍长时间转圈。日志出现 `This endpoint is being retired. Use the bulk advisory endpoint instead`。官方 `registry.npmjs.org` 的 audit 在国内很慢。
- 证据：本机首次安装约 2 分钟，audit 阶段明显停顿；`npm config get registry` 为官方源
- 建议：README 增加国内镜像与 `--no-audit` 示例：
  ```bash
  npm install --registry=https://registry.npmmirror.com --no-audit
  ```

### ISS-06 存在副本路由，正式测评路径命名为 `exam-copy`

- 模块：路由
- 现象：
  - `/qa` 与 `/qa-copy` 并存，逻辑高度重复
  - 测评入口指向 `/exam-copy`，没有 `/exam`
- 证据：`src/routes/qa/`、`src/routes/qa-copy/`、`src/routes/exam-copy/`；`agent-select/+page.svelte` 的 `goto('/exam-copy?...')`
- 建议：明确正式路由（建议 `/qa`、`/exam`），删除或归档 copy 页，避免演示走错入口。

### ISS-07 欢迎页能力宣传与当前实现不符

- 模块：欢迎页 `/welcome`
- 现象：副标题写「RAG 增强检索 · LangGraph 智能体 · 实时答疑与知识测评」。当前无 LangGraph、无真实 RAG 后端、答疑/测评为 Mock。
- 证据：`src/routes/welcome/+page.svelte` 第 72 行；智能体选择页已有「前端 Mock 演示模式」提示，欢迎页没有
- 建议：未接通后端前改为「演示 / Mock」表述，或与选择页提示保持一致。

### ISS-08 欢迎页依赖 Google Fonts，国内可能加载失败

- 模块：欢迎页
- 现象：`fonts.googleapis.com` / `fonts.gstatic.com` 在部分网络下超时或被拦截，标题字体回退、首屏变慢。
- 证据：`src/routes/welcome/+page.svelte` 的 `<svelte:head>` 外链
- 建议：字体本地化，或提供系统字体回退且不阻塞渲染。

### ISS-12 OpenNoteBook 上传旧版 Word `.doc` 失败

- 模块：OpenNoteBook 来源上传（笔记本知识库）
- 现象：在 OpenNoteBook 中上传 `实验报告.doc` 时提示「操作失败 / Unable to determine file type for: /app/data/uploads/实验报告.doc」。文件已写入容器路径，但无法识别类型，来源添加失败。
- 证据：本机 2026-08-20 联调；OpenNoteBook 官方说明支持 PDF / DOCX / PPTX / XLSX，不包含 Word 97–2003 的 `.doc`（OLE 二进制）。容器内按文件魔数判断类型，旧 `.doc` 无法映射到可处理的 parser。
- 影响：课程材料里大量实验报告仍是 `.doc`，知识库无法入库，答疑/测评引用链不上。
- 建议：
  1. **临时**：用 Word / WPS / Pages 另存为 `.docx` 或 PDF 后再上传；不要只改后缀。
  2. **文档**：在 OpenNoteBook / 教学平台上传说明中写明支持格式。
  3. **产品（tagent 组）**：若必须收 `.doc`，在上传前做格式转换（LibreOffice/`soffice --convert-to docx`），或扩展 OpenNoteBook 的文件类型检测与解析。

---

## P2 · 运行时质量

### ISS-09 Svelte 5 运行时警告（开发服务器已打出）

- 模块：前端质量
- 现象：`npm run dev` 后访问页面出现：
  1. `welcome/+page.svelte`：`on:click` 已弃用，应改 `onclick`
  2. `agent-select/+page.svelte`：`selectedModelId` 未用 `$state(...)`，更新不会触发 UI
  3. `MockSuggestions.svelte`：`<button>` 不能同时 `role="listitem"`
  4. `MockExamPanel.svelte`：`modelId` 只捕获了初始值（`state_referenced_locally`），路由里换模型可能不生效
- 证据：本机 Vite 日志，约 23:10–23:11
- 建议：按 Svelte 5 规范一次性修掉；`selectedModelId` 与 `modelId` 优先修，否则选模型是假交互。

### ISS-10 浏览器请求 `/favicon.ico` 返回 404

- 模块：静态资源
- 现象：存在 `src/lib/assets/favicon.svg`，但 `src/app.html` 未声明 favicon；浏览器默认请求 `/favicon.ico` 404。
- 证据：Vite 日志 `[404] GET /favicon.ico`
- 建议：将图标放到 `static/favicon.svg`（或 ico），并在 `app.html` 中 `<link rel="icon">`。

### ISS-11 根文档语言为英文

- 模块：无障碍 / SEO
- 现象：产品文案为中文，`src/app.html` 为 `lang="en"`。
- 建议：改为 `zh-CN`。

---

## 非问题（已排除）

| 日志 | 结论 |
|------|------|
| `[404] GET /json/version` | 浏览器/调试器探测 Chrome DevTools 端点，不是业务路由缺失 |
| `cd: no such file or directory: tagentnote` 之后 npm 仍在跑 | 见 ISS-04；不是 npm 本身损坏 |

---

## 建议同步到 Gitee 的标签

| Issue | 建议标签 |
|-------|----------|
| ISS-01 | `bug` `P0` `notebook` |
| ISS-02 | `enhancement` `P0` `agent` |
| ISS-03 | `bug` `P0` `docs` |
| ISS-04 | `docs` `P1` |
| ISS-05 | `docs` `P1` `dx` |
| ISS-06 | `enhancement` `P1` |
| ISS-07 | `docs` `P1` |
| ISS-08 | `enhancement` `P1` |
| ISS-09 | `bug` `P2` |
| ISS-10 | `bug` `P2` |
| ISS-11 | `bug` `P2` |
| ISS-12 | `bug` `P1` `notebook` |

创建 Gitee Issue 需要仓库协作者身份 + 私人令牌（`issues` 权限）。本地整理完成后，可用令牌批量创建，或按本文件逐条粘贴到 https://gitee.com/kevin-zhengscuter/tagentnote/issues/new。
