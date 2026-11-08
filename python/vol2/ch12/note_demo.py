"""Chapter 12: the surveillance note for period 10."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.tools.note import draft_surveillance_note

print(draft_surveillance_note(10)["note_markdown"])
