# Tool 4 — search the prospectus and cite the page (R version of tar_agent/tools/prospectus.py).
#
# The same four steps: read the PDF page by page, cut each page into overlapping
# chunks of 5 lines every 3 lines, score each chunk with BM25, return the best chunks.
#
# One difference with Python: pdftools (R) and pypdf (Python) extract the text with
# different libraries. pdftools keeps words whole where pypdf splits a few of them at the
# letter spacing ("Total" versus "T otal"). Lines, pages and chunks are the same; a few
# words differ, so a few BM25 scores differ in the last decimals (chapter 19).

suppressPackageStartupMessages(library(pdftools))

WINDOW <- 5
STRIDE <- 3                     # 5 lines per chunk, a new chunk every 3 lines
K1 <- 1.5
B <- 0.75                       # the usual BM25 settings
STOPWORDS <- strsplit(paste("a an and are as at be by each for from in is it its of on or that the this to",
                            "which with what when how does do"), " ")[[1]]
FIXES <- c("T est" = "Test")    # letters split by the PDF's kerning (pypdf only; harmless here)

tokens <- function(text) {
  words <- regmatches(tolower(text), gregexpr("[a-z0-9]+(?:\\.[0-9]+)?%?", tolower(text), perl = TRUE))[[1]]
  words[!(words %in% STOPWORDS)]
}

# Every chunk of the prospectus: text, page number, section heading.
chunks <- function() {
  cached("chunks", function() {
    out <- list()
    section <- ""
    pages <- pdf_text(file.path(DATA_DIR, "prospectus", "prospectus.pdf"))
    for (number in seq_along(pages)) {
      text <- pages[number]
      for (bad in names(FIXES)) text <- gsub(bad, FIXES[[bad]], text, fixed = TRUE)
      lines <- strsplit(text, "\n", fixed = TRUE)[[1]]
      lines <- trimws(gsub(" {2,}", " ", lines))       # pdftools pads columns with spaces: keep one
      lines <- lines[nchar(lines) > 0 &
                       !startsWith(lines, "Thames Auto Receivables 2026-1 plc Prospectus") &
                       !grepl("^Page [0-9]+$", lines)]
      # Every section starts on a new page, so a heading is the first line of a page, written "N. Title" with no
      # full stop or colon. Numbered lines elsewhere (the contents, list items) are not headings.
      is_heading <- seq_along(lines) == 1 &
        (grepl("^[0-9]{1,2}\\. [A-Z][^.:]*$", lines) | lines %in% c("Important notices", "Index of defined terms"))
      if (!length(lines)) next                       # a page with no text gives no chunk
      for (start in window_starts(length(lines))) {
        for (i in 0:start) if (i + 1 <= length(lines) && is_heading[i + 1]) section <- lines[i + 1]
        body <- paste(lines[(start + 1):min(start + WINDOW, length(lines))], collapse = " ")
        out[[length(out) + 1]] <- list(page = number, section = section, text = body, tokens = tokens(body))
      }
    }
    out
  })
}

# Tool entry point: the top_k chunks that best match the query, with their page numbers.
search_prospectus <- function(query, top_k = 3) {
  docs <- chunks()
  q <- tokens(query)
  if (length(q) == 0) stop("the query has no searchable words", call. = FALSE)
  n <- length(docs)
  lens <- vapply(docs, function(d) length(d$tokens), numeric(1))
  avg_len <- sum(lens) / n
  df <- table(unlist(lapply(docs, function(d) unique(d$tokens))))   # in how many chunks each word appears
  scores <- vapply(seq_len(n), function(j) {
    tf <- table(docs[[j]]$tokens)
    score <- 0
    for (w in q) {
      if (!is.na(tf[w])) {
        idf <- log(1 + (n - df[[w]] + 0.5) / (df[[w]] + 0.5))
        score <- score + idf * tf[[w]] * (K1 + 1) / (tf[[w]] + K1 * (1 - B + B * lens[j] / avg_len))
      }
    }
    score
  }, numeric(1))
  pages <- vapply(docs, function(d) d$page, numeric(1))
  results <- list()
  seen <- character(0)
  for (j in order(-scores, pages)) {               # best score first; ties: the earlier page first
    if (scores[j] <= 0 || length(results) == top_k) break
    if (docs[[j]]$text %in% seen) next
    seen <- c(seen, docs[[j]]$text)
    results[[length(results) + 1]] <- list(page = docs[[j]]$page, section = docs[[j]]$section,
                                           score = round(scores[j], 3), text = docs[[j]]$text)
  }
  list(query = query, results = results)
}

# First line (0-based) of each chunk: every STRIDE lines, plus one last (shorter) chunk so the end of the
# page is covered.
window_starts <- function(n) {
  starts <- seq(0, max(n - WINDOW, 0), by = STRIDE)
  last <- starts[length(starts)]
  if (last + WINDOW < n) starts <- c(starts, last + STRIDE)
  starts
}
