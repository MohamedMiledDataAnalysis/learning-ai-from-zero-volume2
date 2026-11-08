"""Read any prospectus PDF the user uploads, and search it.

Tool 4 (prospectus.py) reads one known file, the Thames prospectus. The Prospectus
Analyser of Volume 2 Part E must read a file it has never seen, so this module
generalises the same steps to any PDF path:

1. read the text of each page and clean it (normalise_line),
2. drop the running header and the page numbers, which repeat on every page,
3. cut each page into overlapping chunks and search them with BM25 (search_document).

The cleaning rules are written once and copied exactly in R (r/taragent/tools/document.R),
so the two languages see the same words even though they use different PDF libraries.
"""

import math
import os
import re
from collections import Counter
from functools import lru_cache

from pypdf import PdfReader

from .prospectus import B, K1, STRIDE, WINDOW, tokens, window_starts

PAGE_NUMBER = re.compile(r"^(?:Page \d+|-\s?\d+\s?-|\d+)$")


def normalise_line(line):
    """Clean one line of PDF text so that pypdf (Python) and pdftools (R) give the same words."""
    line = line.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    line = re.sub(r"\s+", " ", line).strip()
    # pypdf splits a few capital letters from the rest of the word ("T est", "Y our"): join them back.
    # Only T, V, W and Y are joined: A and I are English words, and B, C, D and Z name classes of notes.
    line = re.sub(r"\b([TVWY]) ([a-z]{2,})", r"\1\2", line)
    # pypdf also puts a space before some punctuation ("Monthly ,", "Ratio ”") and after "(".
    line = re.sub(r" ([,;:.)%\u201d])", r"\1", line)
    line = re.sub(r"\( ", "(", line)
    return line


def _read_raw_pages(pdf_path):
    return [page.extract_text() or "" for page in PdfReader(pdf_path).pages]


@lru_cache(maxsize=8)
def _pages_cached(pdf_path, mtime):
    raw = [[normalise_line(ln) for ln in text.splitlines()] for text in _read_raw_pages(pdf_path)]
    raw = [[ln for ln in lines if ln] for lines in raw]
    # The running header is the first line that repeats at the top of at least half of the pages.
    firsts = Counter(lines[0] for lines in raw if lines)
    header = None
    if firsts:
        line, count = firsts.most_common(1)[0]
        if count >= max(2, len(raw) // 2):
            header = line
    pages = []
    for lines in raw:
        pages.append([ln for ln in lines if ln != header and not PAGE_NUMBER.match(ln)])
    return tuple(tuple(p) for p in pages)


def read_pages(pdf_path):
    """The clean lines of each page: pages[0] is page 1."""
    pdf_path = os.path.abspath(str(pdf_path))
    if not os.path.exists(pdf_path):
        raise ValueError(f"no PDF at {pdf_path}")
    return [list(p) for p in _pages_cached(pdf_path, os.path.getmtime(pdf_path))]


def page_texts(pdf_path):
    """Each page as one line of text (its clean lines joined by spaces)."""
    return [" ".join(lines) for lines in read_pages(pdf_path)]


def document_chunks(pdf_path):
    """Chunks of WINDOW lines every STRIDE lines on every page, as in Tool 4."""
    out = []
    for number, lines in enumerate(read_pages(pdf_path), start=1):
        for start in window_starts(len(lines)) if lines else []:
            body = " ".join(lines[start:start + WINDOW])
            out.append({"page": number, "text": body, "tokens": tokens(body)})
    return out


def search_document(pdf_path, query, top_k=3):
    """Tool entry point: the top_k chunks of any PDF that best match the query, with their page numbers."""
    docs = document_chunks(pdf_path)
    q = tokens(query)
    if not q:
        raise ValueError("the query has no searchable words")
    if not docs:
        raise ValueError("the PDF has no text (a scanned document needs OCR first)")
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
        results.append({"page": d["page"], "score": round(score, 3), "text": d["text"]})
    return {"query": query, "results": results}
