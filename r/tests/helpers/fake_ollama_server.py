"""Start the stand-in Ollama server for the R tests.

    python r/tests/helpers/fake_ollama_server.py script.json url.txt

Writes the server's URL to url.txt, then serves until every scripted reply has
been sent (or 60 seconds have passed).
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "python"))
from agent_core import fake_ollama  # noqa: E402

script = json.loads(Path(sys.argv[1]).read_text())
server, url, received = fake_ollama.start(script)
Path(sys.argv[2]).write_text(url)
deadline = time.time() + 60
while len(received) < len(script) and time.time() < deadline:
    time.sleep(0.05)
time.sleep(0.5)
Path(sys.argv[2] + ".received.json").write_text(json.dumps(received))
server.shutdown()
