"""RAG 对话的 prompt 组装。"""

from __future__ import annotations

from app.errors.api_errors import AgentAPIError


def build_prompt_messages(messages: list[dict[str, str]], context: str):
    system = {
        "role": "system",
        "content": (
            "You are a teaching assistant. Ground the answer in the reference below. "
            "Preserve useful Markdown, formulas, tables, and image links. If the reference is insufficient, say so.\n\n"
            f"Reference:\n{context}"
        ),
    }
    return [system, *messages]
def last_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message["content"]
    raise AgentAPIError("At least one user message is required.", 400, "invalid_messages")
