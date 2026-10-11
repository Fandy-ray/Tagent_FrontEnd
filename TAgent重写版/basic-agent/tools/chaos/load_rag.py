"""一个班同时用的压测：真实检索（教材 + 论文 + FAISS + 检索结果缓存）+ 假上游，看系统本身的开销和并发表现。

先按 load_backend.py 的说明起好 fake_upstream（9100）和 load_backend（5011），再在 basic-agent/ 下：

    .venv/bin/python -m tools.chaos.load_rag                 # 全部场景
    .venv/bin/python -m tools.chaos.load_rag sweep same      # 只跑其中几个：sweep / same / soak / essay
    LOAD_TOKEN_DELAY=0.15 LOAD_LEVELS=50 .venv/bin/python -m tools.chaos.load_rag sweep   # 回答拉长到约 17 秒（接近真实模型）
    LOAD_ESSAY_DELAY=7.5 .venv/bin/python -m tools.chaos.load_rag essay                   # 一次批改约 15 秒（接近真实 DeepSeek）

每条流式回答记三个时间：
  出处到达：检索完、收到模型第一块之后单独发的出处帧（假上游立刻回第一块，所以基本就是检索的耗时）
  首字：第一段正文
  答完：收到 [DONE]
假上游默认每个字 20ms（一条回答约 110 字、2.3 秒），LOAD_TOKEN_DELAY 可调；真实模型更慢，答完的时间按比例放大。
持续提问（soak）每个问题都带上序号，互不相同，测的是不命中检索缓存的情况（大家问的大多不一样）。
"""
import json
import math
import os
import random
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = os.getenv("LOAD_BASE", "http://127.0.0.1:5011")
UP = os.getenv("CHAOS_UPSTREAM", "http://127.0.0.1:9100")
OUT = os.getenv("LOAD_OUT", "")
TOKEN_DELAY = float(os.getenv("LOAD_TOKEN_DELAY", "0.02"))
LEVELS = [int(n) for n in os.getenv("LOAD_LEVELS", "1,10,30,50").split(",")]
ESSAY_DELAY = float(os.getenv("LOAD_ESSAY_DELAY", "2.0"))

QUESTIONS = [
    "什么是离散事件系统仿真？", "蒙特卡洛方法的基本思想是什么？", "排队系统由哪几个基本部分组成？",
    "M/M/1 排队模型的平均等待时间怎么算？", "怎样生成服从指数分布的随机数？", "线性同余法的参数应该怎么选？",
    "什么是事件调度法？", "活动扫描法和进程交互法有什么区别？", "仿真时钟有哪两种推进方式？",
    "怎样检验随机数的独立性？", "卡方检验在输入数据分析里怎么用？", "怎样确定仿真的预热期？",
    "终止型仿真和稳态仿真有什么区别？", "怎样给仿真输出估计置信区间？", "方差缩减技术有哪些？",
    "对偶变量法的原理是什么？", "什么是系统动力学？", "库存系统仿真要考虑哪些参数？",
    "Petri 网怎样描述并发？", "连续系统仿真常用哪些数值积分方法？", "欧拉法和龙格-库塔法的精度差在哪里？",
    "怎样对仿真模型做验证与确认？", "Little 公式说的是什么？", "到达率和服务率是什么关系？",
    "怎样用逆变换法生成随机变量？", "舍选法适用于什么情况？", "Arena 软件有哪些基本模块？",
    "仿真实验设计里的析因设计是什么？", "什么是仿真元模型？", "输入数据的分布怎样拟合？",
    "泊松过程有什么性质？", "服务台利用率怎么计算？", "多服务台排队系统怎么建模？",
    "什么是批均值法？", "独立重复运行法怎么做？", "伪随机数和真随机数有什么区别？",
    "离散分布的随机变量怎样生成？", "正态分布随机数有哪些生成方法？", "仿真中的状态变量指什么？",
    "什么是实体、属性和活动？", "事件表是怎样维护的？", "仿真模型的抽象层次怎样选择？",
    "怎样比较两个系统方案的优劣？", "公共随机数法为什么能减小方差？", "敏感性分析在仿真里怎么做？",
    "什么是基于智能体的仿真？", "离散系统和连续系统仿真有什么不同？", "怎样建立银行排队的仿真模型？",
    "生产线仿真关注哪些性能指标？", "仿真软件选型要考虑什么？",
]
# 每档用不同的问法：问题文本不同，检索结果缓存就命中不了，测的是真检索
PHRASINGS = ["{q}", "请解释：{q}", "{q}请结合教材说明。", "课堂提问：{q}", "复习时想确认一下，{q}"]


