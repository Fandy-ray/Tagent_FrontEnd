"""请求合并：同样的请求正在跑就等它，刚跑完就重放，失败不重放。离线运行。"""

from __future__ import annotations

import threading
import time

import pytest

from app.util.singleflight import SingleFlight, fingerprint


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_concurrent_identical_calls_run_once():
    flight = SingleFlight()
    calls = []
    release = threading.Event()

    def work():
        calls.append(1)
        release.wait(5)
        return {"score": 75}

    results = []
    threads = [threading.Thread(target=lambda: results.append(flight.do("k", work))) for _ in range(5)]
    for thread in threads:
        thread.start()
    time.sleep(0.1)
    release.set()
    for thread in threads:
        thread.join(5)

    assert len(calls) == 1, "同样的请求只该真的跑一次"
    assert results == [{"score": 75}] * 5


def test_result_is_replayed_within_the_window_only():
    clock = Clock()
    flight = SingleFlight(clock=clock)
    calls = []

    def work():
        calls.append(1)
        return len(calls)

    assert flight.do("k", work, replay_seconds=90) == 1
    clock.now += 60
    assert flight.do("k", work, replay_seconds=90) == 1, "窗口内重放同一份结果"
    clock.now += 31
    assert flight.do("k", work, replay_seconds=90) == 2, "过了窗口就真的再算一次"


def test_without_replay_nothing_is_kept_after_completion():
    flight = SingleFlight()
    calls = []

    def work():
        calls.append(1)
        return len(calls)

    assert flight.do("k", work) == 1
    assert flight.do("k", work) == 2
    assert flight._calls == {}, "不重放的请求跑完就不该留在内存里"


def test_failures_are_shared_with_waiters_but_never_replayed():
    flight = SingleFlight()
    release = threading.Event()
    attempts = []

    def failing():
        attempts.append(1)
        release.wait(5)
        raise RuntimeError("上游挂了")

    errors = []

    def call():
        try:
            flight.do("k", failing, replay_seconds=90)
        except RuntimeError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=call) for _ in range(3)]
    for thread in threads:
        thread.start()
    time.sleep(0.1)
    release.set()
    for thread in threads:
        thread.join(5)

    assert errors == ["上游挂了"] * 3
    assert len(attempts) == 1
    assert flight.do("k", lambda: "好了", replay_seconds=90) == "好了", "失败之后下一次要真的重试"


def test_different_requests_do_not_share_results():
    flight = SingleFlight()
    assert flight.do(fingerprint("essay/review", "a"), lambda: "A") == "A"
    assert flight.do(fingerprint("essay/review", "b"), lambda: "B") == "B"


def test_capacity_evicts_finished_entries_never_running_ones():
    clock = Clock()
    flight = SingleFlight(max_entries=2, clock=clock)
    release = threading.Event()
    running = threading.Thread(target=lambda: flight.do("running", lambda: release.wait(5)))
    running.start()
    time.sleep(0.05)

    flight.do("old", lambda: "old", replay_seconds=90)
    clock.now += 1
    flight.do("new", lambda: "new", replay_seconds=90)

    assert "running" in flight._calls, "有人在等的请求不能被挤掉"
    assert "old" not in flight._calls
    release.set()
    running.join(5)


def test_fingerprint_is_order_insensitive_for_dict_fields_and_hides_the_text():
    a = fingerprint("essay/review", {"text": "排队论……", "topic": "银行"})
    b = fingerprint("essay/review", {"topic": "银行", "text": "排队论……"})
    assert a == b
    assert "排队论" not in a


@pytest.mark.parametrize("replay", [0.0, 90.0])
def test_leader_exception_propagates(replay):
    flight = SingleFlight()
    with pytest.raises(ValueError):
        flight.do("k", lambda: (_ for _ in ()).throw(ValueError("x")), replay_seconds=replay)
