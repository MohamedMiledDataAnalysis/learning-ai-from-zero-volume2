# Solution 19.7: check that every line of every page appears in at least one chunk.
source("r/taragent/load.R")

pages <- pdf_text(file.path(DATA_DIR, "prospectus", "prospectus.pdf"))
uncovered <- 0
for (number in seq_along(pages)) {
  # The same cleaning as chunks(): one space between words, no header, no page number.
  text <- pages[number]
  for (bad in names(FIXES)) text <- gsub(bad, FIXES[[bad]], text, fixed = TRUE)
  lines <- trimws(gsub(" {2,}", " ", strsplit(text, "\n", fixed = TRUE)[[1]]))
  lines <- lines[nchar(lines) > 0 & !startsWith(lines, "Thames Auto Receivables 2026-1 plc Prospectus") &
                   !grepl("^Page [0-9]+$", lines)]
  starts <- window_starts(length(lines))
  covered <- unique(unlist(lapply(starts, function(s) (s + 1):min(s + WINDOW, length(lines)))))
  missing <- setdiff(seq_along(lines), covered)
  uncovered <- uncovered + length(missing)
  cat(sprintf("page %d: %2d lines, %d chunks, lines in no chunk: %d\n", number, length(lines), length(starts),
              length(missing)))
}
cat(sprintf("Total chunks: %d   Lines in no chunk: %d\n", length(chunks()), uncovered))
