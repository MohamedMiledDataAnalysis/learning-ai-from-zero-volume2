# Chapter 21: R's number formats against Python's, on values that sit exactly on a rounding edge.
source("r/taragent/load.R")

python <- if (nzchar(Sys.which("python3"))) Sys.which("python3") else Sys.which("python")
code <- "print(' '.join(f'{x:.2f}' for x in (0.125, 2.675)), ' '.join(f'{x:,.0f}' for x in (2500.5, 2501.5)))"
py <- strsplit(system2(python, c("-c", shQuote(code)), stdout = TRUE), " ")[[1]]
r <- c(sprintf("%.2f", c(0.125, 2.675)), formatC(c(2500.5, 2501.5), format = "f", digits = 0, big.mark = ","))
print(data.frame(value = c("0.125", "2.675", "2500.5", "2501.5"), format = c(".2f", ".2f", ",.0f", ",.0f"),
                 R = r, Python = py), row.names = FALSE)
