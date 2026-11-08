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
cat("Lines where the words differ (R first, then Python):\n")
for (p in c(4, 9)) {
  a <- clean_lines(r_pages[p]); b <- clean_lines(py_pages[p])
  for (k in which(a != b)[1:2]) cat(sprintf("  page %d  R : %s\n          Py: %s\n", p, substr(a[k], 1, 60), substr(b[k], 1, 60)))
}