def control(**params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return json.load(urllib.request.urlopen(f"{UP}/control?{query}"))


def stats():
    return json.load(urllib.request.urlopen(f"{UP}/stats"))


def ask(question, *, timeout=180):
    """发一条流式提问，返回 (状态, 出处到达, 首字, 答完, 出处条数)。"""
    body = json.dumps({"model": "deepseek", "stream": True, "mode": "qa",
                       "messages": [{"role": "user", "content": question}]}).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    cited = first = None
    sources = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.strip()
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    return 200, cited, first, time.perf_counter() - started, sources
                frame = json.loads(data)
                if "citations" in frame and cited is None:
                    cited = time.perf_counter() - started
                    sources = len(frame["citations"])
                delta = (frame.get("choices") or [{}])[0].get("delta") or {}
                if delta.get("content") and first is None:
                    first = time.perf_counter() - started
        return "no-done", cited, first, time.perf_counter() - started, sources
    except urllib.error.HTTPError as err:
        return err.code, cited, first, time.perf_counter() - started, sources
    except Exception as err:  # noqa: BLE001
        return f"EXC:{type(err).__name__}", cited, first, time.perf_counter() - started, sources


def pct(values, p):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    # 最近秩法：第 ceil(p% × n) 个
    index = max(0, math.ceil(p / 100 * len(values)) - 1)
    return round(values[index], 2)


def describe(results):
    codes = {}
    for result in results:
        codes[result[0]] = codes.get(result[0], 0) + 1
    column = lambda i: [r[i] for r in results if r[0] == 200]  # noqa: E731
    return {
        "status": codes,
        "出处到达": {"p50": pct(column(1), 50), "p95": pct(column(1), 95), "max": pct(column(1), 100)},
        "首字": {"p50": pct(column(2), 50), "p95": pct(column(2), 95), "max": pct(column(2), 100)},
        "答完": {"p50": pct(column(3), 50), "p95": pct(column(3), 95), "max": pct(column(3), 100)},
        "出处条数": sorted(set(column(4))),
    }


class Sampler:
    """压测期间每 0.5 秒记一次后端进程的内存和 CPU，顺带探 /health 要等多久。"""

    def __init__(self):
        port = BASE.rsplit(":", 1)[1].split("/")[0]
        out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], capture_output=True, text=True)
        self.pid = (out.stdout.split() or [""])[0]
        self.rss, self.cpu, self.health = [], [], []
        self._stop = threading.Event()

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()

    def _run(self):
        while not self._stop.is_set():
            if self.pid:
                out = subprocess.run(["ps", "-o", "rss=,%cpu=", "-p", self.pid], capture_output=True, text=True)
                parts = out.stdout.split()
                if len(parts) == 2:
                    self.rss.append(int(parts[0]) / 1024)
                    self.cpu.append(float(parts[1]))
            started = time.perf_counter()
            try:
                urllib.request.urlopen(f"{BASE}/health", timeout=30).read()
                self.health.append(time.perf_counter() - started)
            except Exception:  # noqa: BLE001
                self.health.append(None)
            self._stop.wait(0.5)

    def summary(self):
        health = [h for h in self.health if h is not None]
        return {
            "内存MB": {"max": round(max(self.rss), 0) if self.rss else None},
            "CPU%": {"p50": pct(self.cpu, 50), "max": pct(self.cpu, 100)},
            "/health秒": {"p95": pct(health, 95), "max": pct(health, 100), "失败": len(self.health) - len(health)},
        }


def burst(questions):
    results = [None] * len(questions)

    def run(i):
        results[i] = ask(questions[i])

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(questions))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


REPORT = {}


def sweep():
    """不同人数同时提不同的问题（都不命中检索缓存）。"""
    control(token_delay=TOKEN_DELAY, mode="ok", reset=1)
    run = f"{time.time():.0f}"
    for level, n in enumerate(LEVELS):
        # 带上这次运行的编号：前一次运行（或热身）问过的同一句还在 60 秒缓存里，会让这一档测不到真检索
        questions = [PHRASINGS[level % len(PHRASINGS)].format(q=QUESTIONS[i % len(QUESTIONS)]) + f"（{run}）"
                     for i in range(n)]
        with Sampler() as sampler:
            started = time.perf_counter()
            results = burst(questions)
            wall = time.perf_counter() - started
        row = {**describe(results), **sampler.summary(), "全部答完秒": round(wall, 1), "上游最大并发": stats()["max_active"]}
        REPORT[f"sweep_{n}@{TOKEN_DELAY}"] = row
        print(f"[sweep] {n} 人同时提问: {json.dumps(row, ensure_ascii=False)}", flush=True)
        control(reset=1)
        time.sleep(2)


