"""Reference solution, chapter 6 practical task: call a tool through the MCP-style server."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import META, Client  # noqa: E402


def call_over_mcp(name, arguments):
    client = Client()
    try:
        reply = client.request("tools/call", {"name": name, "arguments": arguments, "_meta": META})
    finally:
        client.close()
    if "error" in reply:
        return {"error": reply["error"]["message"]}
    return json.loads(reply["result"]["content"][0]["text"])
