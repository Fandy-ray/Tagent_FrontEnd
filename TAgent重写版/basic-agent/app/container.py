"""依赖装配。

工厂函数而不是 DI 框架：只有几个单例，上框架是负收益。
唯一的职责是"谁依赖谁"这件事写在一处，别散落在 create_app 里。

三个 service 共用同一个 KnowledgeBase 和同一个 ModelClientFactory：
嵌入模型 + FAISS 索引很贵，HTTP 连接池也需要统一失效，各建一份会出错。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import AgentConfig
from app.repository.provider_repository import load_model_registry


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Services:
    """一次请求可能用到的全部业务服务，外加它们共享的两个重资源。"""

    chat: "object"
    quiz: "object"
    exam: "object"
    knowledge_base: "object"
    client_factory: "object"

    def warm_up(self) -> None:
        """预热知识库。三个 service 共用它，热一次就够。

        预热失败不再把进程拉死：否则国内镜像 SSL 一断、或 OpenNotebook
        没开，basic-agent 会在 create_app 里直接退出，/health 永远探不到。
        检索/出题会在来源可用后于首次请求再试。
        """
        try:
            self.knowledge_base.warm_up()
        except Exception as exc:
            log.error("知识库预热失败，HTTP 服务仍会启动：%s", exc)

    def invalidate_provider(self, served_model_id: str | None) -> None:
        """provider 配置变了，丢掉缓存的上游客户端。"""
        self.client_factory.invalidate(served_model_id)

    def close(self) -> None:
        self.client_factory.close()


def build_registry(settings: AgentConfig):
    return load_model_registry(settings.model_providers_path)


def build_services(settings: AgentConfig, *, warm_up: bool = True) -> Services:
    # 延迟 import：这几个模块会拉起 langchain/langgraph，
    # 只想构造 app 做单测时不该付这个代价。
    from app.infra.model_client_factory import ModelClientFactory
    from app.service.chat_service import ChatService
    from app.service.exam_service import ExamService
    from app.service.quiz_service import QuizService

    knowledge_base = build_knowledge_base(settings)
    client_factory = ModelClientFactory()

    services = Services(
        chat=ChatService(knowledge_base, client_factory),
        quiz=QuizService(knowledge_base, client_factory),
        exam=ExamService(
            knowledge_base,
            client_factory,
            max_concurrent_llm=settings.exam_max_concurrent_llm,
        ),
        knowledge_base=knowledge_base,
        client_factory=client_factory,
    )
    if warm_up:
        services.warm_up()
    return services


def build_knowledge_base(settings: AgentConfig):
    """按配置装配知识来源。默认仍是本地教材，避免没开 OpenNotebook 时启动失败。"""
    from app.rag.knowledge_base import KnowledgeBase

    local = KnowledgeBase(
        text_db_dir=settings.text_db_dir,
        knowledge_file=settings.knowledge_file,
    )
    if settings.knowledge_source == "local":
        return local

    from app.rag.opennotebook_kb import OpenNotebookKnowledgeBase

    # notebook_url 已由 config.normalize_notebook_url 换算成接口基址（默认 5055）。
    log.info(
        "知识来源 = %s，OpenNotebook 接口基址 = %s",
        settings.knowledge_source,
        settings.notebook_url,
    )
    notebook = OpenNotebookKnowledgeBase(
        base_url=settings.notebook_url,
        token=settings.notebook_token,
    )
    if settings.knowledge_source == "notebook":
        return notebook

    from app.rag.composite_kb import CompositeKnowledgeBase

    return CompositeKnowledgeBase(local, notebook)
