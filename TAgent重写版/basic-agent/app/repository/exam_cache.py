"""试卷内存缓存与并发闸门。

纯标准库实现，不依赖 LLM/langchain，可离线单测。
适用场景：单进程 waitress 多线程（threads=8）；多进程部署需换共享存储（列为延后项）。
"""

from __future__ import annotations

import copy
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

from app.errors.exam_errors import ExamBusyError, ExamGoneError


@dataclass(frozen=True)
class StoredExam:
    """缓存中的私有试卷及其锁定模型；不保存 provider 凭据。"""

    exam: Any
    served_model_id: str


# ====================== 内存缓存 ======================
class ExamCache:
    """monotonic TTL + 容量上限；锁只包围缓存操作，读取在锁内深拷贝后立即释放。"""

    def __init__(
        self,
        ttl_seconds: float = 7200.0,
        max_items: int = 200,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._ttl = ttl_seconds
        self._max_items = max_items
        self._clock = clock
        self._lock = threading.Lock()
        # exam_id -> (过期时刻, 试卷对象)；dict 保持插入序，最旧在前
        self._items: Dict[str, Tuple[float, Any]] = {}

    def _cleanup_locked(self) -> None:
        now = self._clock()
        expired = [k for k, (deadline, _) in self._items.items() if deadline <= now]
        for k in expired:
            del self._items[k]

    def put(self, exam_id: str, exam: Any) -> None:
        with self._lock:
            self._cleanup_locked()
            while len(self._items) >= self._max_items:
                oldest = next(iter(self._items))
                del self._items[oldest]
            self._items[exam_id] = (self._clock() + self._ttl, exam)

    def get_copy(self, exam_id: str) -> Any:
        """返回深拷贝；不存在/过期抛 ExamGoneError。拷贝在锁内完成，判分在锁外进行。"""
        with self._lock:
            self._cleanup_locked()
            entry = self._items.get(exam_id)
            if entry is None:
                raise ExamGoneError("试卷不存在或已过期，请重新生成")
            return copy.deepcopy(entry[1])

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


# ====================== 并发闸门 ======================
class LLMGate:
    """全局信号量：覆盖所有 exam LLM 调用（生成+判分），满则立刻 429，不排队。"""

    def __init__(self, max_concurrent: int = 2):
        self._sem = threading.BoundedSemaphore(max_concurrent)

    @contextmanager
    def acquire(self):
        if not self._sem.acquire(blocking=False):
            raise ExamBusyError("出题/判分请求过多，请稍后再试")
        try:
            yield
        finally:
            self._sem.release()
