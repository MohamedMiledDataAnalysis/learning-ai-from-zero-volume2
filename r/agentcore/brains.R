# Brains: the part of the agent that decides the next step (R version).
#
# Every brain is a list with one function, next_step(memory, schemas), returning
#   list(content = "text for the user", tool_calls = list(list(name = ..., arguments = list(...))))
#
# rule_brain       plain if/else rules written by you: no AI, fully predictable
# ollama_brain     a local language model served by Ollama (free, runs on your computer)
# recording_brain  wraps another brain and saves every reply to a file
# replay_brain     plays back a saved file: the same replies, in the same order, every time
#
# Recordings use the same JSON Lines format as python/agent_core/brains.py, so a
# recording made from Python can be replayed from R and the other way round.

library(jsonlite)
library(httr2)

DEFAULT_MODEL <- "qwen2.5:7b"     # pinned: the book's transcripts were recorded with this model
DEFAULT_OPTIONS <- list(temperature = 0, seed = 42, num_ctx = 8192)   # num_ctx: fixed context window

rule_brain <- function(rules) {
  list(next_step = function(memory, schemas) rules(memory))
}

ollama_brain <- function(model = DEFAULT_MODEL, options = DEFAULT_OPTIONS,
                         host = Sys.getenv("OLLAMA_HOST", "http://localhost:11434")) {
  if (!grepl("^https?://", host)) host <- paste0("http://", host)   # OLLAMA_HOST may omit the scheme
  list(next_step = function(memory, schemas) {
    body <- list(model = model, messages = memory, tools = schemas, options = options, stream = FALSE)
    response <- request(paste0(host, "/api/chat")) |>
      req_body_raw(to_json(body), type = "application/json") |>
      req_error(body = function(resp) tryCatch(resp_body_json(resp)$error, error = function(e) NULL)) |>
      req_timeout(600) |>
      req_perform()
    message <- resp_body_json(response, simplifyVector = FALSE)$message
    calls <- lapply(message$tool_calls, function(tc) {
      args <- tc$`function`$arguments
      if (is.character(args)) args <- fromJSON(args, simplifyVector = FALSE)
      if (length(args) == 0) args <- named_list()
      list(name = tc$`function`$name, arguments = args)
    })
    list(content = if (is.null(message$content)) "" else message$content, tool_calls = calls)
  })
}

recording_brain <- function(inner, path) {
  # The file is written only after a reply has arrived, and replaced in one step, so a failed run
  # (for example with Ollama not running) never leaves an empty or half-written recording behind.
  lines <- character(0)
  list(next_step = function(memory, schemas) {
    reply <- inner$next_step(memory, schemas)
    lines <<- c(lines, reply_to_json(reply))
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    partial <- paste0(path, ".partial")
    writeLines(lines, partial, useBytes = TRUE)
    file.rename(partial, path)
    reply
  })
}

# TRUE when a recording exists and is not empty.
recording_ready <- function(path) file.exists(path) && file.size(path) > 0

replay_brain <- function(path) {
  if (!recording_ready(path)) {
    stop(sprintf("no recording at %s: run once with --mode record (needs Ollama)", path))
  }
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  replies <- lapply(lines[nchar(lines) > 0], json_to_reply)
  position <- 0
  list(next_step = function(memory, schemas) {
    position <<- position + 1
    if (position > length(replies)) {
      stop("the recording has no more replies: the run has gone differently from the recording")
    }
    replies[[position]]
  })
}

make_brain <- function(mode, recording, rules = NULL, model = DEFAULT_MODEL) {
  switch(mode,
         rules = rule_brain(rules),
         live = ollama_brain(model),
         record = recording_brain(ollama_brain(model), recording),
         replay = replay_brain(recording),
         stop("mode must be rules, live, record or replay"))
}

# One reply as one line of JSON, in the same JSON Lines format as Python (spacing inside may differ).
reply_to_json <- function(reply) {
  calls <- lapply(reply$tool_calls, function(tc) {
    list(name = tc$name, arguments = if (length(tc$arguments) == 0) named_list() else tc$arguments)
  })
  paste0('{"content": ', to_json(if (is.null(reply$content)) "" else reply$content),
         ', "tool_calls": ', if (length(calls) == 0) "[]" else to_json(calls), "}")
}

json_to_reply <- function(line) {
  x <- fromJSON(line, simplifyVector = FALSE)
  calls <- lapply(x$tool_calls, function(tc) {
    list(name = tc$name, arguments = if (length(tc$arguments) == 0) named_list() else tc$arguments)
  })
  list(content = if (is.null(x$content)) "" else x$content, tool_calls = calls)
}
