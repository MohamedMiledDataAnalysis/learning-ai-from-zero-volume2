# Chapter 20: the agent's memory after one question — every message, in order.
source("r/taragent/load.R")

run <- ask("Which region holds most of the 90+ day arrears in October 2026?", "rules", log = function(m) invisible(NULL))
for (i in seq_along(run$memory)) {
  m <- run$memory[[i]]
  text <- m$content
  if (length(m$tool_calls) > 0) {
    text <- paste("asks for", paste(vapply(m$tool_calls, function(c) paste0(c$`function`$name, to_json(c$`function`$arguments)), ""),
                                    collapse = ", "))
  }
  text <- gsub("\n", " ", text, fixed = TRUE)
  cat(sprintf("%d. %-9s %s%s\n", i, m$role, substr(text, 1, 82), if (nchar(text) > 82) "..." else ""))
}
cat("Stopped because:", run$stopped_because, "\n")
