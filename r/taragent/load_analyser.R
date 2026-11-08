# Load the structured finance agent and the Prospectus Analyser tools of Volume 2 Part E.
#
#   source("r/taragent/load_analyser.R")      # from the repository root
#
# After this line: everything of load.R, plus read_pages(), search_document(), extract_deal_terms(),
# analyse_deal_terms(), simulated_model_brain() and call_analyser_tool().

source(file.path(local({
  dir <- normalizePath(getwd())
  while (!file.exists(file.path(dir, "requirements.txt"))) {
    if (dirname(dir) == dir) stop("run R from inside the repository folder")
    dir <- dirname(dir)
  }
  dir
}), "r", "taragent", "load.R"))
for (f in c("tools/document.R", "tools/extract.R", "tools/extract_sim.R", "tools/analyse.R", "registry_analyser.R")) {
  sys.source(file.path(repo_root(), "r", "taragent", f), envir = globalenv(), keep.source = FALSE)
}
