# Install every R package this book uses, and only those.
#
#   Rscript r/install_packages.R
#
# The book was tested with R 4.3.3 and the versions below. Newer versions are expected to work;
# if an output differs from the book, install the version listed here with
#   remotes::install_version("<package>", "<version>")
#
# | Package    | Version tested | Used for                                                        |
# |------------|----------------|-----------------------------------------------------------------|
# | jsonlite   | 1.8.8          | JSON: tool calls, recordings, deal terms (both volumes)          |
# | httr2      | 1.0.0          | Talking to Ollama over HTTP (Vol. 1 ch. 25 onwards, Vol. 2)      |
# | pdftools   | 3.4.0          | Reading the prospectus PDFs (Vol. 1 ch. 27, Vol. 2 ch. 19, 26)   |
# | ggplot2    | 3.4.4          | Charts (Vol. 1 Part II, Vol. 2 ch. 26)                           |
# | rpart      | 4.1.23         | Decision trees (Vol. 1 ch. 10)                                   |
# | openxlsx   | 4.2.5.2        | Excel export (Vol. 2 ch. 23, 26)                                  |
# | shiny      | 1.8.0          | The two Shiny apps (Vol. 2 ch. 25, 26)                           |
# | bslib      | 0.6.1          | Layout of the Shiny apps                                         |
# | DT         | 0.31           | Tables in the Shiny apps                                         |
# | commonmark | 1.9.1          | Showing the surveillance note as HTML (Vol. 2 ch. 25)            |
# | testthat   | 3.2.1          | The tests in r/tests                                             |
# | withr      | 2.5.0          | One Shiny test                                                   |
#
# rpart ships with R; it is listed so that a minimal R installation still gets it.
# Some R tests and scripts compare R with Python, so they also need Python and the packages in
# requirements.txt (pip install -r requirements.txt).

packages <- c("jsonlite", "httr2", "pdftools", "ggplot2", "rpart", "openxlsx",
              "shiny", "bslib", "DT", "commonmark", "testthat", "withr")
missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  install.packages(missing, repos = "https://cloud.r-project.org")
} else {
  cat("All", length(packages), "packages are already installed.\n")
}
