# WebUI 后端与用户隔离

## 数据模型

`models/agent_model_providers.py` 定义 `AgentModelProvider`、`AgentModelProviderDefault` 和服务层。唯一约束是 `(user_id, name)`；查询、编辑、删除始终同时携带 `provider_id + user_id`。

## 加密

`utils/agent_provider_security.py` 封装 Fernet 与 URL 策略。数据库只保存密文和末四位。`to_public()` 永远不返回完整 Key；`to_runtime()` 只在服务器请求内存中解密。

## API

- 用户：`/api/v1/agent/user-model-providers`
- 管理治理：`/api/v1/admin/agent-user-model-providers`
- 智能体同源代理：`/api/v1/agent/*`
- 主聊天：`/api/chat/completions`

用户路由要求 `get_verified_user`；管理员治理要求 `get_admin_user`。跨用户 provider 统一返回 404，避免暴露资源是否存在。

## 私有模型合并

`main.py:get_models()` 在全局模型过滤完成后，调用 `agent.private_models_for_user(user.id)` 追加当前用户的启用模型。私有记录不写入共享 `app.state.MODELS`。

## 内部调用

`routers/agent.py` 做所有权检查、运行前 URL 复核和 Key 解密，再用 `BASIC_AGENT_INTERNAL_TOKEN` 调用 basic-agent `/internal/*`。上游错误保留稳定 code，同时删除内部 URL、headers 与堆栈。

