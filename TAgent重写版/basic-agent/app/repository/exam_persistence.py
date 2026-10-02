"""把出好的私有卷存进学习记录库，basic-agent 重启后学生照样能交卷。

以前私有卷（含答案与评分规则）只在内存里：演示时有人重跑了一次启动脚本、或者进程崩了，
学生刷新后卷子还在（前端存在本标签页），一交卷却是「试卷不存在或已过期」，答案白写。

尽力而为：库没开、写不进、读出来解析不了，都只记日志——退回只有内存的老样子，不让出卷 / 判卷失败。
"""

from __future__ import annotations

import logging
import time

from app.repository.exam_cache import StoredExam
from app.schema.exam import PrivateExam


log = logging.getLogger(__name__)


class ExamPersistence:
    def __init__(self, store):
        self._store = store

    def save(self, exam_id: str, exam, ttl_seconds: float) -> None:
        if not isinstance(exam, StoredExam):
            return  # 只有正式的 StoredExam 才落盘（老单测里直接塞的裸对象不管）
        try:
            self._store.save_cached_exam(
                exam_id,
                exam.served_model_id,
                exam.exam.model_dump_json(),
                int((time.time() + ttl_seconds) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("私有卷没存上盘（重启后这张卷交不了），照常出卷：%s", exc)

    def load(self, exam_id: str):
        try:
            row = self._store.load_cached_exam(exam_id)
            if row is None:
                return None
            served_model_id, exam_json, expires_at_ms = row
            exam = StoredExam(exam=PrivateExam.model_validate_json(exam_json), served_model_id=served_model_id)
            return exam, max(0.0, expires_at_ms / 1000 - time.time())
        except Exception as exc:  # noqa: BLE001
            log.warning("盘上的私有卷读不出来，当作已过期：%s", exc)
            return None
