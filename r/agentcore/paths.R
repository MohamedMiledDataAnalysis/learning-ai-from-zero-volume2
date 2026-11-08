# Find the repository root (the folder that contains requirements.txt), so scripts and
# tests work whatever the current folder is.
repo_root <- function(start = getwd()) {
  dir <- normalizePath(start)
  while (!file.exists(file.path(dir, "requirements.txt"))) {
    parent <- dirname(dir)
    if (parent == dir) stop("cannot find the repository root (requirements.txt)")
    dir <- parent
  }
  dir
}
