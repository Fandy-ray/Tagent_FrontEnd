"""把同一时刻、同一内容的请求合并成一次调用（single-flight），并可短时重放结果。

为什么要有它：学生连点、刷新后重交、开两个标签页，都会把一模一样的请求再发一遍。
被刷掉的那次在服务端照样跑完（waitress 感知不到客户端已经走了），还占着 LLMGate
的名额，于是重交的那次先吃一个 429，之后要么干等、要么再花一份钱。
压测实测（S3）：批改中刷新 5 次再重交，上游被调 12 次（正常一次批改是 4 次），
重交还要重试两轮才成功。

合并之后：
- 同样的请求**正在跑** → 等它的结果，不进闸门、不占名额、不多花一次模型调用；
- 同样的请求**刚跑完**（replay_seconds 之内）→ 直接给那份结果。刷新后点「重新批改」
  拿到的就是刚才那次，不会一刷新分数就变。

只存在内存里：key 是请求内容的哈希，到期即删，进程重启就没了，不落盘。
失败的结果不重放——下一次请求应该真的再试一次。
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def fingerprint(*parts: Any) -> str:
    """请求内容的指纹。只存哈希，不把学生原文当 key 留在内存里。"""
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class _Call:
    __slots__ = ("done", "result", "error", "finished_at", "replay_seconds")

    def __init__(self, replay_seconds: float):
        self.done = threading.Event()
        self.result: Any = None
        self.error: BaseException | None = None
        self.finished_at = 0.0
        self.replay_seconds = replay_seconds


class SingleFlight:
    def __init__(self, *, max_entries: int = 256, clock: Callable[[], float] = time.monotonic):
        self._lock = threading.Lock()
        self._calls: dict[str, _Call] = {}
        self._max_entries = max_entries
        self._clock = clock

    def do(self, key: str, fn: Callable[[], T], *, replay_seconds: float = 0.0) -> T:
        with self._lock:
            call = self._calls.get(key)
            if call is not None and call.done.is_set():
                if self._clock() - call.finished_at <= call.replay_seconds:
                    return call.result
                del self._calls[key]
                call = None

            leader = call is None
            if leader:
                self._make_room_locked()
                call = _Call(replay_seconds)
                self._calls[key] = call

        if not leader:
            # 领头的那次自带预算（call_json_llm 保证 ≤ budget），这里不会无限等
            call.done.wait()
            if call.error is not None:
                raise call.error
            return call.result

        try:
            call.result = fn()
            return call.result
        except BaseException as exc:
            call.error = exc
            raise
        finally:
            call.finished_at = self._clock()
            if call.error is not None or call.replay_seconds <= 0:
                with self._lock:
                    if self._calls.get(key) is call:
                        del self._calls[key]
            call.done.set()

    def _make_room_locked(self) -> None:
        """先清过期的，还满就丢最早完成的；正在跑的永远不丢（有人在等它）。"""
        if len(self._calls) < self._max_entries:
            return
        now = self._clock()
        for key, call in list(self._calls.items()):
            if call.done.is_set() and now - call.finished_at > call.replay_seconds:
                del self._calls[key]
        if len(self._calls) < self._max_entries:
            return
        finished = sorted(
            (call.finished_at, key) for key, call in self._calls.items() if call.done.is_set()
        )
        for _finished_at, key in finished[: len(self._calls) - self._max_entries + 1]:
            del self._calls[key]
