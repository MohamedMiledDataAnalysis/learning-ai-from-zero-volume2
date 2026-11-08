"""Call each of the five tools once, exactly as the agent will, and print the results.

Run from the python/ folder:

    python demo_tools.py
"""

import json

from tar_agent.registry import call_tool

CALLS = [
    ("validate_loan_tape", {}),
    ("stratify_pool", {"by": "region", "period": 10, "measure": "balance_90plus"}),
    ("run_trigger_tests", {"period": 10}),
    ("search_prospectus", {"query": "What is the limit for the 90+ day arrears ratio?", "top_k": 2}),
    ("draft_surveillance_note", {"period": 10}),
]

for name, args in CALLS:
    print("=" * 78)
    print(f"Tool call: {name}({json.dumps(args)})")
    print("-" * 78)
    result = json.loads(call_tool(name, args))
    if name == "draft_surveillance_note":
        print(result["note_markdown"])
    elif name == "validate_loan_tape":
        result.pop("issues")
        print(json.dumps(result, indent=2))
    elif name == "stratify_pool":
        for row in result["rows"][:4]:
            print(row)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
