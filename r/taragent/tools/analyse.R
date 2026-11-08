# Tool 7 — analyse extracted deal terms (R version of tar_agent/tools/analyse.py):
# credit enhancement per class, five consistency checks, and the waterfall list for diagrams.
# Which reserves count (as in Python): a reserve counts by what the prospectus says it can pay, never by its
# name. It counts only when it can pay principal or cover losses (can_cover_losses is TRUE); a reserve that pays
# only fees and interest is liquidity support, and a reserve whose purpose was not found is not counted either.
# A reserve sized on a list of classes (its basis) supports only those classes, so Severn's General Reserve
# Fund (Classes A to D) does not cover Class Z.

fv <- function(f) if (is.list(f)) f$value else NA
is_num <- function(x) is.numeric(x) && length(x) == 1 && !is.na(x)

credit_enhancement <- function(terms) {
  classes <- Filter(function(c) is_num(fv(c$balance)), terms$classes)
  total <- sum(vapply(classes, function(c) fv(c$balance), numeric(1)))
  if (!length(classes) || total == 0) return(list())
  loss_reserves <- Filter(function(r) is_num(fv(r$amount)) && isTRUE(fv(r$can_cover_losses)), terms$reserve_funds)
  supports <- function(r, name) {
    basis <- fv(r$basis)
    !is.list(basis) || !length(basis) || name %in% unlist(basis)
  }
  lapply(seq_along(classes), function(i) {
    c <- classes[[i]]
    below <- if (i < length(classes)) sum(vapply(classes[(i + 1):length(classes)], function(x) fv(x$balance), numeric(1))) else 0
    reserves <- sum(vapply(Filter(function(r) supports(r, fv(c$name)), loss_reserves), function(r) fv(r$amount), numeric(1)))
    list(class = fv(c$name), balance = fv(c$balance), share_of_notes = round(fv(c$balance) / total, 6),
         subordination = round(below / total, 6), reserve_support = round(reserves / total, 6),
         credit_enhancement = round((below + reserves) / total, 6),
         margin = fv(c$margin), rating = fv(c$rating))
  })
}

# For each reserve fund: counted in credit enhancement or not, and why.
reserve_treatment <- function(terms) {
  lapply(terms$reserve_funds, function(r) {
    cover <- fv(r$can_cover_losses)
    reason <- if (isTRUE(cover)) "counted: it can pay principal or cover losses"
              else if (identical(cover, FALSE)) "not counted: it pays only fees and interest (liquidity support)"
              else "reserve not counted: what it can pay was not found"
    list(name = fv(r$name), amount = fv(r$amount), counted = isTRUE(cover), reason = reason)
  })
}

basis_total <- function(reserve, classes) {
  basis <- fv(reserve$basis)
  keep <- Filter(function(c) is_num(fv(c$balance)), classes)
  if (is.list(basis) && length(basis)) keep <- Filter(function(c) fv(c$name) %in% unlist(basis), keep)
  sum(vapply(keep, function(c) fv(c$balance), numeric(1)))
}

fmt_money <- function(x) formatC(x, format = "f", digits = 2, big.mark = ",")

consistency_checks <- function(terms, ce) {
  checks <- list()
  add <- function(name, passed, detail) checks[[length(checks) + 1]] <<- list(check = name, passed = passed, detail = detail)
  pool <- fv(terms$pool_balance)
  notes <- sum(vapply(ce, function(r) r$balance, numeric(1)))
  if (!is_num(pool) || !length(ce)) add("classes add up to the pool", NA, "pool balance or classes missing")
  else add("classes add up to the pool", abs(notes - pool) <= 1,
           sprintf("notes %s against pool %s (difference %s)", fmt_money(notes), fmt_money(pool), fmt_money(notes - pool)))
  margins <- unlist(Filter(is_num, lapply(ce, function(r) r$margin)))
  if (length(margins) < 2) add("margins rise as seniority falls", NA, "fewer than two margins")
  else add("margins rise as seniority falls", all(diff(margins) >= 0),
           paste(sprintf("%.2f%%", margins * 100), collapse = " < "))
  ces <- vapply(ce, function(r) r$credit_enhancement, numeric(1))
  if (length(ces) < 2) add("credit enhancement highest for Class A", NA, "fewer than two classes")
  else add("credit enhancement highest for Class A", all(diff(ces) < 0),
           paste(vapply(ce, function(r) sprintf("%s %.2f%%", r$class, r$credit_enhancement * 100), character(1)), collapse = " > "))
  res <- Filter(function(r) is_num(fv(r$amount)) && is_num(fv(r$percent)), terms$reserve_funds)
  if (!length(res) || !length(ce)) add("reserve funds match their percentage", NA, "no reserve fund with both an amount and a percentage")
  else {
    ok <- TRUE
    details <- vapply(res, function(r) {
      expected <- fv(r$percent) * basis_total(r, terms$classes)
      ok <<- ok && abs(expected - fv(r$amount)) <= 1
      sprintf("%s: %s against %s", fv(r$name), fmt_money(fv(r$amount)), fmt_money(expected))
    }, character(1))
    add("reserve funds match their percentage", ok, paste(details, collapse = "; "))
  }
  if (!length(terms$triggers)) add("every trigger has a limit", NA, "no trigger found")
  else {
    missing <- vapply(Filter(function(t) is_missing(fv(t$limit)), terms$triggers), function(t) as.character(fv(t$name)), character(1))
    add("every trigger has a limit", !length(missing),
        if (length(missing)) paste("missing:", paste(missing, collapse = ", ")) else "all have one")
  }
  checks
}

waterfall <- function(terms) {
  pop <- terms$priority_of_payments
  vals <- function(x) lapply(x, fv)
  if (length(pop$revenue) || length(pop$principal)) {
    return(list(type = "separate", revenue = vals(pop$revenue), principal = vals(pop$principal)))
  }
  list(type = "combined", combined = vals(pop$combined))
}

# Tool entry point: credit enhancement per class, consistency checks and the waterfall list.
analyse_deal_terms <- function(terms) {
  ce <- credit_enhancement(terms)
  checks <- consistency_checks(terms, ce)
  passed <- vapply(checks, function(c) c$passed, logical(1))
  list(deal = fv(terms$deal_name), credit_enhancement = ce, reserves = reserve_treatment(terms), checks = checks,
       checks_passed = sum(passed %in% TRUE), checks_failed = sum(passed %in% FALSE),
       checks_not_possible = sum(is.na(passed)), waterfall = waterfall(terms),
       ungrounded_values = length(terms$ungrounded))
}
