# Chapter 19: where pdftools (R) and pypdf (Python) read the prospectus differently.
# The script asks Python for pypdf's text, then compares it with pdftools, line by line.
source("r/taragent/load.R")

python <- if (nzchar(Sys.which("python3"))) Sys.which("python3") else Sys.which("python")
code <- paste0("import json; from pypdf import PdfReader; ",
               "print(json.dumps([p.extract_text() for p in PdfReader('data/prospectus/prospectus.pdf').pages]))")
py_pages <- fromJSON(paste(system2(python, c("-c", shQuote(code)), stdout = TRUE), collapse = ""))
r_pages <- pdftools::pdf_text("data/prospectus/prospectus.pdf")
clean_lines <- function(t) { l <- trimws(gsub(" {2,}", " ", strsplit(t, "\n", fixed = TRUE)[[1]])); l[nchar(l) > 0] }
same_count <- 0
for (p in seq_along(r_pages)) {
  a <- clean_lines(r_pages[p]); b <- clean_lines(py_pages[p])
  if (length(a) == length(b)) same_count <- same_count + 1
}
cat(sprintf("Pages with the same number of lines: %d of %d\n\n", same_count, length(r_pages)))
cat("The first lines where the words differ, on pages with the same lines (R first, then Python):\n")
shown <- 0
for (p in seq_along(r_pages)) {
  a <- clean_lines(r_pages[p]); b <- clean_lines(py_pages[p])
  if (length(a) != length(b)) next
  for (k in which(a != b)) {
    if (shown == 4) break
    x <- strsplit(a[k], "")[[1]]; y <- strsplit(b[k], "")[[1]]
    first <- which(x[seq_len(min(length(x), length(y)))] != y[seq_len(min(length(x), length(y)))])[1]
    from <- max(1, (if (is.na(first)) min(length(x), length(y)) else first) - 25)   # 25 letters before the change
    cat(sprintf("  page %d  R : ...%s\n          Py: ...%s\n", p, substr(a[k], from, from + 50), substr(b[k], from, from + 50)))
    shown <- shown + 1
  }
}
