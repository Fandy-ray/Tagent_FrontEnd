"""单题测评（quiz）的数据结构。

与整卷（app/schema/exam.py）分开：单题是旧的轻量接口，字段与整卷没有交集。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QuizQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=10_000)

class QuizReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_correct: bool
    score: int = Field(ge=0, le=100)
    comment: str = Field(min_length=1, max_length=10_000)
    correct_answer: str = Field(max_length=10_000)

class QuizResult(QuizQuestion):
    reference_context: str = Field(max_length=100_000)
    reference_display: str = Field(max_length=100_000)

class QuizReviewResult(QuizReview):
    reference_context: str = Field(max_length=100_000)
    reference_display: str = Field(max_length=100_000)
