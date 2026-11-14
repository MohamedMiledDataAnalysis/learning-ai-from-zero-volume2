"""Tool 4 — search the prospectus and cite the page.

This is the retrieval part of RAG (retrieval-augmented generation):
1. read the PDF page by page,
2. cut each page into short overlapping chunks,
3. score every chunk against the question with BM25, a classic keyword-ranking formula,
4. return the best chunks with their page numbers.

The model then answers from these chunks only, and cites the pages. BM25 needs
no model and no internet, so the results are the same on every computer.
Volume 1, chapter 27 compares it with stemming and embeddings.
"""

import math
import re
from collections import Counter
from functools import lru_cache

from pypdf import PdfReader

from ..data import DATA_DIR

WINDOW, STRIDE = 5, 3          # 5 lines per chunk, a new chunk every 3 lines
K1, B = 1.5, 0.75              # the usual BM25 settings
STOPWORDS = set("a an and are as at be by each for from in is it its of on or that the this to which with "
                "what when how does do".split())
FIXES = {"T est": "Test"}       # letters split by the PDF's kerning


def tokens(text):
    words = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?%?", text.lower())
    return [w for w in words if w not in STOPWORDS]


@lru_cache(maxsize=1)
def chunks():
    """Every chunk of the prospectus: text, page number, section heading."""
    out = []
    section = ""
    for number, page in enumerate(PdfReader(DATA_DIR / "prospectus" / "prospectus.pdf").pages, start=1):
        text = page.extract_text()
        for bad, good in FIXES.items():
            text = text.replace(bad, good)
        lines = [ln.strip() for ln in text.splitlines()
                 if ln.strip() and not ln.startswith("Thames Auto Receivables 2026-1 plc Prospectus")
                 and not re.fullmatch(r"Page \d+", ln.strip())]
        # Every section starts on a new page, so a heading is the first line of a page, written "N. Title" with no
        # full stop or colon. Numbered lines elsewhere (the contents, list items) are not headings.
        first = lines[0] if lines else ""
        is_heading = (re.fullmatch(r"\d{1,2}\. [A-Z][^.:]*", first)
                      or first in ("Important notices", "Index of defined terms"))
        headings = {0: first} if is_heading else {}
        for start in window_starts(len(lines)):
            for i in range(start + 1):
                section = headings.get(i, section)
            body = " ".join(lines[start:start + WINDOW])
            out.append({"page": number, "section": section, "text": body, "tokens": tokens(body)})
    return out


def search_prospectus(query, top_k=3):
    """Tool entry point: the top_k chunks that best match the query, with their page numbers."""
    docs = chunks()
    q = tokens(query)
    if not q:
        raise ValueError("the query has no searchable words")
    n = len(docs)
    avg_len = sum(len(d["tokens"]) for d in docs) / n
    df = Counter(w for d in docs for w in set(d["tokens"]))
    scored = []
    for d in docs:
        tf = Counter(d["tokens"])
        score = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                score += idf * tf[w] * (K1 + 1) / (tf[w] + K1 * (1 - B + B * len(d["tokens"]) / avg_len))
        scored.append((score, d))
    scored.sort(key=lambda x: (-x[0], x[1]["page"]))
    results, seen = [], set()
    for score, d in scored:
        if score <= 0 or len(results) == top_k:
            break
        if d["text"] in seen:
            continue
        seen.add(d["text"])
        results.append({"page": d["page"], "section": d["section"], "score": round(score, 3), "text": d["text"]})
    return {"query": query, "results": results}


def window_starts(n):
    """First line of each chunk: every STRIDE lines, plus one last (shorter) chunk so the end of the page is covered."""
    starts = list(range(0, max(n - WINDOW, 0) + 1, STRIDE))
    if starts[-1] + WINDOW < n:
        starts.append(starts[-1] + STRIDE)
    return starts
