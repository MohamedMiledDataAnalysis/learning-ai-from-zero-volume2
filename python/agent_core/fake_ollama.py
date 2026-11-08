"""A stand-in for the Ollama server, used only by the automatic tests.

It answers POST /api/chat in Ollama's format with replies taken from a script,
so the tests can check that OllamaBrain sends and reads real HTTP messages
without downloading a model. It does not imitate a model's intelligence.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def start(script, port=0):
    """Serve the replies in `script` one per request. Returns (server, url, received_requests)."""
    replies = list(script)
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(body)
            reply = replies.pop(0)
            message = {"role": "assistant", "content": reply.get("content", "")}
            if reply.get("tool_calls"):
                message["tool_calls"] = [{"function": {"name": c["name"], "arguments": c["arguments"]}}
                                         for c in reply["tool_calls"]]
            out = json.dumps({"model": body["model"], "created_at": "2026-01-01T00:00:00Z",
                              "message": message, "done": True, "done_reason": "stop"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}", received
