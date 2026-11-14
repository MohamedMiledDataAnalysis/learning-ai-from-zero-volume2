"""Shared helpers to assemble the full-length prospectuses (Thames and Severn).

Each generator writes the deal's key sections from its terms (word for word as in the short teaching
prospectus) and this module places them, renumbered, among the longer sections of a real prospectus
(risk factors, terms and conditions, servicing, regulation, tax...). The long sections are Markdown files in
generator/prospectus_text/<deal>/, with [[key]] placeholders for the deal's facts. The index of defined
terms is built in two passes: the first PDF gives the page where each term is defined, the second prints it.
"""

import os
import re
import subprocess
from pathlib import Path

TEXT = Path(__file__).resolve().parent / "prospectus_text"
ENV = {**os.environ, "SOURCE_DATE_EPOCH": "1767225600", "FORCE_SOURCE_DATE": "1"}


def section_file(deal, name):
    """The text of one long section, or an empty string if the file is missing."""
    path = TEXT / deal / name
    return path.read_text(encoding="utf-8").strip() + "\n" if path.exists() else ""


def fill(text, values):
    """Replace every [[key]] placeholder; an unknown key is an error, so no placeholder reaches the PDF."""
    def sub(m):
        key = m.group(1)
        if key not in values:
            raise KeyError(f"unknown placeholder [[{key}]]")
        return str(values[key])
    return re.sub(r"\[\[([a-z_0-9]+)\]\]", sub, text)


def split_sections(md, heading):
    """Split Markdown into its YAML front matter and a list of (heading line, body) pairs."""
    front = ""
    if md.startswith("---\n"):
        end = md.index("\n---\n", 4) + 5
        front, md = md[:end], md[end:]
    parts, current, body = [], None, []
    for line in md.splitlines(keepends=True):
        if re.match(heading, line):
            if current is not None or "".join(body).strip():
                parts.append((current, "".join(body)))
            current, body = line.rstrip("\n"), []
        else:
            body.append(line)
    parts.append((current, "".join(body)))
    return front, parts


def strip_newpages(text):
    return re.sub(r"\n\s*\\newpage\s*\n", "\n", "\n" + text).strip() + "\n"


DEFINED = re.compile(r'\(the "([A-Z][A-Za-z\'\- ]{2,50})"\)|\(together, the "([A-Z][A-Za-z\'\- ]{2,50})"\)'
                     r'|"\*\*([A-Z][A-Za-z\'\- ]{2,50})\*\*" means|^\*\*([A-Z][A-Za-z\'\- ]{2,50})\*\*:', re.M)


def defined_terms(md):
    """Defined terms in order of first definition: (the "Term"), "**Term**" means, **Term**: ..."""
    seen = []
    for m in DEFINED.finditer(md):
        term = next(g for g in m.groups() if g)
        if term not in seen:
            seen.append(term)
    return seen


def pdf_pages_text(pdf):
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    return out.split("\f")


def first_pages(pdf, terms, start_page=1):
    """For each term, the first page (1-based, from start_page) where it appears in quotes or bold."""
    pages = [re.sub(r"\s+", " ", p) for p in pdf_pages_text(pdf)]
    found = {}
    for term in terms:
        defined = re.compile(r'[“"]' + re.escape(term) + r'[”"]')        # where it is defined, in quotes
        for i, text in enumerate(pages[start_page - 1:], start=start_page):
            if defined.search(text):
                found[term] = i
                break
    return found


def index_table(terms, pages, title_line):
    rows = sorted(((t, pages.get(t)) for t in terms), key=lambda x: x[0].lower())
    lines = [title_line, "", "| Term | Page |", "|---|---:|"]
    for term, page in rows:
        lines.append(f"| {term} | {page if page else '–'} |")
    return "\n".join(lines) + "\n"


def run_pandoc(md_path, pdf_path, toc=True):
    args = ["pandoc", str(md_path), "-o", str(pdf_path), "--pdf-engine=xelatex"]
    subprocess.run(args, check=True, env=ENV)
    pdf = Path(pdf_path).read_bytes()
    pdf = re.sub(rb"/ID\[<[0-9a-f]{32}><[0-9a-f]{32}>\]", b"/ID[<" + b"0" * 32 + b"><" + b"0" * 32 + b">]", pdf)
    Path(pdf_path).write_bytes(pdf)


def build_with_index(md_without_index, index_title, out_dir, index_heading_line):
    """Two passes: build, find the page of each defined term, build again with the index filled in."""
    out_dir = Path(out_dir)
    terms = defined_terms(md_without_index)
    placeholder = index_table(terms, {t: 999 for t in terms}, index_heading_line)
    md = md_without_index.rstrip() + "\n\n\\newpage\n\n" + placeholder
    (out_dir / "prospectus.md").write_text(md, encoding="utf-8")
    run_pandoc(out_dir / "prospectus.md", out_dir / "prospectus.pdf")
    pages = first_pages(out_dir / "prospectus.pdf", terms, start_page=2)
    md = md_without_index.rstrip() + "\n\n\\newpage\n\n" + index_table(terms, pages, index_heading_line)
    (out_dir / "prospectus.md").write_text(md, encoding="utf-8")
    run_pandoc(out_dir / "prospectus.md", out_dir / "prospectus.pdf")
    return len(terms)
