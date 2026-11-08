# Load the structured finance agent in R: the shared agent core, then every part of taragent.
#
#   source("r/taragent/load.R")      # from the repository root
#
# After this line, every function of the agent is available: validate_loan_tape(),
# stratify_pool(), run_trigger_tests(), search_prospectus(), draft_surveillance_note(),
# call_tool(), ask(), run_evaluation(), export_monthly_pack(), run_surveillance().

local({
  find_root <- function(dir = getwd()) {
    dir <- normalizePath(dir)
    while (!file.exists(file.path(dir, "requirements.txt"))) {
      if (dirname(dir) == dir) stop("run R from inside the repository folder")
      dir <- dirname(dir)
    }
    dir
  }
  root <- find_root()
  files <- c("agentcore/paths.R", "agentcore/loop.R", "agentcore/brains.R",
             "taragent/data.R", "taragent/tools/loan_tape.R", "taragent/tools/stratify.R",
             "taragent/tools/triggers.R", "taragent/tools/prospectus.R", "taragent/tools/note.R",
             "taragent/registry.R", "taragent/agent.R", "taragent/evaluate.R", "taragent/export.R",
             "taragent/agentic.R")
  for (f in files) {
    path <- file.path(root, "r", f)
    if (!file.exists(path)) stop("missing file: ", path, call. = FALSE)
    sys.source(path, envir = globalenv())
  }
})
# The prospectus, the note and the recordings contain "£" and "—": read them as UTF-8. Only change the
# session's character setting when it is not UTF-8 already (it is on most Linux and macOS set-ups).
if (!isTRUE(l10n_info()[["UTF-8"]])) invisible(suppressWarnings(Sys.setlocale("LC_CTYPE", "C.UTF-8")))
