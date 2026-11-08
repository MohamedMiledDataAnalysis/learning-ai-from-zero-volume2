"""Chapter 27: what dcc.Upload sends, and how the app turns it into a PDF file on disk."""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logic  # noqa: E402

raw = logic.SAMPLES["thames"]["pdf"].read_bytes()
contents = "data:application/pdf;base64," + base64.b64encode(raw).decode()    # what the browser sends
print("What dcc.Upload sends (first 60 characters):")
print(" ", contents[:60] + "...")
print(f"Length of the text: {len(contents):,} characters for a file of {len(raw):,} bytes")
header, data = contents.split(",", 1)
print("Header:", header)
print("First bytes after decoding:", base64.b64decode(data)[:8])

path = logic.decode_upload(contents, "prospectus.pdf")
print("Saved as a temporary .pdf file in", Path(path).parent.name + "/", "- same bytes:", Path(path).read_bytes() == raw)

for bad, name in [("data:text/plain;base64," + base64.b64encode(b"hello").decode(), "notes.pdf"), (None, "x.pdf")]:
    try:
        logic.decode_upload(bad, name)
    except ValueError as e:
        print("Refused:", e)
