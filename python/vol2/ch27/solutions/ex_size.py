"""Exercise 27.7: what the upload check says for a file over the limit (the limit is lowered to 1 kB here)."""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import logic  # noqa: E402

logic.MAX_BYTES = 1024
raw = logic.SAMPLES["thames"]["pdf"].read_bytes()
try:
    logic.decode_upload("data:application/pdf;base64," + base64.b64encode(raw).decode(), "big.pdf")
except ValueError as e:
    print("Refused:", e)
