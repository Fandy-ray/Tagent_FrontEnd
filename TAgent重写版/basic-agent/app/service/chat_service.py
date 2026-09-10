"""RAG 对话服务。

service 层规则：不 import flask，不认识 request/current_app。
收普通参数，返回普通对象；流式接口返回裸生成器，
由 api 层用 stream_with_context 包起来。
"""

from __future__ import annotations

from typing import Any

from app.errors.api_errors import AgentAPIError
from app.infra.upstream_errors import translate_upstream_error
from app.prompts.chat_prompts import build_prompt_messages, last_user_message
from app.rag.graph import build_answer_graph
from app.schema.provider import ModelProvider
from app.util.text import content_text


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
    ) -> dict[str, Any]:
        query = last_user_message(messages)
        try:
            result = self.graph.invoke(
                {
                    "messages": messages,
                    "provider": provider,
                    "query": query,
                    "notebook_ids": notebook_ids or [],
                    "step_log": [],
                }
            )
            return {
                "content": result["content"],
                "retrieved_context": result.get("retrieved_context", ""),
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
    ):
        query = last_user_message(messages)
        try:
            context, _documents = self.knowledge_base.retrieve(query, notebook_ids=notebook_ids)
            prompt_messages = build_prompt_messages(messages, context)
            finish_reason = None
            for chunk in self.client_factory.get(provider).stream(prompt_messages):
                metadata = getattr(chunk, "response_metadata", None) or {}
                finish_reason = metadata.get("finish_reason", finish_reason)
                content = content_text(chunk.content)
                if content:
                    yield content, None
            yield "", finish_reason or "stop"
        except AgentAPIError:
            raise
        except Exception as exc:
            raise translate_upstream_error(exc) from exc
