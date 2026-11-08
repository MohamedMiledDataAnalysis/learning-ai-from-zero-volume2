# Solution 24.6: R monitors September, Python monitors October with the same memory file.
source("r/taragent/load.R")

folder <- tempfile()
memory <- file.path(folder, "memory")
r9 <- run_surveillance(9, memory_dir = memory, out_dir = file.path(folder, "out"), approve = TRUE,
                       log = function(m) invisible(NULL))
cat("R wrote the memory for period 9.\n")
python <- if (nzchar(Sys.which("python3"))) Sys.which("python3") else Sys.which("python")
code <- sprintf(paste0("import sys; sys.path.insert(0, 'python'); from tar_agent.agentic import run_surveillance; ",
                       "r = run_surveillance(10, memory_dir=%s, out_dir=%s, approve=False, log=lambda m: None); ",
                       "print('Python compared October with September:'); [print('  ' + c) for c in r['changes']]"),
                shQuote(memory), shQuote(file.path(folder, "out")))
cat(system2(python, c("-c", shQuote(code)), stdout = TRUE), sep = "\n")
unlink(folder, recursive = TRUE)
