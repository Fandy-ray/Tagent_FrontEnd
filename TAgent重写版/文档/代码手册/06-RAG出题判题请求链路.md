# RAG、出题、判题请求链路

## RAG

1. 浏览器提交 `model + user_question`。
2. WebUI 根据模型前缀选择全局代理或私有内部代理。
3. basic-agent 校验请求与 provider。
4. `LangChainRAGSimulator` 线程安全初始化知识分块、Embedding 与 FAISS。
5. 检索四个相似片段，拼成 reference。
6. 选中 provider 的 ChatOpenAI 客户端生成答案。

## 出题

`generate_quiz()` 随机选择知识片段，要求上游只返回 JSON。`JsonOutputParser + QuizQuestion` 校验标题和问题长度，因此普通 OpenAI Chat Completions 服务即可使用，不要求 tool calling。

## 判题

`review_quiz()` 先按题目检索参考上下文，再要求上游返回 `is_correct`、`score`、`comment`、`correct_answer`。`QuizReview` 限制评分范围 0-100。

## 流式聊天

`stream_answer()` 在检索完成后调用 LangChain `stream()`；`openai_routes.py` 将每个真实 token 封装为 OpenAI SSE chunk，最后发送 stop chunk 与 `[DONE]`。

## 整卷测评

`exam_schema.py` 定义公开卷、答案卷和评审结构；`exam_routes.py` 装配出卷/判卷接口；`exam_store.py` 用线程安全的 TTL/LRU 缓存保存试卷及锁定的 `served_model_id`。出卷规则为 4-6 道填空、3-4 道选择、1-2 道大题，总分归一为 100。

公开响应递归去除答案和 provider 信息。判卷时客观题本地比较，主观题由生成该卷的同一模型批量评审；请求模型不一致返回 422，模型失效返回 410。
