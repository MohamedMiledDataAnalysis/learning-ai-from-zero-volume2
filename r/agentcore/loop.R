# The agent loop: the controller that every agent in this book shares (R version).
#
#   1. Send the goal, the instructions and the tool descriptions to the brain.
#   2. Read the reply. If it asks for tools, run them and add the results to memory.
#   3. Go back to 1 with the longer memory.
#   4. Stop when the brain gives a final answer, or when the step limit is reached.
#
# It mirrors python/agent_core/loop.py line for line. A brain is a list with one
# function, next_step(memory, schemas), that returns
#   list(content = "text", tool_calls = list(list(name = "...", arguments = list(...))))
# An empty tool_calls list means the brain has given its final answer.

library(jsonlite)

run_agent <- function(goal, brain, schemas, call_tool, system_prompt,
                      max_steps = 10, log = function(msg) cat(msg, "\n", sep = "")) {
  memory <- list(
    list(role = "system", content = system_prompt),
    list(role = "user", content = goal)
  )
  steps <- list()
  for (step in seq_len(max_steps)) {
    reply <- brain$next_step(memory, schemas)              # the brain chooses the next step
    calls <- reply$tool_calls
    if (is.null(calls)) calls <- list()
    content <- if (is.null(reply$content)) "" else reply$content
    memory[[length(memory) + 1]] <- list(role = "assistant", content = content,
                                         tool_calls = lapply(calls, function(tc) list(`function` = tc)))
    if (length(calls) == 0) {                               # no tool requested: final answer
      log(sprintf("[step %d] final answer", step))
      steps[[length(steps) + 1]] <- list(step = step, type = "answer")
      return(list(answer = content, stopped_because = "final answer", steps = steps, memory = memory))
    }
    for (tc in calls) {                                     # run every tool the brain asked for
      args <- if (is.null(tc$arguments)) named_list() else tc$arguments
      result <- call_tool(tc$name, args)
      log(sprintf("[step %d] tool %s(%s) -> %s", step, tc$name, to_json(args), short_text(result)))
      steps[[length(steps) + 1]] <- list(step = step, type = "tool", name = tc$name,
                                         arguments = args, result = result)
      memory[[length(memory) + 1]] <- list(role = "tool", tool_name = tc$name, content = result)
    }
  }
  log(sprintf("[stop] step limit of %d reached without a final answer", max_steps))
  list(answer = NULL, stopped_because = "step limit", steps = steps, memory = memory)
}

# An empty named list: written as {} in JSON (an unnamed empty list would be []).
named_list <- function() setNames(list(), character(0))

# JSON text in the same style as Python's json.dumps: single values are not wrapped in [ ].
to_json <- function(x) {
  if (is.list(x) && length(x) == 0 && !is.null(names(x))) return("{}")
  as.character(jsonlite::toJSON(x, auto_unbox = TRUE, null = "null", na = "null", digits = NA))
}

short_text <- function(text, n = 90) {
  text <- gsub("\n", " ", text, fixed = TRUE)
  if (nchar(text) <= n) text else paste0(substr(text, 1, n - 3), "...")
}
