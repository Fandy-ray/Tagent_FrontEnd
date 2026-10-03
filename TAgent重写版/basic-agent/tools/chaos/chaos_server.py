"""真实后端栈 + 假上游：路由、闸门、service、JSON 重试、HTTP 模型客户端都是真的，只有模型是假的。

服务名沿用 deepseek，前端不用改就能连上；用 waitress 8 线程，和 main.py 一致。
"""
import os
import sys
import tempfile
from pathlib import Path

BA = str(Path(__file__).resolve().parents[2])  # basic-agent/
sys.path.insert(0, BA)
os.chdir(BA)

from langchain_core.documents import Document  # noqa: E402

from app.config import LLM_GATE_MAX_WAITING, LLM_GATE_WAIT_SECONDS, AgentConfig  # noqa: E402
from app.container import Services, build_learning_store  # noqa: E402
from app.factory import create_app  # noqa: E402
from app.infra.model_client_factory import ModelClientFactory  # noqa: E402
from app.repository.exam_cache import LLMGate  # noqa: E402
from app.repository.provider_repository import ModelProviderRegistry  # noqa: E402
from app.service.chat_service import ChatService  # noqa: E402
from app.service.essay_service import EssayService  # noqa: E402
from app.service.exam_service import ExamService  # noqa: E402
from app.service.quiz_service import QuizService  # noqa: E402

MATERIAL = "排队论研究随机到达与服务的系统。M/M/1 模型假设到达服从泊松过程、服务时间服从指数分布。"


class FakeKB:
    def describe(self):
        return {"kind": "fake"}

    def warm_up(self):
        pass

    def search(self, query, *, k=3, notebook_ids=None):
        return [Document(page_content=MATERIAL)]

    def retrieve(self, query, notebook_ids=None):
        return MATERIAL, [Document(page_content=MATERIAL)]


# 学习记录默认写进临时目录，不碰真实的应用数据目录；要看记录就自己指定 TAGENT_DB_PATH
os.environ.setdefault("TAGENT_DB_PATH", str(Path(tempfile.mkdtemp(prefix="chaos-db-")) / "tagent.sqlite3"))
settings = AgentConfig.from_env()
registry = ModelProviderRegistry(Path(tempfile.mkdtemp(prefix="chaos-")) / "providers.json")
registry.create_provider({
    "name": "DeepSeek（假上游）", "served_model_id": "deepseek", "base_url": os.getenv("CHAOS_UPSTREAM", "http://127.0.0.1:9100") + "/v1",
    "upstream_model": "fake-model", "auth_mode": "none", "api_key": "", "enabled": True,
})
kb, factory = FakeKB(), ModelClientFactory()
gate = LLMGate(max_concurrent=settings.exam_max_concurrent_llm, wait_seconds=LLM_GATE_WAIT_SECONDS, max_waiting=LLM_GATE_MAX_WAITING)
services = Services(
    chat=ChatService(kb, factory),
    quiz=QuizService(kb, factory),
    exam=ExamService(kb, factory, llm_gate=gate),
    essay=EssayService(knowledge_base=kb, client_factory=factory, llm_gate=gate),
    knowledge_base=kb,
    client_factory=factory,
    store=build_learning_store(settings),
)
app = create_app({"TESTING": True}, registry=registry, services=services)

if __name__ == "__main__":
    from waitress import serve

    print(f"chaos backend: gate={settings.exam_max_concurrent_llm} threads={settings.waitress_threads} "
          f"db={settings.resolved_learning_db_path() if services.store else 'off'}", flush=True)
    serve(app, host="127.0.0.1", port=int(os.getenv("CHAOS_PORT", "5001")), threads=settings.waitress_threads)
