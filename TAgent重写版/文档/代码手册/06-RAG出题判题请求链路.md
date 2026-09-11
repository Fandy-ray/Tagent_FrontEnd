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

## 闪卡

`ExamService.generate_flash_deck()` 只出能本地判定的题型：填空 + 选择。`sample_exam_context()` 拼好的材料按
`EXAM_CONTEXT_SEPARATOR` 切回独立片段，用 `deal_shards()` 轮流发牌成 3 份，三片**并发**
各出 3~4 张——每片拿到的材料互不相同，这是并发分片不撞考点的主要手段（整卷那边实测过
「把已考清单塞回 prompt」，结果是重复更多）。三片回来后 `dedupe_cards()` 按归一化答案与
挖空句去重，低于 `FLASH_DECK_MIN_CARDS` 判 502。

出卡 prompt 复用 `build_cloze_prompt(..., count_range=..., deck_mode=True)`，
整卷调用方不传关键字参数，输出与改造前逐字一致。

`to_public_deck()` 与整卷的 `to_public()` 相反，**故意下发答案**（`accept` /
`accept_normalized` / `explanation`）：翻卡就是给用户看答案，判定也在浏览器本地做，
为此多一次往返只会让「零等待」落空。闪卡是复习工具，没有分数完整性可言。这条取舍只在
闪卡这条路径上成立，`to_public()` 一个字都没改。卡组另存在 `flash_cache`（独立的
`ExamCache` 实例），不与试卷共用，免得 `deck_id` 走进 `review_exam` 造成类型混淆。

闪卡**没有判卷接口**：前端 `$lib/data/cloze.ts` 是 `_normalize_text_answer` /
`cloze_matches` 的 TS 版，参考答案那一侧直接用后端下发的 `accept_normalized`，
只归一用户输入。两边的用例表在 `tests/test_flash_schema.py::NORMALIZE_CASES`。

## 整卷测评

`exam_schema.py` 定义公开卷、答案卷和评审结构；`exam_routes.py` 装配出卷/判卷接口；`exam_store.py` 用线程安全的 TTL/LRU 缓存保存试卷及锁定的 `served_model_id`。出卷规则为 4-6 道填空、3-4 道选择、1-2 道大题，总分归一为 100。

公开响应递归去除答案和 provider 信息。判卷时客观题本地比较，主观题由生成该卷的同一模型批量评审；请求模型不一致返回 422，模型失效返回 410。
