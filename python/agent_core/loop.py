"""The agent loop: the controller that every agent in this book shares.

    1. Send the goal, the instructions and the tool descriptions to the brain.
    2. Read the reply. If it asks for tools, run them and add the results to memory.
    3. Go back to 1 with the longer memory.
    4. Stop when the brain gives a final answer, or when the step limit is reached.

The loop does not know what the tools do or which brain it talks to: swapping
the brain (rules, a recording, a live model) changes nothing here.
"""

import json
import time


def run_agent(goal, brain, schemas, call_tool, system_prompt, max_steps=10, log=print):
    """Run the loop. Returns a dict with the final answer, the full memory and the step log."""
    memory = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal},
    ]
    steps = []
    for step in range(1, max_steps + 1):
        reply = brain.next(memory, schemas)                  # the brain chooses the next step
        memory.append({"role": "assistant", "content": reply.get("content", ""),
                       "tool_calls": [{"function": tc} for tc in reply.get("tool_calls", [])]})
        if not reply.get("tool_calls"):                      # no tool requested: this is the final answer
            log(f"[step {step}] final answer")
            steps.append({"step": step, "type": "answer"})
            return {"answer": reply.get("content", ""), "stopped_because": "final answer",
                    "steps": steps, "memory": memory}
        for tc in reply["tool_calls"]:                       # run every tool the brain asked for
            started = time.perf_counter()
            result = call_tool(tc["name"], tc.get("arguments", {}))
            ms = (time.perf_counter() - started) * 1000
            log(f"[step {step}] tool {tc['name']}({json.dumps(tc.get('arguments', {}))}) -> "
                f"{_short(result)}")
            steps.append({"step": step, "type": "tool", "name": tc["name"],
                          "arguments": tc.get("arguments", {}), "result": result, "ms": round(ms, 1)})
            memory.append({"role": "tool", "tool_name": tc["name"], "content": result})
    log(f"[stop] step limit of {max_steps} reached without a final answer")
    return {"answer": None, "stopped_because": "step limit", "steps": steps, "memory": memory}


def _short(text, n=90):
    text = text.replace("\n", " ")
    return text if len(text) <= n else text[: n - 3] + "..."
