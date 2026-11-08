"""Chapter 6: a minimal MCP-style tool server, written by hand, over stdio.

The client starts this program and talks to it through standard input and output:
one JSON-RPC 2.0 message per line, UTF-8. The server exposes two finance tools.

This is a TEACHING server: it follows the message shapes of MCP revision 2026-07-28 for
server/discover, tools/list and tools/call, but it is not a complete or certified implementation.
For real servers, use an official MCP SDK.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.registry import TOOLS, call_tool  # noqa: E402

PROTOCOL = "2026-07-28"
EXPOSED = ["run_trigger_tests", "search_prospectus"]          # the only tools this server offers
SERVER_INFO = {"name": "thames-surveillance", "version": "1.0.0"}


def result(msg_id, body):
    return {"jsonrpc": "2.0", "id": msg_id, "result": {**body, "resultType": "complete",
                                                       "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO}}}


def error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle(msg):
    msg_id, method, params = msg.get("id"), msg.get("method"), msg.get("params", {})
    if method == "server/discover":
        return result(msg_id, {"supportedVersions": [PROTOCOL], "capabilities": {"tools": {}}})
    version = params.get("_meta", {}).get("io.modelcontextprotocol/protocolVersion")
    if version is None:
        return error(msg_id, -32602, "missing _meta protocolVersion")
    if version != PROTOCOL:
        return error(msg_id, -32022, "Unsupported protocol version")
    if method == "tools/list":
        tools = [{"name": n, "description": TOOLS[n]["description"], "inputSchema": TOOLS[n]["parameters"]}
                 for n in EXPOSED]
        return result(msg_id, {"tools": tools})
    if method == "tools/call":
        name = params.get("name")
        if name not in EXPOSED:
            return error(msg_id, -32602, f"unknown tool: {name}")
        text = call_tool(name, params.get("arguments", {}))
        is_error = "error" in json.loads(text)
        return result(msg_id, {"content": [{"type": "text", "text": text}], "isError": is_error})
    return error(msg_id, -32601, f"method not found: {method}")


def main():
    for line in sys.stdin:                         # one message per line
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = error(None, -32700, "parse error")
        else:
            reply = handle(msg)
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
