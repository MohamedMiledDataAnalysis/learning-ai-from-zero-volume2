"""Chapter 7: one rule on its own — interest rates must be between 0% and 30%."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.tools.loan_tape import read_tape

tape = read_tape()
outside = tape[(tape.interest_rate_pct <= 0) | (tape.interest_rate_pct > 30)]
print(f"Loans with a rate outside 0%-30%: {len(outside)}")
print(outside[["loan_id", "interest_rate_pct"]].to_string(index=False))
print(f"Corrected rate: {outside.interest_rate_pct.iloc[0] / 100:.2f}%")
