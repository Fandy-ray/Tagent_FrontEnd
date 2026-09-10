"""单题测评服务：出一道题、判一道题。

与整卷（ExamService）分开：单题是旧的轻量接口，没有试卷缓存、
没有并发闸门、没有模型锁定，超时后还会退化成一个兜底问题而不是报错。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any

from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser

from app.config import QUIZ_GENERATION_TIMEOUT_SECONDS
from app.infra.model_client_factory import ModelClientFactory
from app.infra.upstream_errors import is_timeout_error, translate_upstream_error
from app.prompts.quiz_prompts import quiz_generation_messages, quiz_review_messages
from app.rag.knowledge_base import (
    first_heading,
    join_quiz_context,
    join_quiz_display,
    select_quiz_documents,
)
from app.schema.provider import ModelProvider
from app.schema.quiz import QuizQuestion, QuizResult, QuizReview, QuizReviewResult
from app.util.markdown_sanitizer import clean_generated_markdown, clean_reference_for_display
from app.util.text import content_text


class QuizService:
    def __init__(self, knowledge_base, client_factory):
        self.knowledge_base = knowledge_base
        self.client_factory = client_factory

    def generate_quiz(
        self, provider: ModelProvider, notebook_ids: list[str] | None = None
    ) -> dict[str, str]:
        chunks = self.knowledge_base.chunks(notebook_ids=notebook_ids)
        selected = select_quiz_documents(chunks)
        context = join_quiz_context(selected)
        display_context = join_quiz_display(selected)
        parser = JsonOutputParser(pydantic_object=QuizQuestion)
        messages = quiz_generation_messages(context, parser)
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quiz-generation")
        future = executor.submit(_invoke_quiz_model, self.client_factory, provider, messages, parser)
        try:
            result = future.result(timeout=QUIZ_GENERATION_TIMEOUT_SECONDS)
            executor.shutdown(wait=False)
            question_data = result.model_dump()
            question_data["question"] = clean_generated_markdown(result.question)
            return QuizResult(
                **question_data,
                reference_context=context,
                reference_display=display_context,
            ).model_dump()
        except FutureTimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            return _fallback_quiz(selected, context, display_context)
        except Exception as exc:
            executor.shutdown(wait=False, cancel_futures=True)
            if is_timeout_error(exc):
                return _fallback_quiz(selected, context, display_context)
            raise translate_upstream_error(exc) from exc

    def review_quiz(
        self,
        question: str,
        user_answer: str,
        provider: ModelProvider,
        reference_context: str | None = None,
    ) -> dict[str, Any]:
        context = reference_context.strip() if isinstance(reference_context, str) and reference_context.strip() else ""
        if not context:
            context, _documents = self.knowledge_base.retrieve(question)
        parser = JsonOutputParser(pydantic_object=QuizReview)
        messages = quiz_review_messages(context, question, user_answer, parser)
        try:
            content = content_text(self.client_factory.get(provider).invoke(messages).content)
            result = QuizReview.model_validate(parser.parse(content))
            review_data = result.model_dump()
            review_data["comment"] = clean_generated_markdown(result.comment)
            review_data["correct_answer"] = clean_generated_markdown(result.correct_answer)
            return QuizReviewResult(
                **review_data,
                reference_context=context,
                reference_display=clean_reference_for_display(context),
            ).model_dump()
        except Exception as exc:
            raise translate_upstream_error(exc) from exc


def _invoke_quiz_model(
    client_factory: ModelClientFactory,
    provider: ModelProvider,
    messages: list[dict[str, str]],
    parser: JsonOutputParser,
) -> QuizQuestion:
    content = content_text(
        client_factory.get(
            provider,
            timeout_seconds=QUIZ_GENERATION_TIMEOUT_SECONDS,
            max_retries=0,
        ).invoke(messages).content
    )
    return QuizQuestion.model_validate(parser.parse(content))
def _fallback_quiz(
    documents: list[Document],
    context: str,
    display_context: str,
) -> dict[str, str]:
    heading = first_heading(documents)
    title = f"{heading}知识点测验" if heading else "知识点测验"
    topic = heading or "参考内容"
    question = f"根据参考内容，概括说明“{topic}”中的一个关键概念、步骤或结论。"
    return QuizResult(
        title=title[:200],
        question=question,
        reference_context=context,
        reference_display=display_context,
    ).model_dump()
