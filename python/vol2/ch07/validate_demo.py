"""Chapter 7: run the validation tool and compare the totals before and after cleaning."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.tools.loan_tape import clean_tape, find_issues, read_tape

tape = read_tape()                                  # the tape exactly as received
issues = find_issues(tape)                          # run the nine rules
print(f"Rows received: {len(tape):,}")
print(f"Issues found:  {len(issues)}")
print()
print(f"{'loan_id':<10} {'column':<32} {'rule'}")
for i in issues:
    print(f"{i['loan_id']:<10} {i['column']:<32} {i['rule']}")

clean = clean_tape(tape, issues)                    # apply the safe fixes
print()
print(f"Balance as received:  £{tape.current_balance.sum():,.2f}")
print(f"Balance after fixes:  £{clean.current_balance.sum():,.2f}")
print(f"Loans after fixes:    {len(clean):,}")
