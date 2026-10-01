"""可控延迟 / 可控故障的 OpenAI 兼容假上游，只给压测用。

GET  /control?delay=1.5&token_delay=0.03&mode=ok|error|hang|drop&reset=1   调行为、清计数
GET  /stats                                                                调用计数与最大并发
POST /v1/chat/completions                                                  按 prompt 认出请求类型，回合法 JSON
"""
import json
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # basic-agent/
from app.schema.essay import RUBRIC_POINTS  # noqa: E402

STATE = {"delay": 1.0, "token_delay": 0.03, "mode": "ok"}
STATS = {"calls": 0, "active": 0, "max_active": 0, "completed": 0}
LOCK = threading.Lock()
ANSWER = "到达率 λ 指单位时间内到达系统的平均顾客数，是排队模型最基本的输入参数之一。" * 3


def answer_for(prompt: str):
    for name, points in RUBRIC_POINTS.items():
        if points[0] in prompt:
            payload = {"hits": list(points[:3]), "misses": list(points[3:]), "comment": f"{name}：命中前三条，缺第四条。"}
            if "flagged_paragraphs" in prompt:
                payload["flagged_paragraphs"] = [2]
            return payload
    if "逐句批注" in prompt:
        ids = re.findall(r"^(P\d+S\d+) ", prompt, flags=re.M)
        items = []
        if ids:
            items.append({"sentence_id": ids[0], "kind": "issue", "comment": "这句下结论没有给依据。"})
        if len(ids) > 1:
            items.append({"sentence_id": ids[-1], "kind": "praise", "comment": "这句把结论收住了。"})
        return {"items": items}
    if "小论文题" in prompt:
        return {"title": "排队论视角下的银行窗口配置", "requirements": ["用 M/M/c 模型估算平均等待时间", "写明到达与服务的假设"], "suggested_chars": 1000}
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def _json(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/control":
            for key in ("delay", "token_delay"):
                if key in query:
                    STATE[key] = float(query[key][0])
            if "mode" in query:
                STATE["mode"] = query["mode"][0]
            if "reset" in query:
                with LOCK:
                    STATS.update(calls=0, max_active=0, completed=0)
            return self._json(200, STATE)
        if url.path == "/stats":
            with LOCK:
                return self._json(200, dict(STATS))
        return self._json(404, {})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        with LOCK:
            STATS["calls"] += 1
            STATS["active"] += 1
            STATS["max_active"] = max(STATS["max_active"], STATS["active"])
        try:
            mode = STATE["mode"]
            if mode == "error":
                return self._json(500, {"error": {"message": "fake upstream error", "type": "server_error"}})
            if mode == "hang":
                time.sleep(3600)
                return
            prompt = data["messages"][-1]["content"]
            if data.get("stream"):
                return self._stream(data, drop=(mode == "drop"))
            time.sleep(STATE["delay"])
            payload = answer_for(prompt)
            content = json.dumps(payload, ensure_ascii=False) if payload is not None else ANSWER
            self._json(200, {
                "id": "chatcmpl-fake", "object": "chat.completion", "created": int(time.time()),
                "model": data.get("model", "fake-model"),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            })
            with LOCK:
                STATS["completed"] += 1
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with LOCK:
                STATS["active"] -= 1

    def _stream(self, data, *, drop):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def frame(delta, finish=None):
            body = {"id": "chatcmpl-fake", "object": "chat.completion.chunk", "created": int(time.time()),
                    "model": data.get("model", "fake-model"),
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            self.wfile.write(f"data: {json.dumps(body, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()

        frame({"role": "assistant", "content": ""})
        for index, char in enumerate(ANSWER):
            if drop and index == 20:
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            frame({"content": char})
            time.sleep(STATE["token_delay"])
        frame({}, "stop")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        with LOCK:
            STATS["completed"] += 1


if __name__ == "__main__":
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("127.0.0.1", 9100), Handler).serve_forever()
