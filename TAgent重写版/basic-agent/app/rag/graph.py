"""RAG 的 LangGraph 状态图：检索 -> 生成。

图本身不持有业务状态，依赖由 build_answer_graph 闭包注入，
这样 ChatService 只需要拿到一个编译好的 graph。
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.prompts.chat_prompts import build_prompt_messages
from app.schema.provider import ModelProvider
from app.util.text import content_text


class RAGState(TypedDict, total=False):
    messages: list[dict[str, str]]
    provider: ModelProvider
    query: str
    notebook_ids: list[str]
    mode: str
    retrieved_context: str
    retrieved_documents: list[Any]
    content: str
    step_log: list[str]


def build_answer_graph(knowledge_base, client_factory):
    def retrieve_node(state: RAGState):
        context, documents = knowledge_base.retrieve(
            state["query"], notebook_ids=state.get("notebook_ids")
        )
        return {
            "retrieved_context": context,
            "retrieved_documents": documents,
            "step_log": [*state.get("step_log", []), f"Retrieved {len(documents)} knowledge chunks."],
        }

    def answer_node(state: RAGState):
        messages = build_prompt_messages(
            state["messages"], state["retrieved_context"], mode=state.get("mode", "qa")
        )
        response = client_factory.get(state["provider"]).invoke(messages)
        return {
            "content": content_text(response.content),
            "step_log": [*state.get("step_log", []), "Generated the answer."],
        }

    builder = StateGraph(RAGState)
    builder.add_node("retrieve_context", retrieve_node)
    builder.add_node("generate_answer", answer_node)
    builder.add_edge(START, "retrieve_context")
    builder.add_edge("retrieve_context", "generate_answer")
    builder.add_edge("generate_answer", END)
    return builder.compile()
