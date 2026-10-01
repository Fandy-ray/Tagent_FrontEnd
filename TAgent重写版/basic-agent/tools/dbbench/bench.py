"""数据库方案多维度压测：同一份数据、同一组操作，跑 SQLite / DuckDB / PostgreSQL / MySQL / MongoDB / SurrealDB。

数据模拟 TAgent 的真实负载：
  messages  对话消息（学生 2000 人、40 个班），默认 100 万条，每条 80~400 字
  essays    小论文批改记录（原文 1200~2500 字 + 批改 JSON 约 2~3 KB），默认 2 万篇

用法：python bench.py <sqlite|duckdb|postgres|mysql|mongo|surreal> --out results/xxx.json [--n 1000000] [--essays 20000]
连接参数走环境变量（见 connect_*）；嵌入式库的数据文件放在 $DATA_DIR（默认 ./data）。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import statistics
import sys
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
STUDENTS, CLASSES = 2000, 40
BASE_MS = 1_780_000_000_000
WORDS = ["排队论", "到达率", "服务率", "泊松过程", "指数分布", "离散事件仿真", "实体", "资源", "队列长度",
         "稳态", "利用率", "平均等待时间", "系统边界", "模型验证", "蒙特卡洛", "随机数", "服务台", "吞吐量",
         "输入建模", "输出分析", "置信区间", "预热期", "事件调度", "活动周期图"]
SEP = "，。的是在和对把"


# ====================== 数据 ======================
def text(rng: random.Random, pairs: int) -> str:
    return "".join(rng.choice(WORDS) + rng.choice(SEP) for _ in range(pairs))


def message_row(rng: random.Random, i: int):
    student = rng.randrange(STUDENTS)
    return (
        i, student, student % CLASSES, rng.randrange(20_000), rng.choice(("user", "assistant")),
        text(rng, rng.randint(20, 80)),
        None if rng.random() < 0.7 else round(rng.uniform(0, 100), 1),
        BASE_MS + rng.randrange(120 * 86_400_000),
    )


def essay_row(rng: random.Random, i: int):
    student = rng.randrange(STUDENTS)
    body = text(rng, rng.randint(300, 600))
    review = {
        "score": rng.randint(40, 100),
        "dimensions": [{"name": n, "score_ratio": rng.choice([0.25, 0.5, 0.75, 1.0]),
                        "hits": [text(rng, 6) for _ in range(2)], "misses": [text(rng, 6) for _ in range(2)],
                        "comment": text(rng, 15)} for n in ("content", "argument", "language")],
        "annotations": [{"sentence_id": f"P{rng.randint(1, 5)}S{rng.randint(1, 6)}", "kind": rng.choice(("issue", "praise")),
                         "comment": text(rng, 12), "start": rng.randrange(1000), "end": rng.randrange(1000, 2000)}
                        for _ in range(5)],
    }
    return (i, student, student % CLASSES, text(rng, 6), body, json.dumps(review, ensure_ascii=False),
            review["score"], BASE_MS + rng.randrange(120 * 86_400_000))


def batches(n: int, size: int, start: int = 1, seed: int = 7, maker=message_row):
    rng = random.Random(seed)
    for lo in range(start, start + n, size):
        yield [maker(rng, i) for i in range(lo, min(lo + size, start + n))]


# ====================== 适配层 ======================
MSG_COLS = "id, student_id, class_id, conv_id, role, content, score, created_at"
ESSAY_COLS = "id, student_id, class_id, topic, body, review, score, created_at"


class SQLDB:
    """关系库的公共部分：各库只需给出连接、占位符和少数方言差异。"""

    name = "sql"
    ph = "?"
    review_type = "TEXT"
    bulk_batch = 5000

    def schema(self):
        return [
            f"CREATE TABLE messages (id BIGINT PRIMARY KEY, student_id INTEGER NOT NULL, class_id INTEGER NOT NULL, "
            f"conv_id INTEGER NOT NULL, role VARCHAR(16) NOT NULL, content TEXT NOT NULL, score DOUBLE PRECISION, created_at BIGINT NOT NULL)",
            "CREATE INDEX idx_msg_student ON messages (student_id, created_at)",
            "CREATE INDEX idx_msg_class ON messages (class_id)",
            f"CREATE TABLE essays (id BIGINT PRIMARY KEY, student_id INTEGER NOT NULL, class_id INTEGER NOT NULL, "
            f"topic TEXT NOT NULL, body TEXT NOT NULL, review {self.review_type} NOT NULL, score INTEGER NOT NULL, created_at BIGINT NOT NULL)",
            "CREATE INDEX idx_essay_student ON essays (student_id, created_at)",
        ]

    def q(self, sql: str) -> str:
        return sql.replace("?", self.ph)

    # 每个库自己实现：connect / reset / commit 语义
    def run(self, con, sql, params=()):
        cur = con.cursor()
        cur.execute(self.q(sql), params)
        return cur

    def insert_messages(self, con, rows):
        cur = con.cursor()
        cur.executemany(self.q(f"INSERT INTO messages ({MSG_COLS}) VALUES (?,?,?,?,?,?,?,?)"), rows)
        self.commit(con)

    def insert_essays(self, con, rows):
        cur = con.cursor()
        cur.executemany(self.q(f"INSERT INTO essays ({ESSAY_COLS}) VALUES (?,?,?,?,?,?,?,?)"), rows)
        self.commit(con)

    def insert_one(self, con, row):
        self.run(con, f"INSERT INTO messages ({MSG_COLS}) VALUES (?,?,?,?,?,?,?,?)", row)
        self.commit(con)

    def get(self, con, i):
        return self.run(con, "SELECT * FROM messages WHERE id = ?", (i,)).fetchone()

    def recent(self, con, student):
        return self.run(con, "SELECT * FROM messages WHERE student_id = ? ORDER BY created_at DESC LIMIT 20", (student,)).fetchall()

    def class_avg(self, con):
        return self.run(con, "SELECT class_id, AVG(score) FROM messages WHERE score IS NOT NULL GROUP BY class_id").fetchall()

    def search(self, con, kw):
        return self.run(con, "SELECT id FROM messages WHERE content LIKE ? LIMIT 20", (f"%{kw}%",)).fetchall()

    def get_essay(self, con, i):
        row = self.run(con, "SELECT * FROM essays WHERE id = ?", (i,)).fetchone()
        review = row[5]
        return json.loads(review) if isinstance(review, str) else review

    def update_one(self, con, i, v):
        self.run(con, "UPDATE messages SET score = ? WHERE id = ?", (v, i))
        self.commit(con)

    def update_many(self, con, ids, v):
        marks = ",".join("?" * len(ids))
        self.run(con, f"UPDATE messages SET score = ? WHERE id IN ({marks})", (v, *ids))
        self.commit(con)

    def delete_one(self, con, i):
        self.run(con, "DELETE FROM messages WHERE id = ?", (i,))
        self.commit(con)

    def delete_many(self, con, ids):
        marks = ",".join("?" * len(ids))
        self.run(con, f"DELETE FROM messages WHERE id IN ({marks})", ids)
        self.commit(con)

    def count(self, con):
        return self.run(con, "SELECT COUNT(*) FROM messages").fetchone()[0]

    def commit(self, con):
        con.commit()

    def close(self, con):
        con.close()


class SQLiteDB(SQLDB):
    name = "SQLite"
    tuned = False

    def __init__(self):
        self.path = DATA_DIR / "bench.sqlite"


class SQLiteTunedDB(SQLiteDB):
    name = "SQLite（调优）"
    tuned = True

    def __init__(self):
        self.path = DATA_DIR / "bench-tuned.sqlite"

    def connect(self):
        import sqlite3

        con = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=30000")
        if self.tuned:
            # 默认页缓存只有 2 MB：百万行的库随机读几乎次次落到文件读，macOS 上尤其慢。
            # 生产配置：内存映射 256 MB + 缓存 64 MB + 临时表放内存
            con.execute("PRAGMA mmap_size=268435456")
            con.execute("PRAGMA cache_size=-65536")
            con.execute("PRAGMA temp_store=MEMORY")
        return con

    def reset(self):
        for suffix in ("", "-wal", "-shm"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
        con = self.connect()
        for stmt in self.schema():
            con.execute(stmt)
        return con

    def insert_messages(self, con, rows):  # 自动提交模式下，批量要显式包一个事务
        con.execute("BEGIN")
        con.executemany(f"INSERT INTO messages ({MSG_COLS}) VALUES (?,?,?,?,?,?,?,?)", rows)
        con.execute("COMMIT")

    def insert_essays(self, con, rows):
        con.execute("BEGIN")
        con.executemany(f"INSERT INTO essays ({ESSAY_COLS}) VALUES (?,?,?,?,?,?,?,?)", rows)
        con.execute("COMMIT")

    def commit(self, con):
        pass  # 自动提交：每条语句本身就是一个事务

    def disk_bytes(self, con):
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return sum(Path(f"{self.path}{s}").stat().st_size for s in ("", "-wal") if Path(f"{self.path}{s}").exists())


class DuckDBDB(SQLDB):
    name = "DuckDB"
    review_type = "VARCHAR"

    def __init__(self):
        self.path = DATA_DIR / "bench.duckdb"
        self._root = None

    def connect(self):
        import duckdb

        if self._root is None:
            self._root = duckdb.connect(str(self.path))
        return self._root.cursor()  # 同一进程只能有一个 DuckDB 数据库句柄，线程各拿一个游标

    def reset(self):
        if self._root is not None:
            self._root.close()
            self._root = None
        for suffix in ("", ".wal"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
        con = self.connect()
        for stmt in self.schema():
            con.execute(stmt)
        return con

    def insert_messages(self, con, rows):  # DuckDB 官方不推荐 executemany 批量写；惯用做法是从 DataFrame 导入
        import pandas as pd

        frame = pd.DataFrame(rows, columns=[c.strip() for c in MSG_COLS.split(",")])  # noqa: F841
        con.execute("INSERT INTO messages SELECT * FROM frame")

    def insert_essays(self, con, rows):
        import pandas as pd

        frame = pd.DataFrame(rows, columns=[c.strip() for c in ESSAY_COLS.split(",")])  # noqa: F841
        con.execute("INSERT INTO essays SELECT * FROM frame")

    def commit(self, con):
        pass  # DuckDB 默认自动提交

    def close(self, con):
        con.close()

    def disk_bytes(self, con):
        con.execute("CHECKPOINT")
        return sum(Path(f"{self.path}{s}").stat().st_size for s in ("", ".wal") if Path(f"{self.path}{s}").exists())


class PostgresDB(SQLDB):
    name = "PostgreSQL"
    ph = "%s"
    review_type = "JSONB"

    def connect(self):
        import psycopg

        # 和其他库一样自动提交：并发读不该挂着一个打开的事务
        return psycopg.connect(os.getenv("PG_DSN", "postgresql://bench:bench@127.0.0.1:55432/bench"), autocommit=True)

    def insert_messages(self, con, rows):
        with con.transaction():
            con.cursor().executemany(f"INSERT INTO messages ({MSG_COLS}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", rows)

    def insert_essays(self, con, rows):
        with con.transaction():
            con.cursor().executemany(f"INSERT INTO essays ({ESSAY_COLS}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", rows)

    def reset(self):
        con = self.connect()
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS messages; DROP TABLE IF EXISTS essays")
        for stmt in self.schema():
            cur.execute(stmt)
        con.commit()
        return con

    def update_many(self, con, ids, v):
        self.run(con, "UPDATE messages SET score = %s WHERE id = ANY(%s)", (v, list(ids)))
        con.commit()

    def delete_many(self, con, ids):
        self.run(con, "DELETE FROM messages WHERE id = ANY(%s)", (list(ids),))
        con.commit()

    def disk_bytes(self, con):
        return self.run(con, "SELECT pg_database_size(current_database())").fetchone()[0]


class MySQLDB(SQLDB):
    name = "MySQL"
    ph = "%s"
    review_type = "JSON"

    def schema(self):
        return [s.replace("content TEXT", "content TEXT").replace("DOUBLE PRECISION", "DOUBLE") for s in super().schema()]

    def connect(self):
        import mysql.connector

        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "53306")),
            user="root", password="bench", database="bench", use_pure=False, charset="utf8mb4",
            autocommit=True,
        )

    def reset(self):
        con = self.connect()
        cur = con.cursor()
        cur.execute("DROP TABLE IF EXISTS messages")
        cur.execute("DROP TABLE IF EXISTS essays")
        for stmt in self.schema():
            cur.execute(stmt)
        con.commit()
        return con

    def run(self, con, sql, params=()):
        cur = con.cursor(buffered=True)
        cur.execute(self.q(sql), params)
        return cur

    def disk_bytes(self, con):
        self.run(con, "ANALYZE TABLE messages, essays")
        return int(self.run(con, "SELECT SUM(data_length + index_length) FROM information_schema.tables "
                                 "WHERE table_schema = 'bench'").fetchone()[0])


class MongoDB:
    name = "MongoDB"
    bulk_batch = 5000

    _client = None

    def connect(self):
        from pymongo import MongoClient

        if MongoDB._client is None:
            MongoDB._client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:57017"), maxPoolSize=128)
        return MongoDB._client["bench"]

    def reset(self):
        db = self.connect()
        db.messages.drop()
        db.essays.drop()
        db.messages.create_index([("student_id", 1), ("created_at", -1)])
        db.messages.create_index("class_id")
        db.essays.create_index([("student_id", 1), ("created_at", -1)])
        return db

    @staticmethod
    def _msg(row):
        keys = ("_id", "student_id", "class_id", "conv_id", "role", "content", "score", "created_at")
        return dict(zip(keys, row))

    def insert_messages(self, db, rows):
        db.messages.insert_many([self._msg(r) for r in rows], ordered=False)

    def insert_essays(self, db, rows):
        keys = ("_id", "student_id", "class_id", "topic", "body", "review", "score", "created_at")
        docs = [dict(zip(keys, r)) for r in rows]
        for doc in docs:
            doc["review"] = json.loads(doc["review"])  # 文档库直接存嵌套对象
        db.essays.insert_many(docs, ordered=False)

    def insert_one(self, db, row):
        db.messages.insert_one(self._msg(row))

    def get(self, db, i):
        return db.messages.find_one({"_id": i})

    def recent(self, db, student):
        return list(db.messages.find({"student_id": student}).sort("created_at", -1).limit(20))

    def class_avg(self, db):
        return list(db.messages.aggregate([{"$match": {"score": {"$ne": None}}},
                                           {"$group": {"_id": "$class_id", "avg": {"$avg": "$score"}}}]))

    def search(self, db, kw):
        return list(db.messages.find({"content": {"$regex": kw}}, {"_id": 1}).limit(20))

    def get_essay(self, db, i):
        return db.essays.find_one({"_id": i})["review"]

    def update_one(self, db, i, v):
        db.messages.update_one({"_id": i}, {"$set": {"score": v}})

    def update_many(self, db, ids, v):
        db.messages.update_many({"_id": {"$in": list(ids)}}, {"$set": {"score": v}})

    def delete_one(self, db, i):
        db.messages.delete_one({"_id": i})

    def delete_many(self, db, ids):
        db.messages.delete_many({"_id": {"$in": list(ids)}})

    def count(self, db):
        return db.messages.count_documents({})

    def disk_bytes(self, db):
        stats = db.command("dbStats")
        return int(stats.get("storageSize", 0) + stats.get("indexSize", 0))

    def close(self, db):
        pass  # MongoClient 自带连接池，线程共享同一个客户端是官方推荐用法


class SurrealDB:
    name = "SurrealDB"
    bulk_batch = 1000

    def connect(self):
        from surrealdb import Surreal

        db = Surreal(os.getenv("SURREAL_URL", "ws://127.0.0.1:58000/rpc"))
        db.signin({"username": "root", "password": "root"})
        db.use("bench", "bench")
        return db

    def reset(self):
        db = self.connect()
        db.query("REMOVE TABLE IF EXISTS messages; REMOVE TABLE IF EXISTS essays;")
        db.query("DEFINE TABLE messages SCHEMALESS; DEFINE TABLE essays SCHEMALESS;"
                 "DEFINE INDEX idx_msg_student ON messages FIELDS student_id, created_at;"
                 "DEFINE INDEX idx_msg_class ON messages FIELDS class_id;"
                 "DEFINE INDEX idx_essay_student ON essays FIELDS student_id, created_at;")
        return db

    @staticmethod
    def _msg(row):
        keys = ("id", "student_id", "class_id", "conv_id", "role", "content", "score", "created_at")
        doc = dict(zip(keys, row))
        if doc["score"] is None:
            del doc["score"]
        return doc

    def insert_messages(self, db, rows):
        db.query("INSERT INTO messages $rows", {"rows": [self._msg(r) for r in rows]})

    def insert_essays(self, db, rows):
        keys = ("id", "student_id", "class_id", "topic", "body", "review", "score", "created_at")
        docs = [dict(zip(keys, r)) for r in rows]
        for doc in docs:
            doc["review"] = json.loads(doc["review"])
        db.query("INSERT INTO essays $rows", {"rows": docs})

    def insert_one(self, db, row):
        db.query("INSERT INTO messages $row", {"row": self._msg(row)})

    def get(self, db, i):
        return db.query("SELECT * FROM type::thing('messages', $i)", {"i": i})

    def recent(self, db, student):
        return db.query("SELECT * FROM messages WHERE student_id = $s ORDER BY created_at DESC LIMIT 20", {"s": student})

    def class_avg(self, db):
        return db.query("SELECT class_id, math::mean(score) AS avg FROM messages WHERE score != NONE GROUP BY class_id")

    def search(self, db, kw):
        return db.query("SELECT id FROM messages WHERE string::contains(content, $kw) LIMIT 20", {"kw": kw})

    def get_essay(self, db, i):
        return db.query("SELECT review FROM type::thing('essays', $i)", {"i": i})

    def update_one(self, db, i, v):
        db.query("UPDATE type::thing('messages', $i) SET score = $v", {"i": i, "v": v})

    def update_many(self, db, ids, v):
        db.query("FOR $i IN $ids { UPDATE type::thing('messages', $i) SET score = $v; };", {"ids": list(ids), "v": v})

    def delete_one(self, db, i):
        db.query("DELETE type::thing('messages', $i)", {"i": i})

    def delete_many(self, db, ids):
        db.query("FOR $i IN $ids { DELETE type::thing('messages', $i); };", {"ids": list(ids)})

    def count(self, db):
        rows = db.query("SELECT count() FROM messages GROUP ALL")
        return rows[0]["count"] if rows else 0

    def disk_bytes(self, db):
        return None  # 由外部用 du 量容器里的数据目录

    def close(self, db):
        db.close()


class SQLiteLockedDB(SQLiteTunedDB):
    """调优 + 应用内写锁：写操作在进程里排队，而不是让线程在 SQLite 的忙等待里抢锁。

    SQLite 同一时刻只允许一个写者；抢不到锁的线程由 busy handler 按毫秒级睡眠重试，
    线程一多吞吐就掉、延迟出尖峰。basic-agent 是单进程多线程，用一把 threading.Lock
    让写入排队即可，读不受影响（WAL 下读写互不阻塞）。
    """

    name = "SQLite（调优+写锁）"
    _write_lock = threading.Lock()

    def _locked(method):  # noqa: N805
        def wrapper(self, *args, **kwargs):
            with SQLiteLockedDB._write_lock:
                return method(self, *args, **kwargs)
        return wrapper

    insert_one = _locked(SQLiteTunedDB.insert_one)
    update_one = _locked(SQLiteTunedDB.update_one)
    delete_one = _locked(SQLiteTunedDB.delete_one)
    insert_messages = _locked(SQLiteTunedDB.insert_messages)
    insert_essays = _locked(SQLiteTunedDB.insert_essays)
    update_many = _locked(SQLiteTunedDB.update_many)
    delete_many = _locked(SQLiteTunedDB.delete_many)


DBS = {"sqlite": SQLiteDB, "sqlite-tuned": SQLiteTunedDB, "sqlite-locked": SQLiteLockedDB, "duckdb": DuckDBDB, "postgres": PostgresDB, "mysql": MySQLDB,
       "mongo": MongoDB, "surreal": SurrealDB}


# ====================== 计时 ======================
def pct(values, p):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


def per_op(fn, args_list):
    """逐条计时：给出吞吐和延迟分位数（毫秒）。"""
    latencies = []
    started = time.perf_counter()
    for args in args_list:
        t = time.perf_counter()
        fn(*args)
        latencies.append((time.perf_counter() - t) * 1000)
    total = time.perf_counter() - started
    return {"ops": len(args_list), "seconds": round(total, 3), "ops_per_s": round(len(args_list) / total, 1),
            "p50_ms": round(pct(latencies, 50), 3), "p95_ms": round(pct(latencies, 95), 3),
            "p99_ms": round(pct(latencies, 99), 3)}


def mixed(db, threads: int, seconds: float, n: int, essays: int, id_base: int):
    """并发混合负载：70% 查某个学生最近 20 条、15% 新增、10% 改分、5% 读一篇作文。每线程一个连接。"""
    stop = time.perf_counter() + seconds
    lock = threading.Lock()
    stats = {"ops": 0, "errors": 0, "lat": [], "error_samples": []}

    def worker(k):
        rng = random.Random(1000 + k)
        con = db.connect()
        next_id = id_base + k * 10_000_000
        local, lat, errors, samples = 0, [], 0, []
        try:
            while time.perf_counter() < stop:
                r = rng.random()
                t = time.perf_counter()
                try:
                    if r < 0.70:
                        db.recent(con, rng.randrange(STUDENTS))
                    elif r < 0.85:
                        next_id += 1
                        db.insert_one(con, message_row(rng, next_id))
                    elif r < 0.95:
                        db.update_one(con, rng.randrange(1, n // 2), round(rng.uniform(0, 100), 1))
                    else:
                        db.get_essay(con, rng.randrange(1, essays + 1))
                    lat.append((time.perf_counter() - t) * 1000)
                    local += 1
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    if len(samples) < 3:
                        samples.append(f"{type(exc).__name__}: {str(exc)[:120]}")
        finally:
            try:
                db.close(con)
            except Exception:  # noqa: BLE001
                pass
        with lock:
            stats["ops"] += local
            stats["errors"] += errors
            stats["lat"].extend(lat)
            stats["error_samples"].extend(samples)

    pool = [threading.Thread(target=worker, args=(k,)) for k in range(threads)]
    started = time.perf_counter()
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    total = time.perf_counter() - started
    return {"threads": threads, "seconds": round(total, 2), "ops": stats["ops"],
            "ops_per_s": round(stats["ops"] / total, 1), "errors": stats["errors"],
            "error_samples": stats["error_samples"][:3],
            "p50_ms": round(pct(stats["lat"], 50) or 0, 3), "p95_ms": round(pct(stats["lat"], 95) or 0, 3),
            "p99_ms": round(pct(stats["lat"], 99) or 0, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("db", choices=sorted(DBS))
    parser.add_argument("--out", required=True)
    parser.add_argument("--n", type=int, default=1_000_000)
    parser.add_argument("--essays", type=int, default=20_000)
    parser.add_argument("--single", type=int, default=5_000)
    parser.add_argument("--threads", default="8,32,64")
    parser.add_argument("--mixed-seconds", type=float, default=10)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = DBS[args.db]()
    rng = random.Random(42)
    result = {"db": db.name, "label": args.label, "n": args.n, "essays": args.essays, "phases": {}}
    phases = result["phases"]

    def log(name, value):
        phases[name] = value
        print(f"[{db.name}{' ' + args.label if args.label else ''}] {name}: {json.dumps(value, ensure_ascii=False)}", flush=True)

    t = time.perf_counter()
    con = db.reset()
    log("reset_schema_s", round(time.perf_counter() - t, 3))

    # 1. 批量写入
    batch = getattr(db, "bulk_batch", 5000)
    t = time.perf_counter()
    for rows in batches(args.n, batch):
        db.insert_messages(con, rows)
    secs = time.perf_counter() - t
    log("bulk_insert_messages", {"rows": args.n, "batch": batch, "seconds": round(secs, 2), "rows_per_s": round(args.n / secs)})

    t = time.perf_counter()
    for rows in batches(args.essays, 500, seed=8, maker=essay_row):
        db.insert_essays(con, rows)
    secs = time.perf_counter() - t
    log("bulk_insert_essays", {"rows": args.essays, "seconds": round(secs, 2), "rows_per_s": round(args.essays / secs)})

    # 2. 单条写（每条一个事务，模拟学生一条条发消息）
    single_rng = random.Random(9)
    base = args.n + 1
    log("insert_single", per_op(lambda r: db.insert_one(con, r), [(message_row(single_rng, base + i),) for i in range(args.single)]))

    # 3. 读
    ids = [rng.randrange(1, args.n + 1) for _ in range(20_000)]
    log("point_read", per_op(lambda i: db.get(con, i), [(i,) for i in ids]))
    log("recent_by_student", per_op(lambda s: db.recent(con, s), [(rng.randrange(STUDENTS),) for _ in range(5_000)]))
    log("class_avg_aggregate", per_op(lambda: db.class_avg(con), [()] * 5))
    log("like_search_scan", per_op(lambda: db.search(con, "活动周期图，队列长度"), [()] * 5))
    log("essay_read_json", per_op(lambda i: db.get_essay(con, i), [(rng.randrange(1, args.essays + 1),) for _ in range(5_000)]))

    # 4. 改
    log("update_single", per_op(lambda i: db.update_one(con, i, 88.8), [(rng.randrange(1, args.n + 1),) for _ in range(args.single)]))
    bulk = min(100_000, args.n // 10)
    upd = rng.sample(range(1, args.n + 1), bulk)
    t = time.perf_counter()
    for k in range(0, len(upd), 1000):
        db.update_many(con, upd[k:k + 1000], 66.6)
    secs = time.perf_counter() - t
    log("update_bulk", {"rows": len(upd), "batch": 1000, "seconds": round(secs, 2), "rows_per_s": round(len(upd) / secs)})

    # 5. 删
    pool = list(range(args.n // 2 + 1, args.n + 1))
    rng.shuffle(pool)
    single_del, bulk_del = pool[: args.single], pool[args.single: args.single + bulk]
    log("delete_single", per_op(lambda i: db.delete_one(con, i), [(i,) for i in single_del]))
    t = time.perf_counter()
    for k in range(0, len(bulk_del), 1000):
        db.delete_many(con, bulk_del[k:k + 1000])
    secs = time.perf_counter() - t
    log("delete_bulk", {"rows": len(bulk_del), "batch": 1000, "seconds": round(secs, 2), "rows_per_s": round(len(bulk_del) / secs)})

    # 6. 数据是否对得上：总数 = n + 单条写入 - 删掉的
    expected = args.n + args.single - len(single_del) - len(bulk_del)
    got = db.count(con)
    log("count_check", {"expected": expected, "got": got, "ok": expected == got})

    size = db.disk_bytes(con)
    if size is not None:
        log("disk_mb", round(size / 1e6, 1))

    # 7. 并发混合负载
    for threads in [int(x) for x in args.threads.split(",") if x]:
        log(f"mixed_{threads}_threads", mixed(db, threads, args.mixed_seconds, args.n, args.essays, 50_000_000 + threads * 1_000_000_000))

    db.close(con)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {args.out}", flush=True)


if __name__ == "__main__":
    sys.setrecursionlimit(10_000)
    main()
