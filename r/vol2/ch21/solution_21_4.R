# Solution 21.4: the headline of the note in every period of 2026.
source("r/taragent/load.R")

for (period in 1:12) {
  note <- draft_surveillance_note(period)$note_markdown
  headline <- strsplit(note, "**", fixed = TRUE)[[1]][2]
  cat(sprintf("%2d  %s\n", period, headline))
}
