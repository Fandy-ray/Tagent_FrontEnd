"""持久化 / 崩溃恢复测试：已经确认写入的数据，崩溃重启后必须一条不少；成批事务不能只进去半批。

写入进程每成功提交一次，就把编号追加到确认清单（写进内核缓冲，进程被杀也不丢）。
  嵌入式库（SQLite / DuckDB）：kill -9 写入进程本身 —— 模拟应用崩溃
  服务端库：kill -9 数据库服务所在容器 —— 模拟数据库崩溃，然后重启、计时、核对

用法：python crash.py <db> [--container NAME] [--mode single|batch] [--seconds 3]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402

START = {"single": 900_000_000, "batch": 950_000_000}
BATCH = 5000


def child(db_name: str, mode: str, ack_path: str):
    db = bench.DBS[db_name]()
    con = db.connect()
    rng = random.Random(123)
    fd = os.open(ack_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    next_id = START[mode]
    while True:
        if mode == "single":
            db.insert_one(con, bench.message_row(rng, next_id))
            os.write(fd, f"{next_id}\n".encode())
            next_id += 1
        else:
            rows = [bench.message_row(rng, next_id + k) for k in range(BATCH)]
            db.insert_messages(con, rows)
            os.write(fd, f"{next_id}:{next_id + BATCH - 1}\n".encode())
            next_id += BATCH


def stored_ids(db, con, lo: int, hi: int) -> set[int]:
    if isinstance(db, bench.MongoDB):
        return {d["_id"] for d in con.messages.find({"_id": {"$gte": lo, "$lt": hi}}, {"_id": 1})}
    if isinstance(db, bench.SurrealDB):
        rows = con.query(f"SELECT VALUE record::id(id) FROM messages:{int(lo)}..{int(hi)}")
        return {int(r) for r in rows}
    return {r[0] for r in db.run(con, "SELECT id FROM messages WHERE id >= ? AND id < ?", (lo, hi)).fetchall()}


def cleanup(db, con, lo: int, hi: int):
    if isinstance(db, bench.MongoDB):
        con.messages.delete_many({"_id": {"$gte": lo, "$lt": hi}})
    elif isinstance(db, bench.SurrealDB):
        con.query(f"DELETE messages:{int(lo)}..{int(hi)}")
    else:
        db.run(con, "DELETE FROM messages WHERE id >= ? AND id < ?", (lo, hi))
        db.commit(con)


def wait_ready(db, deadline_s=180):
    started = time.time()
    while time.time() - started < deadline_s:
        try:
            con = db.connect()
            if isinstance(db, bench.SurrealDB):
                con.query("RETURN 1")
            elif isinstance(db, bench.MongoDB):
                con.command("ping")
            else:
                db.run(con, "SELECT 1").fetchone()
            return con, time.time() - started
        except Exception:  # noqa: BLE001
            if isinstance(db, bench.MongoDB):
                bench.MongoDB._client = None
            time.sleep(0.2)
    raise SystemExit("database did not come back")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("db", choices=sorted(bench.DBS))
    parser.add_argument("--container")
    parser.add_argument("--mode", default="single", choices=["single", "batch"])
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--ack")
    parser.add_argument("--out")
    args = parser.parse_args()

    if args.child:
        child(args.db, args.mode, args.ack)
        return

    db = bench.DBS[args.db]()
    lo, hi = START[args.mode], START[args.mode] + 40_000_000
    con = db.connect()
    cleanup(db, con, lo, hi)  # 上一轮留下的测试数据
    db.close(con)
    if isinstance(db, bench.DuckDBDB) and db._root is not None:
        db._root.close()  # DuckDB 一个库文件同时只允许一个进程打开
        db._root = None

    ack = Path(os.getenv("DATA_DIR", "./data")) / f"ack-{args.db}-{args.mode}.txt"
    ack.unlink(missing_ok=True)
    proc = subprocess.Popen([sys.executable, __file__, args.db, "--child", "--mode", args.mode, "--ack", str(ack)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(args.seconds)

    if args.container:  # 服务端：杀数据库，不杀客户端
        subprocess.run(["docker", "kill", "--signal", "KILL", args.container], check=True, capture_output=True)
        killed = "数据库服务 kill -9"
        time.sleep(0.5)
        proc.kill()
        proc.wait()
        subprocess.run(["docker", "start", args.container], check=True, capture_output=True)
    else:  # 嵌入式：数据库就在应用进程里，杀应用进程
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait()
        killed = "写入进程 kill -9"

    con, recovery = wait_ready(db)
    lines = ack.read_text().split()
    if args.mode == "single":
        acked = {int(x) for x in lines}
    else:
        acked = set()
        for span in lines:
            a, b = (int(x) for x in span.split(":"))
            acked.update(range(a, b + 1))
    stored = stored_ids(db, con, lo, hi)
    lost = acked - stored
    result = {"db": db.name, "mode": args.mode, "killed": killed, "acked": len(acked), "stored": len(stored),
              "lost_acked": len(lost), "recovery_s": round(recovery, 2)}
    if args.mode == "batch":
        # 原子性：每批要么全在、要么全不在
        partial = 0
        start = lo
        while start < (max(stored) + 1 if stored else lo):
            got = len({i for i in range(start, start + BATCH)} & stored)
            if 0 < got < BATCH:
                partial += 1
            start += BATCH
        result["partial_batches"] = partial
    if isinstance(db, bench.SQLiteDB):
        result["integrity_check"] = db.run(con, "PRAGMA integrity_check").fetchone()[0]
    result["ok"] = not lost and result.get("partial_batches", 0) == 0
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    cleanup(db, con, lo, hi)
    db.close(con)


if __name__ == "__main__":
    main()
