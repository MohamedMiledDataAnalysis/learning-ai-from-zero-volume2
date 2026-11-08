"""Build a volume's glossary appendix from the glossary files the chapters write.

    python python/vol2/build_glossary.py          -> book/vol2/appendix-glossary.md
    python python/vol1/build_glossary.py          -> book/vol1/appendix-glossary.md

Each line of book/glossary/<volume>-*.tsv is: term <TAB> definition <TAB> chapter.
A term defined in several chapters appears once: the definition comes from the first chapter
that defines it, and every chapter is listed. Run it again whenever a chapter adds terms.
"""

import csv
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def read_terms(volume):
    """All (term, definition, chapter) rows of one volume, skipping header lines."""
    rows = []
    for path in sorted((REPO / "book" / "glossary").glob(f"{volume}-*.tsv")):
        with path.open(encoding="utf-8", newline="") as f:
            for line in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(line) != 3 or line[0].strip().lower() == "term":
                    continue
                term, definition, chapter = (x.strip() for x in line)
                if term and definition and chapter.isdigit():
                    rows.append((term, definition, int(chapter)))
    return rows


def merge(rows):
    """One entry per term (case-insensitive): first definition by chapter, all chapters listed."""
    entries = OrderedDict()
    for term, definition, chapter in sorted(rows, key=lambda r: r[2]):
        key = term.lower()
        if key not in entries:
            entries[key] = {"term": term, "definition": definition, "chapters": set()}
        entries[key]["chapters"].add(chapter)
    return sorted(entries.values(), key=lambda e: e["term"].lower().lstrip("(\"'"))


def to_markdown(entries, volume):
    title = "Volume 1" if volume == "vol1" else "Volume 2"
    appendix = "Appendix A — Glossary" if volume == "vol1" else "Appendix B — Glossary"
    lines = [f"# {appendix} {{.unnumbered}}", "",
             f"Every term defined in a Word box in {title}, in alphabetical order. The numbers in brackets are "
             "the chapters where the term is defined or explained; the first one is where it first appears.", ""]
    letter = None
    for e in entries:
        first = e["term"][0].upper()
        heading = first if first.isalpha() else "Symbols and numbers"
        if heading != letter:
            letter = heading
            lines += [f"## {heading} {{-}}", ""]
        definition = e["definition"][0].upper() + e["definition"][1:]
        if not definition.endswith("."):
            definition += "."
        chapters = ", ".join(str(c) for c in sorted(e["chapters"]))
        lines += [f"**{e['term']}** — {definition} (ch. {chapters})", ""]
    return "\n".join(lines)


def build(volume):
    entries = merge(read_terms(volume))
    out = REPO / "book" / volume / "appendix-glossary.md"
    out.write_text(to_markdown(entries, volume), encoding="utf-8")
    print(f"{out.relative_to(REPO)}: {len(entries)} terms")
    return entries


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "vol2")
