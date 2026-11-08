# Chapter 21: is the R note identical to the Python note, character for character, in every period?
source("r/taragent/load.R")

python <- if (nzchar(Sys.which("python3"))) Sys.which("python3") else Sys.which("python")
code <- paste0("import sys, json; sys.path.insert(0, 'python'); ",
               "from tar_agent.tools.note import draft_surveillance_note as d; ",
               "print(json.dumps([d(p)['note_markdown'] for p in range(1, 13)]))")
py_notes <- fromJSON(paste(system2(python, c("-c", shQuote(code)), stdout = TRUE), collapse = ""))
same <- vapply(1:12, function(p) identical(draft_surveillance_note(p)$note_markdown, py_notes[p]), logical(1))
cat(sprintf("Periods with identical notes: %d of 12\n", sum(same)))
