"""Check your answer to the practical task of chapter 28.

Task: run fairness_by_region.py. For model C (postcode areas), what share of GOOD North West loans does the
model flag (the false positive rate, FPR NW), in percent with 2 decimals?
Run from the repository root:  python python/vol2/ch28/check_ch28.py --fpr 12.34
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--fpr", type=float, required=True, help="false positive rate in percent, e.g. 12.34")
answer = parser.parse_args().fpr

script = Path(__file__).resolve().parent / "fairness_by_region.py"
out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True).stdout
line = next(ln for ln in out.splitlines() if ln.startswith("C. postcode areas"))
fpr_nw = float(re.findall(r"([\d.]+)%", line)[3])
if abs(answer - fpr_nw) < 0.005:
    print(f"Correct: model C flags {fpr_nw:.2f}% of the good North West loans.")
else:
    print("Not yet. Read the row 'C. postcode areas', column 'FPR NW'. Reread section 28.3.")
