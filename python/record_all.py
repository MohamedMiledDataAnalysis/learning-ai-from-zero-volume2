"""Record every model reply the book prints. Needs Ollama running with the pinned models:

    ollama pull qwen2.5:7b
    ollama pull nomic-embed-text
    python python/record_all.py

Each line of python/recordings/manifest-*.txt is a command run in 'record' mode.
Afterwards, rebuild the book: replay mode prints exactly what was recorded.
"""

import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
failed = []                                     # a failed command does not stop the others
for manifest in sorted((REPO / "python" / "recordings").glob("manifest-*.txt")) + \
        sorted((REPO / "r" / "recordings").glob("manifest-*.txt")):
    for line in manifest.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            cmd = shlex.split(line)
            if cmd[0] == "python":
                cmd[0] = sys.executable
            print("Recording:", line)
            if subprocess.run(cmd, cwd=REPO).returncode != 0:
                failed.append(line)
if failed:
    print("Failed:", *failed, sep="\n  ")
    sys.exit(1)
print("Done. Rebuild the book to print the recorded replies.")
