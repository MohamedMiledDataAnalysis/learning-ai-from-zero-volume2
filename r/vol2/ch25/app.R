# The surveillance app. Run it from the repository root:
#
#   Rscript -e "shiny::runApp('r/vol2/ch25', launch.browser = TRUE)"
#
# The repository root is found by climbing from the current folder until requirements.txt
# appears, so the app also starts from RStudio's Run App button or from the root itself.
library(shiny)

root <- local({
  d <- normalizePath(getwd())
  while (!file.exists(file.path(d, "requirements.txt")) && dirname(d) != d) d <- dirname(d)
  d
})
local({
  old <- setwd(root)
  on.exit(setwd(old))
  source("r/taragent/load.R")
})
source(file.path(root, "r", "vol2", "ch25", "app_ui.R"))
source(file.path(root, "r", "vol2", "ch25", "app_server.R"))

shinyApp(ui, server)
