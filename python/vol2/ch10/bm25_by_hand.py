"""Chapter 10: the BM25 score of one word in one chunk, step by step."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

import math
from collections import Counter

from tar_agent.tools.prospectus import B, K1, chunks

docs = chunks()
word = "arrears"
chunk = next(c for c in docs if "must not exceed 1.25%" in c["text"])
n = len(docs)
df = sum(1 for d in docs if word in d["tokens"])
tf = Counter(chunk["tokens"])[word]
avg_len = sum(len(d["tokens"]) for d in docs) / n
length = len(chunk["tokens"])
idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
weight = tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / avg_len))
print(f"N (chunks) = {n}, df (chunks containing '{word}') = {df}")
print(f"idf = ln(1 + ({n} - {df} + 0.5) / ({df} + 0.5)) = {idf:.4f}")
print(f"tf = {tf}, chunk length = {length}, average length = {avg_len:.2f}")
print(f"tf part = {tf} x {K1 + 1} / ({tf} + {K1} x (1 - {B} + {B} x {length} / {avg_len:.2f})) = {weight:.4f}")
print(f"score for '{word}' = {idf:.4f} x {weight:.4f} = {idf * weight:.4f}")
