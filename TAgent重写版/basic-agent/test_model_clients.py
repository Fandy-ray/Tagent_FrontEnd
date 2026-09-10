import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


from app.infra.model_client_factory import ModelClientFactory
from app.schema.provider import ModelProvider


class FakeOpenAIHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    records = []
    record_lock = threading.Lock()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        request_body = json.loads(self.rfile.read(length))
        with self.record_lock:
            self.records.append(
                {
                    "authorization": self.headers.get("Authorization"),
                    "model": request_body.get("model"),
                    "stream": request_body.get("stream", False),
                }
            )

        if request_body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            for content in ["token", "-", request_body["model"]]:
                chunk = {
                    "id": "chatcmpl-fake",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": request_body["model"],
                    "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True
            return

        response = {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "created": 1,
            "model": request_body["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": f"reply-{request_body['model']}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format, *_args):
        return


def provider(base_url: str, model_id: str, auth_mode: str) -> ModelProvider:
    return ModelProvider(
        name=model_id,
        served_model_id=model_id,
        base_url=base_url,
        upstream_model=f"upstream-{model_id}",
        auth_mode=auth_mode,
        api_key="top-secret" if auth_mode == "bearer" else "",
        updated_at="2026-07-10T00:00:00Z",
        created_at="2026-07-10T00:00:00Z",
    )


class ModelClientFactoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        FakeOpenAIHandler.records = []
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenAIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        with FakeOpenAIHandler.record_lock:
            FakeOpenAIHandler.records.clear()
        self.factory = ModelClientFactory(timeout_seconds=5)

    def tearDown(self):
        self.factory.close()

    def test_bearer_and_no_auth_providers_send_correct_model_and_headers(self):
        bearer = self.factory.get(provider(self.base_url, "bearer", "bearer"))
        local = self.factory.get(provider(self.base_url, "local", "none"))

        self.assertEqual(bearer.invoke([{"role": "user", "content": "hello"}]).content, "reply-upstream-bearer")
        self.assertEqual(local.invoke([{"role": "user", "content": "hello"}]).content, "reply-upstream-local")

        records = FakeOpenAIHandler.records
        self.assertEqual(records[0]["authorization"], "Bearer top-secret")
        self.assertEqual(records[0]["model"], "upstream-bearer")
        self.assertIsNone(records[1]["authorization"])
        self.assertEqual(records[1]["model"], "upstream-local")

    def test_stream_yields_real_upstream_chunks(self):
        client = self.factory.get(provider(self.base_url, "stream", "none"))
        chunks = [
            chunk.content
            for chunk in client.stream([{"role": "user", "content": "hello"}])
            if chunk.content
        ]
        self.assertEqual(chunks, ["token", "-", "upstream-stream"])
        self.assertTrue(FakeOpenAIHandler.records[0]["stream"])

    def test_cache_uses_served_id_and_updated_at_and_can_be_invalidated(self):
        current = provider(self.base_url, "cached", "bearer")
        first = self.factory.get(current)
        self.assertIs(first, self.factory.get(current))

        changed = ModelProvider(**{**current.__dict__, "updated_at": "2026-07-10T01:00:00Z"})
        self.assertIsNot(first, self.factory.get(changed))
        self.factory.invalidate("cached")
        self.assertIsNot(self.factory.get(changed), first)


if __name__ == "__main__":
    unittest.main()
