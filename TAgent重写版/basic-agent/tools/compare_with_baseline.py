"""新旧两个服务并行跑同一批真实请求，对比响应结构。

LLM 输出不确定，所以比对的是"形状"：状态码、JSON 键的嵌套集合、值的类型，
以及若干关键不变量（如 code/msg、model 字段、SSE 帧序列）。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

OLD = "http://127.0.0.1:5098"
NEW = "http://127.0.0.1:5099"
API_KEY = sys.argv[1]

PROVIDER = {
    "name": "deepseek",
    "served_model_id": "deepseek-chat",
    "base_url": "https://api.deepseek.com/v1",
    "upstream_model": "deepseek-chat",
    "auth_mode": "bearer",
    "api_key": API_KEY,
    "temperature": 0.1,
    "enabled": True,
}


def call(base, method, path, body=None, headers=None, timeout=180, raw=False):
    url = base + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", "replace")
        status = e.code
    except Exception as e:  # noqa: BLE001
        return {"status": -1, "error": f"{type(e).__name__}: {e}", "ms": 0}
    elapsed = (time.perf_counter() - t0) * 1000
    if raw:
        return {"status": status, "text": payload, "ms": elapsed}
    try:
        return {"status": status, "json": json.loads(payload), "ms": elapsed}
    except json.JSONDecodeError:
        return {"status": status, "text": payload, "ms": elapsed}


def shape(value, path=""):
    """把 JSON 摊平成 {路径: 类型} 的集合，忽略具体取值。"""
    out = {}
    if isinstance(value, dict):
        for k, v in value.items():
            out.update(shape(v, f"{path}.{k}"))
    elif isinstance(value, list):
        out[path + "[]"] = "list"
        if value:
            out.update(shape(value[0], path + "[0]"))
    else:
        out[path] = type(value).__name__
    return out


def sse_shape(text):
    """SSE 流的帧序列特征：帧数、首帧 delta 键、末帧 finish_reason、是否有 [DONE]。"""
    frames = [ln[6:] for ln in text.splitlines() if ln.startswith("data: ")]
    done = frames and frames[-1].strip() == "[DONE]"
    parsed = []
    for f in frames:
        if f.strip() == "[DONE]":
            continue
        try:
            parsed.append(json.loads(f))
        except json.JSONDecodeError:
            pass
    first_delta = sorted(parsed[0]["choices"][0]["delta"]) if parsed else []
    finishes = [p["choices"][0].get("finish_reason") for p in parsed]
    return {
        "has_done": done,
        "first_delta_keys": first_delta,
        "final_finish_reason": finishes[-1] if finishes else None,
        "object": parsed[0]["object"] if parsed else None,
        "content_nonempty": any(
            p["choices"][0]["delta"].get("content") for p in parsed
        ),
    }


results = []


def compare(label, fn_old, fn_new, extract=shape):
    o = fn_old()
    n = fn_new()
    so = (o["status"], extract(o.get("json", o.get("text"))))
    sn = (n["status"], extract(n.get("json", n.get("text"))))
    ok = so == sn
    results.append((label, ok, o, n, so, sn))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label:<46} 旧 {o['status']} {o['ms']:>6.0f}ms | 新 {n['status']} {n['ms']:>6.0f}ms")
    if not ok:
        only_old = set(so[1].items()) - set(sn[1].items()) if isinstance(so[1], dict) else so[1]
        only_new = set(sn[1].items()) - set(so[1].items()) if isinstance(sn[1], dict) else sn[1]
        print(f"        仅旧有: {sorted(only_old)[:8]}")
        print(f"        仅新有: {sorted(only_new)[:8]}")
    return o, n


ADMIN = {"X-Agent-Admin-Token": "tok"}
INTERNAL = {"X-Agent-Internal-Token": "itok"}

print("=" * 96)
print("1) 注册 provider（admin 通道）")
compare("POST /admin/model-providers",
        lambda: call(OLD, "POST", "/admin/model-providers", PROVIDER, ADMIN),
        lambda: call(NEW, "POST", "/admin/model-providers", PROVIDER, ADMIN))

print("\n2) 只读接口")
compare("GET /v1/models",
        lambda: call(OLD, "GET", "/v1/models"),
        lambda: call(NEW, "GET", "/v1/models"))
compare("GET /admin/model-providers（Key 应脱敏）",
        lambda: call(OLD, "GET", "/admin/model-providers", None, ADMIN),
        lambda: call(NEW, "GET", "/admin/model-providers", None, ADMIN))

print("\n3) 真实 LLM 调用")
chat_body = {"model": "deepseek-chat",
             "messages": [{"role": "user", "content": "用一句话说明什么是排队论。"}]}
compare("POST /v1/chat/completions（非流式）",
        lambda: call(OLD, "POST", "/v1/chat/completions", chat_body),
        lambda: call(NEW, "POST", "/v1/chat/completions", chat_body))

stream_body = dict(chat_body, stream=True)
compare("POST /v1/chat/completions（SSE 流式）",
        lambda: call(OLD, "POST", "/v1/chat/completions", stream_body, raw=True),
        lambda: call(NEW, "POST", "/v1/chat/completions", stream_body, raw=True),
        extract=lambda t: sse_shape(t if isinstance(t, str) else ""))

rag_body = {"model": "deepseek-chat", "user_question": "什么是系统仿真？"}
compare("POST /rag/query",
        lambda: call(OLD, "POST", "/rag/query", rag_body),
        lambda: call(NEW, "POST", "/rag/query", rag_body))

compare("POST /quiz/generate",
        lambda: call(OLD, "POST", "/quiz/generate", {"model": "deepseek-chat"}),
        lambda: call(NEW, "POST", "/quiz/generate", {"model": "deepseek-chat"}))

review_body = {"model": "deepseek-chat", "question": "什么是排队论？",
               "user_answer": "研究排队现象的数学理论。"}
compare("POST /quiz/review",
        lambda: call(OLD, "POST", "/quiz/review", review_body),
        lambda: call(NEW, "POST", "/quiz/review", review_body))

print("\n4) 内部通道（临时 provider envelope）")
env_body = {"provider": PROVIDER, "payload": chat_body}
compare("POST /internal/v1/chat/completions",
        lambda: call(OLD, "POST", "/internal/v1/chat/completions", env_body, INTERNAL),
        lambda: call(NEW, "POST", "/internal/v1/chat/completions", env_body, INTERNAL))
compare("POST /internal/rag/query",
        lambda: call(OLD, "POST", "/internal/rag/query", {"provider": PROVIDER, "payload": rag_body}, INTERNAL),
        lambda: call(NEW, "POST", "/internal/rag/query", {"provider": PROVIDER, "payload": rag_body}, INTERNAL))
compare("POST /internal/cache/invalidate",
        lambda: call(OLD, "POST", "/internal/cache/invalidate", {"model": "deepseek-chat"}, INTERNAL),
        lambda: call(NEW, "POST", "/internal/cache/invalidate", {"model": "deepseek-chat"}, INTERNAL))

print("\n5) 错误路径")
for label, path, body, hdr in [
    ("空 body -> 400", "/rag/query", {"user_question": ""}, None),
    ("未知模型 -> 404", "/v1/chat/completions", dict(chat_body, model="nope"), None),
    ("内部通道缺 token -> 403", "/internal/rag/query", {}, None),
    ("admin 缺 token -> 403", "/admin/model-providers", None, None),
    ("整卷 exam_id 非法 -> 422", "/quiz/exam/review",
     {"model": "deepseek-chat", "exam_id": "not-a-uuid", "answers": {}}, None),
    ("整卷试卷不存在 -> 410", "/quiz/exam/review",
     {"model": "deepseek-chat", "exam_id": "12345678-1234-5678-1234-567812345678", "answers": {}}, None),
]:
    m = "GET" if body is None else "POST"
    compare(label,
            lambda p=path, b=body, h=hdr, mm=m: call(OLD, mm, p, b, h),
            lambda p=path, b=body, h=hdr, mm=m: call(NEW, mm, p, b, h))

print("\n" + "=" * 96)
failed = [r for r in results if not r[1]]
print(f"合计 {len(results)} 项，通过 {len(results)-len(failed)}，失败 {len(failed)}")
if failed:
    print("\n失败明细：")
    for label, _, o, n, so, sn in failed:
        print(f"\n--- {label} ---")
        print("旧:", json.dumps(o.get('json', o.get('text', o)), ensure_ascii=False)[:600])
        print("新:", json.dumps(n.get('json', n.get('text', n)), ensure_ascii=False)[:600])
sys.exit(1 if failed else 0)
