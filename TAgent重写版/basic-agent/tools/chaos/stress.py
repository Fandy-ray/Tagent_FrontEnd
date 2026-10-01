"""极端场景压测：连点、刷新、断网、上游故障、一个班同时提问。输出可前后对比的数字。

在 basic-agent/ 目录下开三个终端（5001 要空着，别和正式的 basic-agent 同时跑）：

    .venv/bin/python -m tools.chaos.fake_upstream   # 假上游 9100：可控延迟 / 故障，零 token 成本
    .venv/bin/python -m tools.chaos.chaos_server    # 真实后端栈（路由、闸门、service、HTTP 客户端）+ 假上游，占 5001
    .venv/bin/python -m tools.chaos.stress          # S1~S5；再单独跑 s7（一个班同时提问）

s6（上游卡死）会把两个闸门名额各占住约 90 秒，跑完要重启上面两个服务。
chaos_server 占着 5001 时前端（npm run dev）也能直接连上，可以在浏览器里手动试连点、刷新、断网。

结果与结论记在 TAgent重写版/文档/极端场景压测与稳定性升级.md。
"""
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

BASE, UP = "http://127.0.0.1:5001", "http://127.0.0.1:9100"
PAPER = (
    "排队论研究随机到达与随机服务的系统，是系统仿真课程的核心内容之一。它用到达率和服务率刻画拥挤程度。\n"
    "以银行网点为例，顾客的到达可以近似看成泊松过程，柜员的服务时间可以近似看成指数分布。于是可以用 M/M/c 模型来描述。\n"
    "我觉得窗口越多越好，因为顾客的时间很宝贵。其实排队论算出来的结果大家都知道。\n"
    "不过模型也有局限。现实中顾客到达并不是完全随机的，中午和下班后会出现高峰。可以用仿真的方法分时段估计到达率。\n"
    "总之，排队论为窗口设置提供了定量依据，但使用时要检验模型假设。"
)
TOPIC = "排队论模型在银行窗口设置中的应用"


