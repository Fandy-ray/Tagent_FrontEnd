"""路由层的请求合并：同一篇作文连点 / 刷新重交，只批一次、不占第二个闸门名额。"""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path

from app.api import exam as exam_api
from app.container import Services
from app.factory import create_app
from app.repository.provider_repository import ModelProviderRegistry
from app.util.singleflight import SingleFlight

PAPER = "排队论研究随机服务系统。" * 12


class SlowEssayService:
    def __init__(self, seconds=0.3):
        self.seconds = seconds
        self.calls = []
        self.lock = threading.Lock()

    def review_paper(self, text, topic, provider, notebook_ids=None):
        with self.lock:
            self.calls.append(text)
        time.sleep(self.seconds)
        return {"score": 75, "text_len": len(text)}


def make_client(service):
    temp = tempfile.mkdtemp()
    registry = ModelProviderRegistry(Path(temp) / "providers.json")
    registry.create_provider({
        "name": "m", "served_model_id": "m", "base_url": "http://127.0.0.1:9/v1",
        "upstream_model": "u", "auth_mode": "none", "api_key": "", "enabled": True,
    })
    services = Services(chat=None, quiz=None, exam=None, essay=service, knowledge_base=None, client_factory=None)
    return create_app({"TESTING": True}, registry=registry, services=services).test_client()


def post_many(client, bodies):
    results = [None] * len(bodies)

    def run(index, body):
        results[index] = client.post("/essay/review", json=body)

    threads = [threading.Thread(target=run, args=(i, body)) for i, body in enumerate(bodies)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    return results


def setup_function(_function):
    # 每个用例一份干净的合并表，免得上一个用例的重放结果串过来
    exam_api._flights = SingleFlight()


def test_identical_submissions_are_graded_once():
    service = SlowEssayService()
    client = make_client(service)
    responses = post_many(client, [{"model": "m", "text": PAPER}] * 4)

    assert [r.status_code for r in responses] == [200] * 4
    assert len(service.calls) == 1


def test_resubmitting_right_after_completion_replays_the_same_result():
    service = SlowEssayService(seconds=0.01)
    client = make_client(service)
    first = client.post("/essay/review", json={"model": "m", "text": PAPER})
    again = client.post("/essay/review", json={"model": "m", "text": PAPER})

    assert first.get_json()["data"] == again.get_json()["data"]
    assert len(service.calls) == 1


def test_different_papers_are_graded_separately():
    service = SlowEssayService()
    client = make_client(service)
    post_many(client, [{"model": "m", "text": PAPER}, {"model": "m", "text": PAPER + "另一段"}])

    assert len(service.calls) == 2


def test_same_text_with_a_different_topic_is_a_different_request():
    service = SlowEssayService(seconds=0.01)
    client = make_client(service)
    client.post("/essay/review", json={"model": "m", "text": PAPER, "topic": "A"})
    client.post("/essay/review", json={"model": "m", "text": PAPER, "topic": "B"})

    assert len(service.calls) == 2
