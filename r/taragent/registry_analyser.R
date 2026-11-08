# The Prospectus Analyser's tools (R version of the ANALYSER_TOOLS part of tar_agent/registry.py).
# They have their own registry, so the surveillance agent of Parts C and D keeps exactly its five
# tools. Descriptions and schemas are word for word the same as in Python.

PDF_PATH <- list(type = "string", description = "Path of the prospectus PDF uploaded by the user.")

ANALYSER_TOOLS <- list(
  extract_deal_terms = list(
    fun = function(pdf_path) extract_deal_terms(pdf_path, layer = "rules"),
    description = paste("Extract the deal terms of a prospectus PDF with the rules layer: parties, dates, pool",
                        "balance, classes of notes, reserve funds, priority of payments, triggers, eligibility",
                        "criteria and risk retention. Every value has its page, a quote and a grounding flag."),
    parameters = list(type = "object", properties = list(pdf_path = PDF_PATH), required = list("pdf_path"))
  ),
  analyse_deal_terms = list(
    fun = function(pdf_path) analyse_deal_terms(extract_deal_terms(pdf_path, layer = "rules")),
    description = paste("Credit enhancement of each class, five consistency checks and the priority of payments",
                        "of a prospectus PDF, computed from the extracted terms."),
    parameters = list(type = "object", properties = list(pdf_path = PDF_PATH), required = list("pdf_path"))
  ),
  search_document = list(
    fun = search_document,
    description = paste("Search a prospectus PDF and return the most relevant passages with their page numbers.",
                        "Answer only from the passages returned and cite the page."),
    parameters = list(type = "object", properties = list(
      pdf_path = PDF_PATH,
      query = list(type = "string", description = "The question or key words to search for."),
      top_k = list(type = "integer", minimum = 1, maximum = 5, description = "Number of passages (default 3).")
    ), required = list("pdf_path", "query"))
  )
)

analyser_schemas <- function() {
  lapply(names(ANALYSER_TOOLS), function(name) {
    t <- ANALYSER_TOOLS[[name]]
    list(type = "function", `function` = list(name = name, description = t$description, parameters = t$parameters))
  })
}

# The same rules as call_tool(), for the analyser's registry.
call_analyser_tool <- function(name, arguments = NULL) {
  if (is.character(arguments)) {
    parsed <- tryCatch(
      if (nchar(trimws(arguments)) == 0) named_list() else fromJSON(arguments, simplifyVector = FALSE),
      error = function(e) e)
    if (inherits(parsed, "error")) {
      return(to_json(list(error = paste("arguments are not valid JSON:", conditionMessage(parsed)))))
    }
    arguments <- parsed
  }
  if (is.null(arguments)) arguments <- named_list()
  if (!(name %in% names(ANALYSER_TOOLS))) {
    return(to_json(list(error = sprintf("unknown tool '%s'. Available tools: %s", name,
                                        py_list(sort(names(ANALYSER_TOOLS), method = "radix"))))))
  }
  allowed <- names(ANALYSER_TOOLS[[name]]$parameters$properties)
  unknown <- setdiff(names(arguments), allowed)
  if (length(unknown) > 0) {
    return(to_json(list(error = sprintf("unknown argument(s) %s for %s. Allowed: %s", py_list(unknown), name,
                                        py_list(sort(allowed, method = "radix"))))))
  }
  result <- tryCatch(do.call(ANALYSER_TOOLS[[name]]$fun, arguments), error = function(e) e)
  if (inherits(result, "error")) return(to_json(list(error = conditionMessage(result))))
  to_json(result)
}
