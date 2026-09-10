"""启动类：装配配置、依赖、路由与异常处理，别的什么都不做。"""

from __future__ import annotations

from flask import Flask, request

from app.api import register_blueprints
from app.api.error_handler import register_error_handlers
from app.config import AgentConfig
from app.container import build_registry, build_services


def create_app(config: dict | None = None, *, registry=None, services=None) -> Flask:
    settings = AgentConfig.from_env()

    app = Flask(__name__)
    app.config.from_mapping(
        AGENT_ADMIN_TOKEN=settings.admin_token,
        AGENT_INTERNAL_TOKEN=settings.internal_token,
        MAX_CONTENT_LENGTH=settings.max_content_length,
    )
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False

    app.extensions["settings"] = settings
    app.extensions["model_provider_registry"] = registry or build_registry(settings)
    # TESTING 时跳过预热：加载嵌入模型并建 FAISS 索引要几十秒。
    app.extensions["services"] = services or build_services(
        settings, warm_up=not app.config.get("TESTING", False)
    )

    register_blueprints(app)
    register_error_handlers(app)

    @app.after_request
    def allow_tagentnote(response):
        origin = request.headers.get("Origin", "")
        if origin in {"http://127.0.0.1:5173", "http://localhost:5173"}:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    return app
