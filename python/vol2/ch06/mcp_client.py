"""Chapter 6: a client that starts the MCP-style server and talks to it over stdio.

Run from the repository root:
    python python/vol2/ch06/mcp_client.py          five requests, summarised
    python python/vol2/ch06/mcp_client.py raw      one request and its response, in full
"""
import json
import subprocess
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "mcp_server.py"
META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "book-client", "version": "1.0.0"}}


class Client:
    def __init__(self):
        self.proc = subprocess.Popen([sys.executable, str(SERVER)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self.next_id = 1

    def request(self, method, params=None):
        msg = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            msg["params"] = params
        self.next_id += 1
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()
        self.proc.stdout.close()


def short(obj, n=150):
    text = json.dumps(obj)
    return text if len(text) <= n else text[: n - 3] + "..."


def raw():
    """One tools/call exchange, printed exactly as it crosses the pipe (the long text is shortened)."""
    c = Client()
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "search_prospectus", "arguments": {"query": "servicer fee", "top_k": 1},
                          "_meta": META}}
    c.proc.stdin.write(json.dumps(request) + "\n")
    c.proc.stdin.flush()
    reply = json.loads(c.proc.stdout.readline())
    c.close()
    print("Request (one line on the pipe, shown indented):")
    print(json.dumps(request, indent=2))
    text = reply["result"]["content"][0]["text"]
    reply["result"]["content"][0]["text"] = text[:60] + "..."
    print("Response:")
    print(json.dumps(reply, indent=2))


if __name__ == "__main__" and sys.argv[1:] == ["raw"]:
    raw()
elif __name__ == "__main__":
    c = Client()
    r = c.request("server/discover")
    print("1. server/discover ->", short(r["result"]["supportedVersions"]))
    r = c.request("tools/list", {"_meta": META})
    print("2. tools/list      ->", [t["name"] for t in r["result"]["tools"]])
    r = c.request("tools/call", {"name": "run_trigger_tests", "arguments": {"period": 10}, "_meta": META})
    data = json.loads(r["result"]["content"][0]["text"])
    a90 = next(t for t in data["tests"] if t["test"] == "arrears_90_ratio")
    print(f"3. tools/call      -> 90+ ratio {a90['value']:.2%}, breached: {a90['breached']}, "
          f"isError: {r['result']['isError']}")
    r = c.request("tools/call", {"name": "validate_loan_tape", "arguments": {}, "_meta": META})
    print("4. tools/call      ->", short(r["error"]))
    r = c.request("tools/list", {})
    print("5. no _meta        ->", short(r["error"]))
    c.close()
