# TAgent 代码手册

本手册面向后续维护者，重点解释 TAgent 自有代码与 Open WebUI 扩展点，不逐行复述 Open WebUI 上游约 26 万行代码。

## 推荐阅读顺序

1. [01-项目架构与启动链路.md](01-项目架构与启动链路.md)
2. [03-模型注册表与动态路由.md](03-模型注册表与动态路由.md)
3. [04-WebUI后端与用户隔离.md](04-WebUI后端与用户隔离.md)
4. [05-前端配置与聊天切换.md](05-前端配置与聊天切换.md)
5. [06-RAG出题判题请求链路.md](06-RAG出题判题请求链路.md)
6. [02-basic-agent核心代码.md](02-basic-agent核心代码.md)
7. [07-测试调试与二次开发.md](07-测试调试与二次开发.md)
8. [08-核心文件阅读索引.md](08-核心文件阅读索引.md)

## 先记住三条边界

1. 浏览器只访问 WebUI，不直接持有 basic-agent 管理 token 或私有 provider Key。
2. 全局 provider 在 basic-agent JSON；用户私有 provider 在 WebUI 数据库。
3. `model` 是整个系统的路由键：全局使用 `served_model_id`，私有使用 `tagent-user:<uuid>`。

