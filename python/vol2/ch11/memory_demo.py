"""Chapter 11: the agent's memory after one question — every message, in order."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.agent import ask  # noqa: E402

run = ask("Which region holds most of the 90+ day arrears in October 2026?", "rules", None, log=lambda m: None)
for i, message in enumerate(run["memory"], start=1):
    text = message.get("content") or ""
    calls = message.get("tool_calls") or []
    if calls:
        text = "asks for " + ", ".join(f"{c['function']['name']}({c['function']['arguments']})" for c in calls)
    text = text.replace("\n", " ")
    print(f"{i}. {message['role']:<9} {text[:88]}{'...' if len(text) > 88 else ''}")
print("Stopped because:", run["stopped_because"])
