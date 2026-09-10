# TAgent basic-agent

`basic-agent` 是 TAgent v1 的 Flask 智能体服务，提供 OpenAI-compatible 聊天、RAG、单题测评和整卷测评。服务端不固定 DeepSeek，也不从启动脚本读取某个固定模型；每次请求都按 `model` 解析全局 provider 或 WebUI 传入的私有 provider envelope。

## 推荐启动

不要单独复制虚拟环境或手工维护依赖。请在 v1 根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init_windows.ps1
.\start_all.bat
```

Linux 使用：

```bash
bash scripts/init_linux.sh
bash scripts/start_linux.sh --mode local
```

依赖由 `pyproject.toml` 与 `uv.lock` 固定。模型名、Base URL 和第三方 API Key 不写入 `.env.runtime`，应在 WebUI 的管理员模型页或个人 Connections 页面中配置。

## 模型来源

- 全局模型：保存在本机 `config/model_providers.json`，由管理员接口管理；文件被 Git 忽略。
- 私有模型：由 Open WebUI 加密保存在其数据库中，经 localhost 内部 token 发送临时 provider envelope；basic-agent 不落盘私有 Key。
- `GET /v1/models`：只返回已启用的全局 `served_model_id`，默认模型排在首位。
- 请求中的 `model`：必须对应可用的全局模型；内部私有接口则使用经过认证的临时 provider。

## 主要接口

```text
GET  /health
GET  /v1/models
POST /v1/chat/completions
POST /rag/query
POST /quiz/generate
POST /quiz/review
POST /quiz/exam/generate
POST /quiz/exam/review
```

管理员接口位于 `/admin/model-providers`，要求 `X-Agent-Admin-Token`。私有模型使用的聊天、RAG、单题和整卷接口位于 `/internal/*`，要求独立内部 token。未配置相应 token 时接口返回 `503`，不会以无鉴权模式开放。

整卷生成后，服务端缓存只保存模型 ID、题目、答案和评分规则，不保存 Key、Base URL 或 provider。判卷必须使用出卷时锁定的同一模型；模型不一致返回 `422`，缓存过期或模型失效返回 `410`。

## 独立开发

初始化完成后，可以只启动 basic-agent：

```powershell
cd basic-agent
$env:BASIC_AGENT_HOST = '127.0.0.1'
$env:BASIC_AGENT_PORT = '5000'
.\.venv\Scripts\python.exe main.py
```

此时仍需先通过管理员接口写入至少一个全局 provider。不要把真实 Key 写入源码、Markdown、命令历史或可提交的配置文件。

## 测试

```powershell
cd basic-agent
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q
```

完整发布校验应从 v1 根目录运行：

```powershell
.\scripts\verify_release.ps1 -Full
```

接口契约、错误码和调试步骤见根目录 `.docs/V1_ACCEPTANCE.md`、`.docs/MODEL_AND_EXAM_LOCKING.md` 与 `日志/测试方法.md`。