def same():
    """30 人同时问同一个新问题：检索只该做一次（同题合并）；60 秒内再问一遍直接用缓存。"""
    control(token_delay=TOKEN_DELAY, mode="ok", reset=1)
    question = f"同一个问题：排队论里的服务强度为什么必须小于 1？（{time.time():.0f}）"
    first = burst([question] * 30)
    again = burst([question] * 30)
    REPORT["same_first"] = describe(first)
    REPORT["same_again"] = describe(again)
    print(f"[same] 30 人同时问同一个新问题: {json.dumps(REPORT['same_first'], ensure_ascii=False)}", flush=True)
    print(f"[same] 紧接着再问一遍（应命中缓存）: {json.dumps(REPORT['same_again'], ensure_ascii=False)}", flush=True)


def soak(users=30, seconds=90, think=(1.0, 4.0)):
    """一节课的样子：users 个同学持续提问，每人答完歇 1~4 秒再问下一个（大部分问题不同），持续 seconds 秒。"""
    control(token_delay=TOKEN_DELAY, mode="ok", reset=1)
    rng = random.Random(7)
    results, lock = [], threading.Lock()
    deadline = time.perf_counter() + seconds

    counter = iter(range(10**9))

    def student(n):
        local = random.Random(n)
        while time.perf_counter() < deadline:
            question = local.choice(PHRASINGS).format(q=local.choice(QUESTIONS)) + f"（第{next(counter)}问）"
            result = ask(question)
            with lock:
                results.append(result)
            time.sleep(local.uniform(*think))

    with Sampler() as sampler:
        threads = [threading.Thread(target=student, args=(rng.randrange(10**6),)) for _ in range(users)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    row = {**describe(results), **sampler.summary(), "总提问数": len(results),
           "每分钟完成": round(sum(1 for r in results if r[0] == 200) / seconds * 60, 1)}
    REPORT[f"soak_{users}x{seconds}s"] = row
    print(f"[soak] {users} 人持续提问 {seconds} 秒: {json.dumps(row, ensure_ascii=False)}", flush=True)


def essay(n=10, delay=ESSAY_DELAY):
    """n 位同学同时交不同的作文：批改走并发闸门（同时 2 路、最多 8 人排队、最多等 30 秒）。"""
    from tools.chaos.stress import PAPER, TOPIC

    control(delay=delay, mode="ok", reset=1)
    results = [None] * n

    def run(i):
        body = json.dumps({"model": "deepseek", "topic": TOPIC,
                           "text": PAPER + f"\n第{i}位同学补充：模型假设要先检验再使用。（{time.time()}）"}).encode()
        req = urllib.request.Request(f"{BASE}/essay/review", data=body, headers={"Content-Type": "application/json"})
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                resp.read()
                results[i] = (resp.status, time.perf_counter() - started)
        except urllib.error.HTTPError as err:
            results[i] = (err.code, time.perf_counter() - started)
        except Exception as err:  # noqa: BLE001 —— 超时、连不上也记一笔，别让线程悄悄死掉
            results[i] = (f"EXC:{type(err).__name__}", time.perf_counter() - started)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    codes = {}
    for code, _ in results:
        codes[code] = codes.get(code, 0) + 1
    done = sorted(round(t, 1) for code, t in results if code == 200)
    rejected = sorted(round(t, 1) for code, t in results if code != 200)
    row = {"status": codes, "成功的耗时秒": done, "被拒的耗时秒": rejected,
           "上游调用": stats()["calls"], "上游最大并发": stats()["max_active"], "上游单次秒": delay}
    REPORT[f"essay_{n}"] = row
    print(f"[essay] {n} 人同时交稿: {json.dumps(row, ensure_ascii=False)}", flush=True)


if __name__ == "__main__":
    which = sys.argv[1:] or ["sweep", "same", "soak", "essay"]
    urllib.request.urlopen(f"{BASE}/health", timeout=10).read()
    ask("热身：什么是仿真？")  # 先让嵌入模型和索引进内存，别把冷启动算进第一档
    for name in which:
        {"sweep": sweep, "same": same, "soak": soak, "essay": essay}[name]()
    if OUT:
        with open(OUT, "w", encoding="utf-8") as handle:
            json.dump(REPORT, handle, ensure_ascii=False, indent=2)
