"""学习记录的持久化存储（SQLite）：答疑对话、论文批改、整卷作答与成绩。

为什么是 SQLite（选型与压测见 TAgent重写版/文档/数据库方案选型与压测报告.md）：
- 崩溃测试里已确认的写入零丢失、成批事务不会只进去半批；
- 就在应用进程里，单机读写比服务端库快 2~6 倍，不多一个要起、要守的服务；
- Python 自带，macOS / Windows / Linux 一样用，不依赖 Docker。

几条约定：
- **每个线程一个连接**（sqlite3 连接不能跨线程共用），WAL 模式下读写互不阻塞；
- **记录是尽力而为**：由调用方包一层 try/except（见 app/api/learner.py），存不进去只记日志，
  绝不能因此让答疑、批改失败；所以这里的忙等待也设得短（默认 2 秒），宁可丢一条记录也不卡住用户；
- 表结构用 PRAGMA user_version 记版本，启动时按顺序升级；
- 时间一律存毫秒时间戳（整数），JSON 一律存文本（SQLite 自带 JSON 函数能查）。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

def now_ms() -> int:
    return int(time.time() * 1000)


# 每一项是把库从 N-1 版升到 N 版的语句；只能往后追加，不能改已经发布的。
# 升级时按分号切成单条、包在一个事务里执行（失败整版回滚），所以语句和注释里都别出现分号。
MIGRATIONS: list[str] = [
    """
    CREATE TABLE students (
        id            TEXT PRIMARY KEY,           -- 前端生成的匿名设备编号
        name          TEXT NOT NULL DEFAULT '',   -- 学生在设置里填的昵称
        first_seen_at INTEGER NOT NULL,
        last_seen_at  INTEGER NOT NULL
    );

    CREATE TABLE chat_turns (
        id            INTEGER PRIMARY KEY,
        student_id    TEXT,                       -- 可空：没带编号的请求（脚本调用等）
        mode          TEXT NOT NULL,              -- qa | paper
        model         TEXT NOT NULL,
        question      TEXT NOT NULL,
        answer        TEXT NOT NULL,
        finish_reason TEXT,                       -- stop / length / interrupted / error
        notebook_ids  TEXT,                       -- JSON 数组
        duration_ms   INTEGER,
        created_at    INTEGER NOT NULL
    );
    CREATE INDEX idx_chat_student_time ON chat_turns (student_id, created_at);

    CREATE TABLE essay_reviews (
        id          INTEGER PRIMARY KEY,
        student_id  TEXT,
        model       TEXT NOT NULL,
        topic       TEXT,
        text        TEXT NOT NULL,
        score       INTEGER NOT NULL,
        review      TEXT NOT NULL,                -- 完整批改结果 JSON（维度、批注、总评）
        created_at  INTEGER NOT NULL
    );
    CREATE INDEX idx_essay_student_time ON essay_reviews (student_id, created_at);
    -- 学情统计（每人平均分）的覆盖索引：不建的话要逐行回表，压测里慢 37 倍
    CREATE INDEX idx_essay_student_score ON essay_reviews (student_id, score);

    CREATE TABLE exam_attempts (
        exam_id      TEXT PRIMARY KEY,
        student_id   TEXT,
        model        TEXT NOT NULL,
        title        TEXT NOT NULL DEFAULT '',
        topic        TEXT,
        total_points INTEGER,
        paper        TEXT,                        -- JSON：发给学生的卷面（不含答案）
        score        INTEGER,                     -- 交卷前为空
        answers      TEXT,                        -- JSON，交卷后才有
        review       TEXT,                        -- JSON，交卷后才有
        created_at   INTEGER NOT NULL,
        reviewed_at  INTEGER
    );
    CREATE INDEX idx_exam_student_time ON exam_attempts (student_id, created_at);
    CREATE INDEX idx_exam_student_score ON exam_attempts (student_id, score, total_points);
    """,
]


class LearningStore:
    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 2000, backup_keep: int = 7):
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms
        self.backup_keep = backup_keep
        self.backup_dir = self.path.parent / "backups"
        self._local = threading.local()
        self._backup_thread: threading.Thread | None = None
        self._stop = threading.Event()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate(self._conn())

    # ====================== 连接 ======================
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.path,
                timeout=self.busy_timeout_ms / 1000,
                isolation_level=None,  # 自动提交；成组写入自己包 BEGIN/COMMIT
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            for pragma in (
                "PRAGMA journal_mode=WAL",
                # WAL 下的推荐配置：进程崩溃不丢已提交的数据（压测实测）；断电可能丢最后几次提交
                "PRAGMA synchronous=NORMAL",
                f"PRAGMA busy_timeout={self.busy_timeout_ms}",
                # 默认页缓存只有 2 MB，库一大随机读几乎次次读文件（macOS 上慢 20 倍）。
                # 主要靠 mmap（各连接共享系统的文件缓存，不重复占内存）；页缓存是每个连接
                # 各一份的，服务有几十个线程，所以只给 16 MB，不照搬压测里单连接的 64 MB。
                "PRAGMA mmap_size=268435456",
                "PRAGMA cache_size=-16384",
                "PRAGMA temp_store=MEMORY",
                "PRAGMA foreign_keys=ON",
            ):
                conn.execute(pragma)
            self._local.conn = conn
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for target, script in enumerate(MIGRATIONS[version:], start=version + 1):
            conn.execute("BEGIN IMMEDIATE")
            try:
                for statement in (s.strip() for s in script.split(";")):
                    if statement:
                        conn.execute(statement)
                conn.execute(f"PRAGMA user_version={target}")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            log.info("学习记录库升级到第 %s 版：%s", target, self.path)

    @property
    def schema_version(self) -> int:
        return self._conn().execute("PRAGMA user_version").fetchone()[0]

    # ====================== 写 ======================
    def touch_student(self, student_id: str, name: str = "") -> None:
        at = now_ms()
        self._conn().execute(
            "INSERT INTO students (id, name, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET last_seen_at = excluded.last_seen_at, "
            "name = CASE WHEN excluded.name <> '' THEN excluded.name ELSE students.name END",
            (student_id, name, at, at),
        )

    def record_chat(
        self,
        *,
        student_id: str | None,
        mode: str,
        model: str,
        question: str,
        answer: str,
        finish_reason: str | None = None,
        notebook_ids: list[str] | None = None,
        duration_ms: int | None = None,
    ) -> int:
        cur = self._conn().execute(
            "INSERT INTO chat_turns (student_id, mode, model, question, answer, finish_reason, notebook_ids, "
            "duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (student_id, mode, model, question, answer, finish_reason,
             json.dumps(notebook_ids or [], ensure_ascii=False), duration_ms, now_ms()),
        )
        return cur.lastrowid

    def record_essay_review(
        self, *, student_id: str | None, model: str, topic: str | None, text: str, review: dict[str, Any]
    ) -> int:
        cur = self._conn().execute(
            "INSERT INTO essay_reviews (student_id, model, topic, text, score, review, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (student_id, model, topic, text, int(review.get("score", 0)),
             json.dumps(review, ensure_ascii=False), now_ms()),
        )
        return cur.lastrowid

    def record_exam_generated(
        self,
        *,
        student_id: str | None,
        exam_id: str,
        model: str,
        title: str,
        topic: str | None,
        total_points: int | None,
        paper: dict[str, Any] | None = None,
    ) -> None:
        self._conn().execute(
            "INSERT INTO exam_attempts (exam_id, student_id, model, title, topic, total_points, paper, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(exam_id) DO NOTHING",
            (exam_id, student_id, model, title, topic, total_points,
             json.dumps(paper, ensure_ascii=False) if paper is not None else None, now_ms()),
        )

    def record_exam_reviewed(
        self,
        *,
        student_id: str | None,
        exam_id: str,
        model: str,
        answers: dict[str, Any],
        review: dict[str, Any],
    ) -> None:
        """交卷结果。出卷那条没记上（比如当时库不可用）也能补一条完整的。"""
        at = now_ms()
        self._conn().execute(
            "INSERT INTO exam_attempts (exam_id, student_id, model, title, total_points, score, answers, review, "
            "created_at, reviewed_at) VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(exam_id) DO UPDATE SET score = excluded.score, answers = excluded.answers, "
            "review = excluded.review, total_points = excluded.total_points, reviewed_at = excluded.reviewed_at, "
            "student_id = COALESCE(exam_attempts.student_id, excluded.student_id)",
            (exam_id, student_id, model, review.get("total_points"), review.get("total_score"),
             json.dumps(answers, ensure_ascii=False), json.dumps(review, ensure_ascii=False), at, at),
        )

    # ====================== 读（老师看学情） ======================
    def summary(self, limit: int = 500) -> dict[str, Any]:
        conn = self._conn()
        totals = conn.execute(
            "SELECT (SELECT COUNT(*) FROM students) AS students, (SELECT COUNT(*) FROM chat_turns) AS chat_turns, "
            "(SELECT COUNT(*) FROM essay_reviews) AS essay_reviews, "
            "(SELECT COUNT(*) FROM exam_attempts WHERE score IS NOT NULL) AS exams_reviewed"
        ).fetchone()
        rows = conn.execute(
            """
            SELECT s.id, s.name, s.first_seen_at, s.last_seen_at,
                   (SELECT COUNT(*) FROM chat_turns c WHERE c.student_id = s.id) AS chat_turns,
                   (SELECT COUNT(*) FROM essay_reviews e WHERE e.student_id = s.id) AS essay_reviews,
                   (SELECT ROUND(AVG(score), 1) FROM essay_reviews e WHERE e.student_id = s.id) AS essay_avg,
                   (SELECT COUNT(*) FROM exam_attempts x WHERE x.student_id = s.id AND x.score IS NOT NULL) AS exams_reviewed,
                   (SELECT ROUND(AVG(score * 100.0 / total_points), 1) FROM exam_attempts x
                     WHERE x.student_id = s.id AND x.score IS NOT NULL AND x.total_points > 0) AS exam_avg_percent
            FROM students s ORDER BY s.last_seen_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return {"totals": dict(totals), "students": [dict(r) for r in rows]}

    def student_timeline(self, student_id: str, limit: int = 50) -> dict[str, Any]:
        conn = self._conn()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        chats = conn.execute(
            "SELECT id, mode, model, question, answer, finish_reason, duration_ms, created_at FROM chat_turns "
            "WHERE student_id = ? ORDER BY created_at DESC LIMIT ?", (student_id, limit)).fetchall()
        essays = conn.execute(
            "SELECT id, model, topic, text, score, review, created_at FROM essay_reviews "
            "WHERE student_id = ? ORDER BY created_at DESC LIMIT ?", (student_id, limit)).fetchall()
        exams = conn.execute(
            "SELECT exam_id, model, title, topic, total_points, paper, score, answers, review, created_at, reviewed_at "
            "FROM exam_attempts WHERE student_id = ? ORDER BY created_at DESC LIMIT ?", (student_id, limit)).fetchall()

        def decode(row, *fields):
            item = dict(row)
            for field in fields:
                if item.get(field):
                    item[field] = json.loads(item[field])
            return item

        return {
            "student": dict(student) if student else None,
            "chat_turns": [dict(r) for r in chats],
            "essay_reviews": [decode(r, "review") for r in essays],
            "exam_attempts": [decode(r, "paper", "answers", "review") for r in exams],
        }

    # ====================== 备份 ======================
    def backup(self) -> Path:
        """在线备份：不停服务、不挡写入（100 万条约 1.6 秒）。只保留最近 backup_keep 份。"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        target = self.backup_dir / f"tagent-{time.strftime('%Y%m%d-%H%M%S')}.sqlite3"
        partial = target.with_suffix(".partial")
        dest = sqlite3.connect(partial)
        try:
            self._conn().backup(dest)
        finally:
            dest.close()
        os.replace(partial, target)  # 写完整了才改名，备份目录里不会出现半截的文件
        for old in sorted(self.backup_dir.glob("tagent-*.sqlite3"))[: -self.backup_keep]:
            old.unlink(missing_ok=True)
        return target

    def latest_backup_age_s(self) -> float | None:
        backups = sorted(self.backup_dir.glob("tagent-*.sqlite3"))
        return (time.time() - backups[-1].stat().st_mtime) if backups else None

    def start_daily_backup(self, *, every_s: float = 86_400, check_s: float = 3600) -> None:
        """后台线程：距上次备份满一天就备一份。进程刚起来时若从没备份过，也会先备一份。"""
        if self._backup_thread is not None:
            return

        def loop():
            while not self._stop.is_set():
                try:
                    age = self.latest_backup_age_s()
                    if age is None or age >= every_s:
                        log.info("学习记录已备份：%s", self.backup())
                except Exception as exc:  # noqa: BLE001 —— 备份失败不能拖垮服务
                    log.warning("学习记录备份失败：%s", exc)
                self._stop.wait(check_s)

        self._backup_thread = threading.Thread(target=loop, name="learning-store-backup", daemon=True)
        self._backup_thread.start()

    def close(self) -> None:
        self._stop.set()
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
