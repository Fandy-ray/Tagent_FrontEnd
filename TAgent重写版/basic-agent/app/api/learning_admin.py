"""老师看学情：学习记录库的只读接口 + 手动备份。

和模型登记同一套管理员口令（X-Agent-Admin-Token）：这里能读到学生的原文和成绩，
不能像答疑接口那样对谁都开放。没配口令时整组接口 503。
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.deps import get_learning_store
from app.api.security import require_admin_token
from app.errors.api_errors import AgentAPIError


blueprint = Blueprint("learning_admin", __name__, url_prefix="/admin/learning")

MAX_LIMIT = 500


def _store():
    require_admin_token()
    store = get_learning_store()
    if store is None:
        raise AgentAPIError(
            "学习记录库没有启用（LEARNING_STORE=0，或启动时没能打开数据库文件）。",
            503,
            "learning_store_unavailable",
        )
    return store


def _limit(default: int) -> int:
    raw = request.args.get("limit", "")
    if not raw:
        return default
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_LIMIT:
        raise AgentAPIError(f"limit 要在 1 到 {MAX_LIMIT} 之间。", 400, "validation_error")
    return int(raw)


@blueprint.get("/summary")
def summary():
    """全班概览：总量 + 每个学生的提问数、批改数与平均分。"""
    return jsonify(_store().summary(limit=_limit(MAX_LIMIT)))


@blueprint.get("/students/<string:student_id>")
def student(student_id: str):
    """一个学生最近的答疑、论文批改、整卷记录（各取最近 limit 条，带原文与批改结果）。"""
    timeline = _store().student_timeline(student_id, limit=_limit(50))
    if timeline["student"] is None:
        raise AgentAPIError("没有这个学生的记录。", 404, "student_not_found")
    return jsonify(timeline)


@blueprint.post("/backup")
def backup():
    """立刻备份一份（平时每天自动备一次，比赛、演示前可以手动再备一次）。"""
    target = _store().backup()
    return jsonify({"status": True, "file": target.name, "bytes": target.stat().st_size})
