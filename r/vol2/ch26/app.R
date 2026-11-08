# The Prospectus Analyser. Run it from the repository root:
#
#   Rscript -e "shiny::runApp('r/vol2/ch26', launch.browser = TRUE)"
#
# The repository root is found by climbing from the current folder until requirements.txt
# appears, so the app also starts from RStudio's Run App button or from the root itself.
library(shiny)

options(shiny.maxRequestSize = 50 * 1024^2)        # uploads up to 50 MB
root <- local({
  d <- normalizePath(getwd())
  while (!file.exists(file.path(d, "requirements.txt")) && dirname(d) != d) d <- dirname(d)
  d
})
local({
  old <- setwd(root)
  on.exit(setwd(old))
  source("r/taragent/load_analyser.R")
})
for (f in c("analyser_logic.R", "app_ui.R", "app_server.R")) source(file.path(root, "r", "vol2", "ch26", f))

shinyApp(ui, server)
