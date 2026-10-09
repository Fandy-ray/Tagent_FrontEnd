"""RAG 对话服务。

service 层规则：不 import flask，不认识 request/current_app。
收普通参数，返回普通对象；流式接口返回裸生成器，
由 api 层用 stream_with_context 包起来。
"""

from __future__ import annotations

from typing import Any, Callable

from app.errors.api_errors import AgentAPIError
from app.infra.upstream_errors import translate_upstream_error
from app.prompts.chat_prompts import build_prompt_messages, last_user_message
from app.rag.citations import citations_from_documents
from app.rag.graph import build_answer_graph
from app.schema.provider import ModelProvider
from app.util.text import content_text


# 上游没说「答完了」就断了流：多半是连接中途断开。不补这一句，前端会把半截回答
# 当成完整回答显示，还带着追问建议（压测 F3）。
STREAM_INTERRUPTED_NOTE = "\n\n（回答中断：和模型服务的连接断开了，可以点「重新生成」再试一次。）"
# 上游没给 finish_reason 就断了：内部用这个值标出来（学习记录里如实记「没答完」），
# 发给前端时 openai_view 会换回标准的 "stop"，OpenAI 兼容的客户端不认识自造的值
FINISH_INTERRUPTED = "interrupted"
# 流到一半服务端出错时发给前端的那一句（openai_view 用）
STREAM_FAILED_NOTE = "\n\n（回答中断：模型服务出错了，可以点「重新生成」再试一次。）"


def _retrieval_query(messages: list[dict[str, str]], retrieval_query: str | None) -> str:
    """检索词：有前端给的检索提示就用它，否则用最后一条用户消息。

    last_user_message 无论如何都要调——没有用户消息的请求照旧 400。
    """
    question = last_user_message(messages)
    return retrieval_query or question


class ChatService:
    def __init__(self, knowledge_base, client_factory):
        self.knowledge_base = knowledge_base
        self.client_factory = client_factory
        self.graph = build_answer_graph(knowledge_base, client_factory)

    def answer(
        self,
        messages: list[dict[str, str]],
        provider: ModelProvider,
        notebook_ids: list[str] | None = None,
        *,
        mode: str = "qa",
        retrieval_query: str | None = None,
    ) -> dict[str, Any]:
        query = _retrieval_query(messages, retrieval_query)
        try:
            result = self.graph.invoke(
                {
                    "messages": messages,
                    "provider": provider,
                    "query": query,
                    "notebook_ids": notebook_ids or [],
                    "mode": mode,
                    "step_log": [],
                }
            )
            return {
                "content": result["content"],
                "retrieved_context": result.get("retrieved_context", ""),
                "citations": citations_from_documents(result.get("retrieved_documents") or []),
                "step_log": result.get("step_log", []),
            }
        except AgentAPIError:
            raise
        except Exception as exc:
            raise translate_upstream_error(exc) from exc
    def stream_answer(
        self,
        messages: list[dict[str, str]],
        provider: ModelProvider,
        notebook_ids: list[str] | None = None,
        *,
        mode: str = "qa",
        retrieval_query: str | None = None,
        on_citations: Callable[[list[dict[str, Any]]], None] | None = None,
    ):
        """产出 (文字, 结束原因)。检索完、开始生成之前，用到的材料的出处交给 on_citations。

        出处不混进产出里：别处都按两元组读这个生成器。
        """
        query = _retrieval_query(messages, retrieval_query)
        try:
            context, documents = self.knowledge_base.retrieve(query, notebook_ids=notebook_ids)
            if on_citations is not None:
                on_citations(citations_from_documents(documents))
            prompt_messages = build_prompt_messages(messages, context, mode=mode)
            finish_reason = None
            for chunk in self.client_factory.get(provider).stream(prompt_messages):
                metadata = getattr(chunk, "response_metadata", None) or {}
                finish_reason = metadata.get("finish_reason", finish_reason)
                content = content_text(chunk.content)
                if content:
                    yield content, None
            if finish_reason is None:
                yield STREAM_INTERRUPTED_NOTE, None
                finish_reason = FINISH_INTERRUPTED
            yield "", finish_reason
        except AgentAPIError:
            raise
        except Exception as exc:
            raise translate_upstream_error(exc) from exc
