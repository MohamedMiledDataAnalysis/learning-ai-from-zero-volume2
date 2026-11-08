# Exercise 26.8: what the analyser does with a scanned prospectus (a PDF made of images, with no text layer).
#   Rscript r/vol2/ch26/solutions/ex_26_8_scanned.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })

# Make a "scanned" copy of page 1 of Thames: render it as a picture, then put the picture in a new PDF.
img <- pdftools::pdf_render_page(sample_path("thames", "pdf"), page = 1, dpi = 60)
scanned <- tempfile(fileext = ".pdf")
grDevices::pdf(scanned, width = 8.27, height = 11.69)
graphics::par(mar = c(0, 0, 0, 0)); graphics::plot.new()
pixels <- aperm(array(as.integer(img), dim(img)), c(3, 2, 1)) / 255   # bitmap (colour, x, y) -> picture (y, x, colour)
graphics::rasterImage(grDevices::as.raster(pixels), 0, 0, 1, 1)
invisible(grDevices::dev.off())

cat("Is it a PDF?", is.null(check_pdf(scanned)), "\n")
cat("Characters of text on page 1:", nchar(pdftools::pdf_text(scanned)[1]), "\n")
answer <- ask_document(scanned, "What is the pool balance?", "rules")
cat("Ask tab says:", answer$answer, "\n")
run <- run_extraction(scanned, "rules")
cat("Extraction:", if (is.null(run$terms)) run$message else coverage_text(run$terms), "\n")
