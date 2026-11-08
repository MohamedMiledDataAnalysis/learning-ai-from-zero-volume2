"""Record every model reply the book prints. Needs Ollama running with the pinned model:

    ollama pull qwen2.5:7b
    python python/record_all.py

Each line of python/recordings/manifest-*.txt is a command run in 'record' mode.
Afterwards, rebuild the book: replay mode prints exactly what was recorded.
"""

import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for manifest in sorted((REPO / "python" / "recordings").glob("manifest-*.txt")) + \
        sorted((REPO / "r" / "recordings").glob("manifest-*.txt")):
    for line in manifest.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            cmd = shlex.split(line)
            if cmd[0] == "python":
                cmd[0] = sys.executable
            print("Recording:", line)
            subprocess.run(cmd, cwd=REPO, check=True)
print("Done. Rebuild the book to print the recorded replies.")
