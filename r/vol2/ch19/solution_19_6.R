# Solution 19.6: a small stemmer makes "eligible" and "eligibility" the same word.
source("r/taragent/load.R")

# Cut a few common English endings, longest first, keeping at least four letters.
stem <- function(words) {
  for (ending in c("ibility", "ility", "ible", "able", "ies", "s")) {
    cut <- endsWith(words, ending) & nchar(words) - nchar(ending) >= 4
    words[cut] <- substr(words[cut], 1, nchar(words[cut]) - nchar(ending))
  }
  words
}
cat("Stems:", stem(c("eligible", "eligibility", "loans", "criteria")), "\n\n")

# Score every chunk with stemmed words: the same BM25 formula as search_prospectus().
docs <- chunks()
doc_tokens <- lapply(docs, function(d) stem(d$tokens))
q <- stem(tokens("Which loans were eligible?"))
n <- length(docs)
lens <- lengths(doc_tokens)
df <- table(unlist(lapply(doc_tokens, unique)))
scores <- vapply(seq_len(n), function(j) {
  tf <- table(doc_tokens[[j]])
  sum(vapply(q, function(w) if (is.na(tf[w])) 0 else
    log(1 + (n - df[[w]] + 0.5) / (df[[w]] + 0.5)) * tf[[w]] * (K1 + 1) /
      (tf[[w]] + K1 * (1 - B + B * lens[j] / mean(lens))), 0))
}, 0)
for (j in order(-scores)[1:3]) {
  cat(sprintf("page %d  score %6.3f  %s...\n", docs[[j]]$page, scores[j], substr(docs[[j]]$text, 1, 60)))
}
