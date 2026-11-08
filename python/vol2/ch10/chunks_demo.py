"""Chapter 10: how the prospectus is cut into chunks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.tools.prospectus import chunks, tokens

all_chunks = chunks()
print(f"Pages: {max(c['page'] for c in all_chunks)}   Chunks: {len(all_chunks)}")
example = next(c for c in all_chunks if "must not exceed 1.25%" in c["text"])
print(f"Example chunk (page {example['page']}, section '{example['section']}'):")
print(" ", example["text"])
print("Its first 12 tokens:", example["tokens"][:12])
print("Tokens of the question:", tokens("What is the limit for the 90+ day arrears ratio?"))
