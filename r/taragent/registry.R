# The tool registry (R version of tar_agent/registry.py): what the model is told about
# each tool, and how a call is run. The descriptions and schemas are word for word the
# same as in Python, so the model sees exactly the same tools from either language.

PERIOD <- list(type = "integer", minimum = 1, maximum = 12,
               description = "Collection period: 1 = January 2026, 12 = December 2026.")

TOOLS <- list(
  validate_loan_tape = list(
    fun = function() validate_loan_tape(),
    description = paste("Check the cut-off loan tape received from the originator. Lists every data problem",
                        "(duplicates, missing values, impossible values, wrong names) with a suggested fix, and",
                        "says whether the cleaned tape reconciles with the initial pool balance."),
    parameters = list(type = "object", properties = named_list(), required = list())
  ),
  stratify_pool = list(
    fun = stratify_pool,
    description = paste("Split the pool into groups and total a measure in each group. Use measure",
                        "'balance_90plus' to find where 90+ day arrears are concentrated."),
    parameters = list(type = "object", properties = list(
      by = list(type = "string", enum = as.list(FIELDS), description = "The field to group by."),
      period = list(type = "integer", minimum = 0, maximum = 12,
                    description = "0 = cut-off date (31 December 2025); 1-12 = end of that collection period."),
      measure = list(type = "string", enum = as.list(MEASURES), description = "What to total in each group.")
    ), required = list("by"))
  ),
  run_trigger_tests = list(
    fun = run_trigger_tests,
    description = paste("Recompute the cumulative default ratio and the 90+ day arrears ratio from the loan-level",
                        "data for one period, compare them with the prospectus limits and with the investor report,",
                        "and say whether principal is paid pro rata or sequentially."),
    parameters = list(type = "object", properties = list(period = PERIOD), required = list("period"))
  ),
  search_prospectus = list(
    fun = search_prospectus,
    description = paste("Search the prospectus and return the most relevant passages with their page numbers.",
                        "Use it for any question about the deal's rules: definitions, limits, fees, priority of",
                        "payments. Answer only from the passages returned and cite the page."),
    parameters = list(type = "object", properties = list(
      query = list(type = "string", description = "The question or key words to search for."),
      top_k = list(type = "integer", minimum = 1, maximum = 5, description = "Number of passages (default 3).")
    ), required = list("query"))
  ),
  draft_surveillance_note = list(
    fun = draft_surveillance_note,
    description = paste("Draft the monthly surveillance note for one period: pool movements, trigger results,",
                        "the main driver of arrears and the note balances. All figures are computed, not estimated."),
    parameters = list(type = "object", properties = list(period = PERIOD), required = list("period"))
  )
)

# The list sent to the model with every request.
tool_schemas <- function() {
  lapply(names(TOOLS), function(name) {
    t <- TOOLS[[name]]
    list(type = "function", `function` = list(name = name, description = t$description,
                                             parameters = t$parameters))
  })
}

# Run one tool call and return its result as JSON text.
# Errors are returned as text too, never raised: the model reads the error and can
# correct its call on the next step instead of the whole agent stopping.
call_tool <- function(name, arguments = NULL) {
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
  if (!(name %in% names(TOOLS))) {
    return(to_json(list(error = sprintf("unknown tool '%s'. Available tools: %s", name,
                                        py_list(sort(names(TOOLS), method = "radix"))))))
  }
  allowed <- names(TOOLS[[name]]$parameters$properties)
  unknown <- setdiff(names(arguments), allowed)
  if (length(unknown) > 0) {
    return(to_json(list(error = sprintf("unknown argument(s) %s for %s. Allowed: %s", py_list(unknown), name,
                                        py_list(sort(allowed, method = "radix"))))))
  }
  result <- tryCatch(do.call(TOOLS[[name]]$fun, arguments), error = function(e) e)
  if (inherits(result, "error")) return(to_json(list(error = conditionMessage(result))))
  to_json(result)
}
