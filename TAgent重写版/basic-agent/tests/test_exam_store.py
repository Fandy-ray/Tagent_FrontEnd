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


# ====================== 闸门满了先排队 ======================
def test_a_full_gate_queues_briefly_instead_of_failing_at_once():
    gate = LLMGate(max_concurrent=1, wait_seconds=2, max_waiting=4)
    results = []

    def holder():
        with gate.acquire():
            import time
            time.sleep(0.2)

    def waiter():
        try:
            with gate.acquire():
                results.append("ok")
        except ExamBusyError:
            results.append("busy")

    first = threading.Thread(target=holder)
    first.start()
    import time
    time.sleep(0.05)
    waiters = [threading.Thread(target=waiter) for _ in range(3)]
    for t in waiters:
        t.start()
    for t in [first, *waiters]:
        t.join(5)
    assert results == ["ok", "ok", "ok"]


def test_the_queue_has_a_length_limit():
    gate = LLMGate(max_concurrent=1, wait_seconds=1, max_waiting=1)
    started = threading.Event()
    outcomes = []

    def holder():
        with gate.acquire():
            started.set()
            import time
            time.sleep(0.5)

    def queued():
        try:
            with gate.acquire():
                outcomes.append("ok")
        except ExamBusyError:
            outcomes.append("busy")

    threading.Thread(target=holder).start()
    started.wait(2)
    in_queue = threading.Thread(target=queued)
    in_queue.start()
    import time
    time.sleep(0.05)
    with pytest.raises(ExamBusyError):  # 队里已经有一个人，第二个直接 429，不占线程干等
        with gate.acquire():
            pass
    in_queue.join(3)
    assert outcomes == ["ok"]


def test_waiting_too_long_gives_up_with_a_clear_message():
    gate = LLMGate(max_concurrent=1, wait_seconds=0.1, max_waiting=2)
    with gate.acquire():
        with pytest.raises(ExamBusyError, match="排了"):
            with gate.acquire():
                pass
    with gate.acquire():  # 名额照常归还
        pass
