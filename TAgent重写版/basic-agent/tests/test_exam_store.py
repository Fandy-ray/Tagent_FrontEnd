"""exam_store 单测：缓存 TTL/淘汰/深拷贝、并发闸门释放语义。纯标准库。"""

import threading

import pytest

from app.errors.exam_errors import ExamBusyError, ExamGoneError

from app.repository.exam_cache import ExamCache, LLMGate


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_cache_roundtrip_returns_deep_copy():
    cache = ExamCache(ttl_seconds=10, max_items=5)
    cache.put("a", {"nested": {"points": 5}})
    copy1 = cache.get_copy("a")
    copy1["nested"]["points"] = 999
    assert cache.get_copy("a")["nested"]["points"] == 5


def test_cache_expires_by_monotonic_ttl():
    clock = FakeClock()
    cache = ExamCache(ttl_seconds=10, max_items=5, clock=clock)
    cache.put("a", 1)
    clock.now += 9
    assert cache.get_copy("a") == 1
    clock.now += 2
    with pytest.raises(ExamGoneError):
        cache.get_copy("a")


def test_cache_missing_raises_gone():
    cache = ExamCache()
    with pytest.raises(ExamGoneError):
        cache.get_copy("nope")


def test_cache_evicts_oldest_when_full():
    cache = ExamCache(ttl_seconds=100, max_items=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    with pytest.raises(ExamGoneError):
        cache.get_copy("a")
    assert cache.get_copy("b") == 2
    assert cache.get_copy("c") == 3


def test_cache_lazy_cleanup_frees_capacity():
    clock = FakeClock()
    cache = ExamCache(ttl_seconds=10, max_items=2, clock=clock)
    cache.put("a", 1)
    cache.put("b", 2)
    clock.now += 11  # 全部过期
    cache.put("c", 3)  # put 触发懒清理，不应误伤 c
    assert cache.get_copy("c") == 3
    assert len(cache) == 1


def test_gate_limits_and_releases():
    gate = LLMGate(max_concurrent=1)
    with gate.acquire():
        with pytest.raises(ExamBusyError):
            with gate.acquire():
                pass
    # 正常退出后名额归还
    with gate.acquire():
        pass


def test_gate_releases_on_exception():
    gate = LLMGate(max_concurrent=1)
    with pytest.raises(RuntimeError):
        with gate.acquire():
            raise RuntimeError("LLM 爆炸")
    # 异常后名额必须归还，不得永久占用
    with gate.acquire():
        pass


def test_gate_is_thread_safe_under_contention():
    gate = LLMGate(max_concurrent=2)
    active = []
    peak = []
    lock = threading.Lock()
    busy_count = []

    def worker():
        try:
            with gate.acquire():
                with lock:
                    active.append(1)
                    peak.append(len(active))
                import time
                time.sleep(0.05)
                with lock:
                    active.pop()
        except ExamBusyError:
            with lock:
                busy_count.append(1)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert max(peak) <= 2
    assert len(busy_count) >= 1  # 超出名额的请求确实被 429 拒绝
