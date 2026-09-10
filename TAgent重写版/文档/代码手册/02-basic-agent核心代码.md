# basic-agent 核心代码

## 应用装配

`app_factory.py` 的 `create_app()` 创建 Flask 应用、装入注册表与 agent service，并注册 health、OpenAI、业务、管理和内部 Blueprint。测试可注入 fake registry/service，避免真实网络依赖。

`main.py` 只负责 `load_dotenv()`、调用 `create_app()`，再按环境变量使用 Waitress 或 Flask 启动。

## 路由模块

- `health_routes.py`：健康检查。
- `openai_routes.py`：`/v1/models` 与 `/v1/chat/completions`。
- `agent_routes.py`：RAG、出题、判题。
- `admin_routes.py`：全局 provider 管理，校验 `X-Agent-Admin-Token`。
- `internal_routes.py`：私有 provider 临时 envelope，校验 `X-Agent-Internal-Token`。
- `route_utils.py`：消息限制、token 校验、provider 选择、统一错误响应。

## 模型客户端

`model_clients.py` 的 `ModelClientFactory` 使用 `served_model_id + updated_at` 作为缓存键。`auth_mode=none` 时通过 httpx request hook 删除 Authorization；localhost 请求不使用系统代理。

## 错误映射

`rag_utils._translate_upstream_error()` 将认证、限流、超时、连接、请求格式和输出解析错误映射为稳定 HTTP 状态与 code，不把上游 URL、headers 或堆栈返回浏览器。

