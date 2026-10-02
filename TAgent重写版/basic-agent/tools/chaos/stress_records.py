"""学习记录在极端情况下对不对：连点、刷新、一个班同时用，记录不多不少、不串人、不拖慢请求。

先按 stress.py 的说明起好 fake_upstream 与 chaos_server（chaos_server 要带上 TAGENT_DB_PATH 指向一个新库），然后：

    .venv/bin/python -m tools.chaos.stress_records <库文件路径>
"""
import json
import socket
import sqlite3
import sys
import threading
import time
import urllib.request
from urllib.parse import quote

from tools.chaos.stress import BASE, PAPER, TOPIC, control, stats, wait_idle

DB = sys.argv[1] if len(sys.argv) > 1 else ""


def who(n: int, name: str = "") -> dict:
    headers = {"X-Tagent-Client-Id": f"dev_stress_{n:04d}"}
    if name:
        headers["X-Tagent-Client-Name"] = quote(name)
    return headers


def post(path, payload, headers, timeout=120):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            return resp.status, time.time() - started
    except urllib.error.HTTPError as err:
        return err.code, time.time() - started


def stream(headers, question="到达率是什么？"):
    body = {"model": "deepseek", "stream": True, "mode": "qa", "messages": [{"role": "user", "content": question}]}
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    started, first = time.time(), None
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            if first is None and line.startswith(b"data:"):
                first = time.time() - started
    return first, time.time() - started


def abandon_stream(headers, after):
    body = json.dumps({"model": "deepseek", "stream": True, "mode": "qa",
                       "messages": [{"role": "user", "content": "刷新测试"}]}).encode()
    extra = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    sock = socket.create_connection(("127.0.0.1", 5001))
    sock.sendall((f"POST /v1/chat/completions HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n{extra}"
                  f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body)
    time.sleep(after)
    sock.close()


def together(fn, args_list):
    out = [None] * len(args_list)

    def run(i, args):
        out[i] = fn(*args)

    threads = [threading.Thread(target=run, args=(i, a)) for i, a in enumerate(args_list)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def q(sql, *args):
    conn = sqlite3.connect(DB)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def r1_class_streams(n=30):
    control(token_delay=0.03, mode="ok", reset=1)
    before = q("SELECT COUNT(*) FROM chat_turns")[0][0]
    results = together(stream, [(who(i, f"学生{i}"),) for i in range(n)])
    time.sleep(0.5)
    rows = q("SELECT COUNT(*), COUNT(DISTINCT student_id), SUM(finish_reason = 'stop') FROM chat_turns")[0]
    firsts = sorted(round(f, 2) for f, _ in results)
    print(f"R1 {n} 人同时流式提问（都带编号）: 首字 最快 {firsts[0]}s 最慢 {firsts[-1]}s；"
          f"新增记录 {rows[0] - before} 条（应为 {n}），涉及学生 {rows[1]} 人，答完的 {rows[2]} 条")


def r2_refresh_storm(n=20):
    control(token_delay=0.05, mode="ok", reset=1)
    before = q("SELECT COUNT(*) FROM chat_turns WHERE finish_reason = 'interrupted'")[0][0]
    for i in range(n):
        abandon_stream(who(1000), after=0.3)
    wait_idle(30)
    time.sleep(1)
    after = q("SELECT COUNT(*) FROM chat_turns WHERE finish_reason = 'interrupted'")[0][0]
    integrity = q("PRAGMA integrity_check")[0][0]
    print(f"R2 同一学生流式回答中连续刷新 {n} 次: 记成「没答完」的新增 {after - before} 条（应为 {n}），"
          f"上游还在吐字的 {stats()['active']} 路，库完整性 {integrity}")


def r3_spam_submit(n=10):
    control(delay=1.0, mode="ok", reset=1)
    tag = f"R3-{time.time()}"
    payload = {"model": "deepseek", "text": PAPER + f"\n（{tag}）", "topic": TOPIC}
    results = together(post, [("/essay/review", payload, who(2000))] * n)
    wait_idle()
    rows = q("SELECT COUNT(*) FROM essay_reviews WHERE text LIKE ?", f"%{tag}%")[0][0]
    codes = sorted({code for code, _ in results})
    print(f"R3 同一学生连点交稿 {n} 次: 状态 {codes}，上游调用 {stats()['calls']}（一次批改是 4），记录 {rows} 条（应为 1）")


def r4_same_sample(n=2):
    control(delay=1.0, mode="ok", reset=1)
    tag = f"R4-{time.time()}"
    payload = {"model": "deepseek", "text": PAPER + f"\n（{tag}）", "topic": TOPIC}
    for i in range(n):  # 一个接一个交（不撞闸门），模拟两人先后用同一篇范例
        post("/essay/review", payload, who(3000 + i))
    rows = q("SELECT COUNT(DISTINCT student_id) FROM essay_reviews WHERE text LIKE ?", f"%{tag}%")[0][0]
    print(f"R4 {n} 个学生先后交同一篇范例（90 秒内）: 记到了 {rows} 个人（应为 {n}）")


def r5_private(n=5):
    control(token_delay=0.01, mode="ok", reset=1)
    before = q("SELECT COUNT(*) FROM chat_turns")[0][0]
    together(stream, [({**who(4000), "X-Tagent-No-Record": "1"},) for _ in range(n)])
    time.sleep(0.5)
    after = q("SELECT COUNT(*) FROM chat_turns")[0][0]
    print(f"R5 临时对话里连问 {n} 次: 新增记录 {after - before} 条（应为 0）")


def r6_record_overhead(n=40):
    control(token_delay=0.0, delay=0.0, mode="ok", reset=1)
    body = {"model": "deepseek", "stream": False, "mode": "qa", "messages": [{"role": "user", "content": "延迟测试"}]}

    def timed(headers):
        times = []
        for _ in range(n):
            _code, elapsed = post("/v1/chat/completions", body, headers)
            times.append(elapsed * 1000)
        times.sort()
        return times[len(times) // 2], times[int(len(times) * 0.95)]

    on = timed(who(5000))
    off = timed({**who(5000), "X-Tagent-No-Record": "1"})
    print(f"R6 记录本身的开销（非流式，{n} 次）: 记录时 中位 {on[0]:.1f}ms / p95 {on[1]:.1f}ms；"
          f"不记录 中位 {off[0]:.1f}ms / p95 {off[1]:.1f}ms")


if __name__ == "__main__":
    if not DB:
        raise SystemExit("用法：python -m tools.chaos.stress_records <chaos_server 用的 TAGENT_DB_PATH>")
    r1_class_streams()
    r2_refresh_storm()
    r3_spam_submit()
    r4_same_sample()
    r5_private()
    r6_record_overhead()
