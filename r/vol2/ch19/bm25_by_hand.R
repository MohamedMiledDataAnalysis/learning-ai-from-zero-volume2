# Chapter 19: the BM25 score of one word in one chunk, step by step, in R.
source("r/taragent/load.R")

docs <- chunks()
word <- "arrears"
chunk <- Filter(function(c) grepl("must not exceed 1.25%", c$text, fixed = TRUE), docs)[[1]]
n <- length(docs)
df <- sum(vapply(docs, function(d) word %in% d$tokens, logical(1)))
tf <- sum(chunk$tokens == word)
avg_len <- mean(vapply(docs, function(d) length(d$tokens), numeric(1)))
len <- length(chunk$tokens)
idf <- log(1 + (n - df + 0.5) / (df + 0.5))
weight <- tf * (K1 + 1) / (tf + K1 * (1 - B + B * len / avg_len))
cat(sprintf("N (chunks) = %d, df (chunks containing '%s') = %d\n", n, word, df))
cat(sprintf("idf = ln(1 + (%d - %d + 0.5) / (%d + 0.5)) = %.4f\n", n, df, df, idf))
cat(sprintf("tf = %d, chunk length = %d, average length = %.2f\n", tf, len, avg_len))
cat(sprintf("tf part = %d x %.1f / (%d + %.1f x (1 - %.2f + %.2f x %d / %.2f)) = %.4f\n",
            tf, K1 + 1, tf, K1, B, B, len, avg_len, weight))
cat(sprintf("score for '%s' = %.4f x %.4f = %.4f\n", word, idf, weight, idf * weight))
