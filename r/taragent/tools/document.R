# Read any prospectus PDF the user uploads, and search it (R version of tar_agent/tools/document.py).
#
# Tool 4 (prospectus.R) reads the Thames prospectus only. The Prospectus Analyser of Volume 2
# Part E must read a file it has never seen: these functions take any PDF path. The cleaning
# rules are the same as in Python, so pdftools (R) and pypdf (Python) give the same words.

suppressPackageStartupMessages(library(pdftools))

PAGE_NUMBER <- "^(?:Page [0-9]+|-\\s?[0-9]+\\s?-|[0-9]+)$"

# Clean one line of PDF text: one space between words, split capitals joined back ("T est"),
# no space before , ; : . ) % and none after (.
normalise_line <- function(line) {
  line <- gsub("[   ]", " ", line, perl = TRUE)
  line <- trimws(gsub("\\s+", " ", line, perl = TRUE))
  # Only T, V, W and Y are joined: A and I are English words, and B, C, D and Z name classes of notes.
  line <- gsub("\\b([TVWY]) ([a-z]{2,})", "\\1\\2", line, perl = TRUE)
  line <- gsub(" ([,;:.)%\u201d])", "\\1", line, perl = TRUE)
  gsub("\\( ", "(", line, perl = TRUE)
}

# The clean lines of each page: a list, element 1 is page 1.
read_pages <- function(pdf_path) {
  pdf_path <- normalizePath(as.character(pdf_path), mustWork = FALSE)
  if (!file.exists(pdf_path)) stop("no PDF at ", pdf_path, call. = FALSE)
  key <- paste("pages", pdf_path, file.mtime(pdf_path))
  cached(key, function() {
    raw <- lapply(pdf_text(pdf_path), function(text) {
      lines <- normalise_line(strsplit(text, "\n", fixed = TRUE)[[1]])
      lines[nchar(lines) > 0]
    })
    # The running header: the first line that repeats at the top of at least half of the pages.
    firsts <- vapply(Filter(length, raw), function(l) l[1], character(1))
    header <- NA_character_
    if (length(firsts)) {
      counts <- table(factor(firsts, levels = unique(firsts)))     # ties: the first one met wins, as in Python
      best <- names(counts)[which.max(counts)]
      if (max(counts) >= max(2, length(raw) %/% 2)) header <- best
    }
    lapply(raw, function(lines) lines[!(lines %in% header) & !grepl(PAGE_NUMBER, lines, perl = TRUE)])
  })
}

# Each page as one line of text (its clean lines joined by spaces).
page_texts <- function(pdf_path) vapply(read_pages(pdf_path), paste, character(1), collapse = " ")

# Chunks of WINDOW lines every STRIDE lines on every page, as in Tool 4.
document_chunks <- function(pdf_path) {
  out <- list()
  pages <- read_pages(pdf_path)
  for (number in seq_along(pages)) {
    lines <- pages[[number]]
    if (!length(lines)) next
    for (start in window_starts(length(lines))) {
      body <- paste(lines[(start + 1):min(start + WINDOW, length(lines))], collapse = " ")
      out[[length(out) + 1]] <- list(page = number, text = body, tokens = tokens(body))
    }
  }
  out
}

# Tool entry point: the top_k chunks of any PDF that best match the query, with their page numbers.
search_document <- function(pdf_path, query, top_k = 3) {
  docs <- document_chunks(pdf_path)
  q <- tokens(query)
  if (length(q) == 0) stop("the query has no searchable words", call. = FALSE)
  if (length(docs) == 0) stop("the PDF has no text (a scanned document needs OCR first)", call. = FALSE)
  n <- length(docs)
  lens <- vapply(docs, function(d) length(d$tokens), numeric(1))
  avg_len <- sum(lens) / n
  df <- table(unlist(lapply(docs, function(d) unique(d$tokens))))
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
  for (j in order(-scores, pages)) {
    if (scores[j] <= 0 || length(results) == top_k) break
    if (docs[[j]]$text %in% seen) next
    seen <- c(seen, docs[[j]]$text)
    results[[length(results) + 1]] <- list(page = docs[[j]]$page, score = round(scores[j], 3), text = docs[[j]]$text)
  }
  list(query = query, results = results)
}
