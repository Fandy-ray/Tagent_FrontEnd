from flask import Blueprint, jsonify

from app.api.deps import get_learning_store


blueprint = Blueprint("health", __name__)


@blueprint.get("/")
@blueprint.get("/health")
def health():
    # learning_store 只报开没开：库文件在哪是本机路径，不该对谁都说（老师接口里也不回路径）。
    return jsonify(
        {
            "status": "ok",
            "service": "basic-agent",
            "learning_store": "on" if get_learning_store() is not None else "off",
        }
    )