def control(**params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return json.load(urllib.request.urlopen(f"{UP}/control?{query}"))


def stats():
    return json.load(urllib.request.urlopen(f"{UP}/stats"))


def post(path, payload, timeout=120):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, time.time() - started, json.load(resp)
    except urllib.error.HTTPError as err:
        return err.code, time.time() - started, json.loads(err.read() or b"{}")
    except Exception as err:  # noqa: BLE001
        return f"EXC:{type(err).__name__}", time.time() - started, {}


def abandon(path, payload, after):
    """模拟刷新 / 关页：发完请求，过 after 秒直接断开连接，不读响应。"""
    body = json.dumps(payload).encode()
    sock = socket.create_connection(("127.0.0.1", 5001))
    head = (f"POST {path} HTTP/1.1\r\nHost: 127.0.0.1:5001\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode()
    sock.sendall(head + body)
    time.sleep(after)
    sock.close()


def wait_idle(limit=60):
    end = time.time() + limit
    while time.time() < end and stats()["active"] > 0:
        time.sleep(0.2)


def review_payload(text=PAPER, tag=""):
    # tag 让每个场景交的是不同的作文：否则后一个场景会直接拿到前一个场景 90 秒内的重放结果
    return {"model": "deepseek", "text": text + (f"\n（{tag}）" if tag else ""), "topic": TOPIC}


def fire_parallel(jobs, gap=0.0):
    results = [None] * len(jobs)

    def run(i, job):
        results[i] = post(*job)

    threads = []
    for i, job in enumerate(jobs):
        t = threading.Thread(target=run, args=(i, job))
        t.start()
        threads.append(t)
        time.sleep(gap)
    for t in threads:
        t.join()
    return results


def summarize(results):
    codes = {}
    for code, _elapsed, _body in results:
        codes[code] = codes.get(code, 0) + 1
    slowest = max(r[1] for r in results)
    return codes, round(slowest, 2)


def s1_spam_same(delay):
    control(delay=delay, mode="ok", reset=1)
    results = fire_parallel([("/essay/review", review_payload())] * 5, gap=0.08)
    wait_idle()
    codes, slowest = summarize(results)
    scores = sorted({r[2].get("data", {}).get("score") for r in results if r[0] == 200})
    print(f"S1 连点同一篇（5 次，间隔 80ms）: 状态 {codes}，最慢 {slowest}s，上游调用 {stats()['calls']}，成功的分数 {scores}")


def s2_burst_distinct(delay):
    control(delay=delay, mode="ok", reset=1)
    jobs = [("/essay/review", review_payload(PAPER + f"\n第{i}位同学补充了一段新的论证，说明模型假设的适用范围。")) for i in range(6)]
    results = fire_parallel(jobs)
    wait_idle()
    codes, slowest = summarize(results)
    rejects = [round(r[1] * 1000) for r in results if r[0] == 429]
    print(f"S2 六位同学同时交稿: 状态 {codes}，429 响应耗时(ms) {rejects}，上游调用 {stats()['calls']}，最大上游并发 {stats()['max_active']}")


def s3_refresh_storm(delay):
    control(delay=delay, mode="ok", reset=1)
    tag = f"S3-{time.time()}"
    started = time.time()
    for _ in range(5):
        abandon("/essay/review", review_payload(tag=tag), after=0.4)
    code, elapsed, body = post("/essay/review", review_payload(tag=tag))
    first_ok = elapsed
    retries = 0
    while code == 429 and time.time() - started < 60:
        retries += 1
        time.sleep(1)
        code, elapsed, body = post("/essay/review", review_payload(tag=tag))
    total = time.time() - started
    wait_idle()
    print(f"S3 批改中刷新 5 次再重交: 第一次重交状态 {'429' if retries else code}（{first_ok:.2f}s），"
          f"之后每秒重试 {retries} 次才成功，从开始到拿到结果共 {total:.1f}s，上游调用 {stats()['calls']}（正常一次批改是 4）")


def s4_refresh_stream():
    control(token_delay=0.05, mode="ok", reset=1)
    body = json.dumps({"model": "deepseek", "stream": True, "mode": "qa",
                       "messages": [{"role": "user", "content": "到达率是什么？"}]}).encode()
    sock = socket.create_connection(("127.0.0.1", 5001))
    sock.sendall((f"POST /v1/chat/completions HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                  f"Content-Length: {len(body)}\r\n\r\n").encode() + body)
    sock.recv(2048)
    time.sleep(0.5)
    sock.close()
    before = stats()
    time.sleep(3)
    after = stats()
    print(f"S4 流式回答中刷新: 断开时上游还有 {before['active']} 路在吐字，3 秒后 {after['active']} 路；上游完整吐完的 {after['completed']} 路")


def s5_upstream_error():
    control(mode="error", reset=1)
    code, elapsed, body = post("/essay/review", review_payload(tag=f"S5-{time.time()}"))
    message = (body.get("error") or {}).get("message") or body.get("msg")
    print(f"S5 上游报 500: 状态 {code}，{elapsed:.2f}s 返回，上游被调 {stats()['calls']} 次，提示「{message}」")
    control(mode="ok")


def s6_upstream_hang(patience):
    control(mode="hang", reset=1)
    code, elapsed, _ = post("/essay/review", review_payload(), timeout=patience)
    print(f"S6 上游卡死（断网但不报错）: 等了 {elapsed:.0f}s 仍无结果 → {code}")
    code2, _, _ = post("/essay/review", review_payload(PAPER + "另一位同学"), timeout=5)
    print(f"    同时另一位同学交稿: {code2}")


if __name__ == "__main__" and sys.argv[1:] != ["s7"]:
    which = sys.argv[1:] or ["s1", "s2", "s3", "s4", "s5"]
    delay = 2.0
    for name in which:
        if name == "s6":
            s6_upstream_hang(20)
        else:
            {"s1": lambda: s1_spam_same(delay), "s2": lambda: s2_burst_distinct(delay),
             "s3": lambda: s3_refresh_storm(delay), "s4": s4_refresh_stream, "s5": s5_upstream_error}[name]()


def s7_class_streams(n=12):
    """一个班同时提问：n 路流式回答并发，同时探一下 /health 和一次普通批改要等多久。"""
    control(token_delay=0.05, mode="ok", reset=1)
    body = json.dumps({"model": "deepseek", "stream": True, "mode": "qa",
                       "messages": [{"role": "user", "content": "到达率是什么？"}]}).encode()
    done = []

    def stream():
        started = time.time()
        req = urllib.request.Request(BASE + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            first = None
            for line in resp:
                if first is None and line.startswith(b"data:"):
                    first = time.time() - started
        done.append((first, time.time() - started))

    threads = [threading.Thread(target=stream) for _ in range(n)]
    for t in threads:
        t.start()
    time.sleep(0.5)
    started = time.time()
    urllib.request.urlopen(BASE + "/health", timeout=120).read()
    health = time.time() - started
    for t in threads:
        t.join()
    firsts = sorted(round(f, 1) for f, _ in done)
    print(f"S7 {n} 人同时流式提问: /health 等了 {health:.2f}s；首字延迟(s) 最快 {firsts[0]} 最慢 {firsts[-1]}；"
          f"全部答完 {max(t for _, t in done):.1f}s")


if __name__ == "__main__" and sys.argv[1:] == ["s7"]:
    s7_class_streams()
