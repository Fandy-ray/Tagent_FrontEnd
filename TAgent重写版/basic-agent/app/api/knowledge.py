"""知识来源状态。给基础前端看现在用的是教材、笔记库还是两边一起。"""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.api.deps import get_services
from app.config import AgentConfig


blueprint = Blueprint("knowledge", __name__)


@blueprint.get("/knowledge")
def knowledge_status():
    settings = AgentConfig.from_env()
    knowledge_base = get_services().knowledge_base
    payload = (
        knowledge_base.describe()
        if hasattr(knowledge_base, "describe")
        else {"kind": type(knowledge_base).__name__}
    )
    reachable = None
    if settings.knowledge_source in {"notebook", "composite"} and hasattr(knowledge_base, "ping"):
        try:
            reachable = bool(knowledge_base.ping())
        except Exception:
            reachable = False
    elif settings.knowledge_source == "composite":
        reachable = _notebook_reachable(knowledge_base)
    return jsonify(
        {
            "source": settings.knowledge_source,
            "notebook_url": settings.notebook_url,
            "notebook_reachable": reachable,
            "knowledge_base": payload,
        }
    )


def _notebook_reachable(knowledge_base) -> bool | None:
    sources = getattr(knowledge_base, "sources", ())
    for source in sources:
        if hasattr(source, "ping"):
            try:
                return bool(source.ping())
            except Exception:
                return False
    return None
