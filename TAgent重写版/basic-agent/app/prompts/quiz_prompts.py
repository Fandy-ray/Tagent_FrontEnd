"""单题出题与判分的 prompt 组装。"""

from __future__ import annotations


def quiz_generation_messages(context: str, parser) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You create exactly one short Chinese knowledge quiz from the supplied reference. "
                "The question must be a single question, not a numbered list and not multiple subquestions. "
                "Keep formulas in LaTeX delimiters such as $...$ or $$...$$. "
                "Return JSON only and do not use tool calls.\n"
                + parser.get_format_instructions()
            ),
        },
        {"role": "user", "content": f"Reference:\n{context}"},
    ]


def quiz_review_messages(context: str, question: str, user_answer: str, parser) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Grade the answer strictly from the reference. Return JSON only and do not use tool calls.\n"
                + parser.get_format_instructions()
            ),
        },
        {
            "role": "user",
            "content": f"Reference:\n{context}\n\nQuestion:\n{question}\n\nStudent answer:\n{user_answer}",
        },
    ]
