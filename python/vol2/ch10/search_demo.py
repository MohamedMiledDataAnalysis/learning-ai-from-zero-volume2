"""Chapter 10: three searches, and the known limitation of keyword search."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.tools.prospectus import search_prospectus

for q in ["What is the limit for the 90+ day arrears ratio?", "servicer fee", "Which loans were eligible?"]:
    print(f"Query: {q}")
    for r in search_prospectus(q)["results"]:
        print(f"  page {r['page']}  score {r['score']:>6.3f}  {r['text'][:70]}...")
    print()
