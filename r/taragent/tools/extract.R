# Tool 6 — extract the deal terms from any prospectus PDF (R version of tar_agent/tools/extract.py).
#
#   extract_deal_terms(pdf_path, layer = "rules")                  # patterns only
#   extract_deal_terms(pdf_path, layer = "model", brain = brain)   # a model fills the schema, section by section
#   extract_deal_terms(pdf_path, layer = "both", brain = brain)    # rules first, the model fills the gaps
#
# Every value is a field: list(value, page, quote, source, grounded). A missing value is NA
# (written null in JSON). The rules, the prompts and the grounding check are the same as in
# Python, so both languages return the same JSON.

SCALARS <- c("deal_name", "currency", "pool_balance", "parties.issuer", "parties.originator", "parties.servicer",
             "parties.trustee", "dates.cut_off", "dates.closing", "dates.first_payment", "risk_retention")
LISTS <- c("classes", "reserve_funds", "priority_of_payments", "triggers", "eligibility_criteria")

PARTY_LABELS <- list(issuer = "Issuer", originator = c("Originator and seller", "Originator", "Seller"),
                     servicer = "Servicer", trustee = "Trustee")
DATE_LABELS <- list(cut_off = "Cut-off date", closing = "Closing date", first_payment = "First payment date")
COMPANY <- "((?:[A-Z0-9][\\w&'.-]* ){0,6}?(?:plc|PLC|Ltd|Limited|Society|LLP|Bank))\\b"
DATE_RE <- "(\\d{4}-\\d{2}-\\d{2}|\\d{1,2} [A-Z][a-z]+ \\d{4})"
RETENTION_METHODS <- c("vertical slice", "first loss tranche", "randomly selected exposures", "seller's share",
                       "originator's share")
DASH <- "\u2014"

# ---------------------------------------------------------------- small helpers

field <- function(value = NA, page = NA, quote = NA, source = NA) {
  list(value = if (is.null(value)) NA else value, page = if (is.null(page)) NA else page,
       quote = if (is.null(quote)) NA else quote, source = if (is.null(source)) NA else source, grounded = NA)
}
is_missing <- function(x) is.null(x) || (is.atomic(x) && length(x) == 1 && is.na(x))

empty_terms <- function() {
  list(deal_name = field(), currency = field(), pool_balance = field(),
       parties = lapply(PARTY_LABELS, function(x) field()),
       dates = lapply(DATE_LABELS, function(x) field()),
       classes = list(), reserve_funds = list(),
       priority_of_payments = list(combined = list(), revenue = list(), principal = list()),
       triggers = list(), eligibility_criteria = list(),
       risk_retention = field(), definitions = named_list())
}

money <- function(text) as.numeric(gsub(",", "", text, fixed = TRUE))

iso_date <- function(text) {
  if (grepl("^\\d{4}-\\d{2}-\\d{2}$", text, perl = TRUE)) return(text)
  parts <- strsplit(text, " ", fixed = TRUE)[[1]]
  sprintf("%s-%02d-%02d", parts[3], match(parts[2], month.name), as.integer(parts[1]))
}

get_path <- function(terms, path) {
  node <- terms
  for (part in strsplit(path, ".", fixed = TRUE)[[1]]) node <- node[[part]]
  node
}
set_path <- function(terms, path, value) {
  parts <- strsplit(path, ".", fixed = TRUE)[[1]]
  if (length(parts) == 1) terms[[parts]] <- value else terms[[parts[1]]][[parts[2]]] <- value
  terms
}

alnum <- function(text) gsub("[^a-z0-9]", "", tolower(as.character(text)), perl = TRUE)
words <- function(text) unique(regmatches(tolower(text), gregexpr("[a-z0-9]+", tolower(text), perl = TRUE))[[1]])

# The match and its groups: c(whole, group1, group2, ...), or NULL.
match1 <- function(pattern, text) {
  m <- regmatches(text, regexec(pattern, text, perl = TRUE))[[1]]
  if (length(m)) m else NULL
}
# Every match of a pattern in a text, each as c(whole, groups...).
match_all <- function(pattern, text) {
  whole <- regmatches(text, gregexpr(pattern, text, perl = TRUE))[[1]]
  lapply(whole, function(w) match1(pattern, w))
}
# First match on any page: list(m, page) or NULL.
search_pages <- function(texts, pattern) {
  for (number in seq_along(texts)) {
    m <- match1(pattern, texts[number])
    if (!is.null(m)) return(list(m = m, page = number))
  }
  NULL
}

numbered_items <- function(lines, start_pattern) {
  for (i in seq_along(lines)) {
    if (grepl(start_pattern, lines[i], ignore.case = TRUE, perl = TRUE)) {
      items <- character(0)
      started <- FALSE
      rest <- if (i < length(lines)) lines[(i + 1):length(lines)] else character(0)
      for (line2 in rest) {
        m <- match1("^\\d+\\. (.+)$", line2)
        if (!is.null(m) && !grepl("^\\d\\. [A-Z][^.:]*$", line2, perl = TRUE)) {
          items <- c(items, m[2])
          started <- TRUE
        } else if (started && length(items) && !endsWith(trimws(items[length(items)], "right"), ".")) {
          items[length(items)] <- paste(items[length(items)], line2)
        } else if (started) {
          break
        }
      }
      return(items)
    }
  }
  character(0)
}

# ---------------------------------------------------------------- layer 1: rules

extract_rules <- function(pdf_path) {
  pages <- read_pages(pdf_path)
  texts <- page_texts(pdf_path)
  terms <- empty_terms()

  if (length(pages)) {
    first <- Filter(function(ln) grepl("\\b(plc|PLC|Limited|Ltd)$", ln, perl = TRUE), pages[[1]])
    if (length(first)) terms$deal_name <- field(first[1], 1, first[1], "rules")
  }
  for (key in names(PARTY_LABELS)) {
    for (label in PARTY_LABELS[[key]]) {
      hit <- search_pages(texts, paste0("\\b", label, " ", COMPANY))
      if (!is.null(hit)) { terms$parties[[key]] <- field(hit$m[2], hit$page, hit$m[1], "rules"); break }
    }
  }
  for (key in names(DATE_LABELS)) {
    for (label in DATE_LABELS[[key]]) {
      hit <- search_pages(texts, paste0("\\b", label, " ", DATE_RE))
      if (!is.null(hit)) { terms$dates[[key]] <- field(iso_date(hit$m[2]), hit$page, hit$m[1], "rules"); break }
    }
  }
  hit <- search_pages(texts, "\\bCurrency [^()]*?\\(?\\b(GBP|EUR|USD)\\b")
  if (!is.null(hit)) terms$currency <- field(hit$m[2], hit$page, hit$m[1], "rules")
  hit <- search_pages(texts, "\\bPool balance(?: at the cut-off date)? \u00a3([\\d,]+\\.\\d\\d)")
  if (!is.null(hit)) terms$pool_balance <- field(money(hit$m[2]), hit$page, hit$m[1], "rules")

  row <- "Class ([A-Z]) \u00a3([\\d,]+(?:\\.\\d\\d)?) (\\d+(?:\\.\\d+)?)% SONIA \\+ (\\d+(?:\\.\\d+)?)% ([A-Z]{1,3}(?:sf)?)\\b"
  for (number in seq_along(texts)) {
    for (m in match_all(row, texts[number])) {
      q <- m[1]
      terms$classes[[length(terms$classes) + 1]] <- list(
        name = field(m[2], number, q, "rules"), balance = field(money(m[3]), number, q, "rules"),
        share = field(round(as.numeric(m[4]) / 100, 6), number, q, "rules"),
        margin = field(round(as.numeric(m[5]) / 100, 6), number, q, "rules"),
        rating = field(m[6], number, q, "rules"))
    }
  }

  pattern <- paste0("\\b((?:[A-Z][a-z]+ )?[Rr]eserve [Ff]und) of \u00a3([\\d,]+(?:\\.\\d\\d)?), equal to ",
                    "(\\d+(?:\\.\\d+)?)% of the initial balance of the notes")
  for (number in seq_along(texts)) {
    for (m in match_all(pattern, texts[number])) {
      name <- paste0(toupper(substr(m[2], 1, 1)), substr(m[2], 2, nchar(m[2])))
      terms$reserve_funds[[length(terms$reserve_funds) + 1]] <- list(
        name = field(name, number, m[1], "rules"), amount = field(money(m[3]), number, m[1], "rules"),
        percent = field(round(as.numeric(m[4]) / 100, 6), number, m[1], "rules"),
        basis = field(),                              # "the notes": every class (the rules do not read a list here)
        can_cover_losses = cover_field(name, texts))
    }
  }

  for (number in seq_along(pages)) {
    items <- numbered_items(pages[[number]], "^\\d+\\. Priority of payments$")
    if (length(items)) {
      for (item in items) {
        label <- trimws(strsplit(item, "[:.]", perl = TRUE)[[1]][1])
        terms$priority_of_payments$combined[[length(terms$priority_of_payments$combined) + 1]] <-
          field(label, number, item, "rules")
      }
      break
    }
  }

  test_re <- paste0("Test \\d ", DASH, " ([^.]+)\\. (.*?)(?=Test \\d ", DASH, "|Consequence\\.|$)")
  for (number in seq_along(texts)) {
    consequence <- match1("Consequence\\. (.+?\\.)", texts[number])
    for (m in match_all(test_re, texts[number])) {
      name <- m[2]
      body <- m[3]
      schedule <- match_all("Periods (\\d+) to (\\d+) (\\d+(?:\\.\\d+)?)%", body)
      single <- match1("must not exceed (\\d+(?:\\.\\d+)?)%", body)
      limit <- if (length(schedule)) {
        lapply(schedule, function(s) list(periods = paste(s[2], "to", s[3]), limit = round(as.numeric(s[4]) / 100, 6)))
      } else if (!is.null(single)) round(as.numeric(single[2]) / 100, 6)
      else if (grepl("required amount", body, fixed = TRUE)) "required amount" else NA
      q <- trimws(m[1])
      terms$triggers[[length(terms$triggers) + 1]] <- list(
        name = field(name, number, q, "rules"), measure = field(tolower(name), number, q, "rules"),
        limit = field(limit, number, q, "rules"),
        consequence = field(if (is.null(consequence)) NA else consequence[2], number,
                            if (is.null(consequence)) NA else consequence[1], "rules"))
    }
  }

  for (number in seq_along(pages)) {
    items <- numbered_items(pages[[number]], "met the following criteria|eligibility criteria:")
    if (length(items)) {
      terms$eligibility_criteria <- lapply(items, function(it) field(it, number, it, "rules"))
      break
    }
  }

  for (number in seq_along(texts)) {
    for (sentence in strsplit(texts[number], "(?<=\\.) ", perl = TRUE)[[1]]) {
      if (grepl("\\bretain", sentence, perl = TRUE) || grepl("Risk retention", sentence, fixed = TRUE)) {
        method <- RETENTION_METHODS[vapply(RETENTION_METHODS, grepl, logical(1), x = sentence, fixed = TRUE)]
        if (length(method)) { terms$risk_retention <- field(method[1], number, sentence, "rules"); break }
      }
    }
    if (!is_missing(terms$risk_retention$value)) break
  }

  for (number in seq_along(pages)) {
    lines <- pages[[number]]
    if (!any(grepl("Definitions", lines, fixed = TRUE))) next
    for (line in lines) {
      m <- match1("^\u2022 ([A-Z][^:]{2,40}): (.+)$", line)
      if (!is.null(m)) terms$definitions[[m[2]]] <- field(m[3], number, line, "rules")
    }
  }
  terms
}

# ---------------------------------------------------------------- what a reserve fund can pay (as in Python)

# TRUE (it can pay principal or cover losses), FALSE (it pays only fees and interest), NA (the sentence does not say).
reads_cover <- function(sentence) {
  s <- tolower(gsub("\\s+", " ", sentence))
  if (grepl("\\b(never|not|cannot)\\b[^.]*\\bprincipal\\b", s, perl = TRUE)) return(FALSE)
  if (grepl("principal deficiency|pay principal|principal on the notes|\\blosses\\b", s, perl = TRUE)) return(TRUE)
  if (grepl("\\binterest\\b", s, perl = TRUE) && grepl("\\bonly\\b", s, perl = TRUE)) return(FALSE)
  NA
}

# The first sentence whose subject is the reserve fund ("The General Reserve Fund covers ...") and that says
# what it can pay. Only sentences that start with the fund's own name count.
cover_field <- function(name, texts) {
  escaped <- gsub("([.^$|()\\[\\]{}*+?\\\\])", "\\\\\\1", name, perl = TRUE)
  pattern <- paste0("(?i)\\bThe ", escaped, "\\b[^.;]*[.;]")
  for (number in seq_along(texts)) {
    text <- gsub("\\s+", " ", trimws(texts[number]))
    hits <- regmatches(text, gregexpr(pattern, text, perl = TRUE))[[1]]
    for (sentence in hits) {
      reading <- reads_cover(sentence)
      if (!is.na(reading)) return(field(reading, number, sentence, "rules"))
    }
  }
  field()
}

# ---------------------------------------------------------------- layer 2: a model, section by section

EXTRACT_SYSTEM_PROMPT <- paste(
  "You extract the terms of a securitisation from passages of its prospectus. Reply with JSON only, no other",
  "text. Use only the passages given. For every value give the page number of the passage it comes from and",
  "copy the exact sentence or table row as the quote. If a value is not in the passages, use null. Write",
  "percentages as decimals (0.58% becomes 0.0058), amounts as plain numbers without commas or currency signs,",
  "and dates as YYYY-MM-DD. For a reserve fund, can_cover_losses is true when the prospectus says it can pay",
  "principal or cure a principal deficiency, false when it pays only fees and interest.",
  "Each field is an object: {\"value\": ..., \"page\": ..., \"quote\": ...}.")

F_TEXT <- '{"value": ..., "page": ..., "quote": ...}'
SECTIONS <- list(
  list("overview", paste("issuer seller originator servicer administrator trustee cut-off reference closing issue date",
                         "first payment currency sterling pool balance aggregate"),
       paste0('{"deal_name": F, "parties": {"issuer": F, "originator": F, "servicer": F, "trustee": F}, ',
              '"dates": {"cut_off": F, "closing": F, "first_payment": F}, "currency": F, "pool_balance": F}')),
  list("classes", "notes class principal amount margin SONIA rating",
       '{"classes": [{"name": F, "balance": F, "share": F, "margin": F, "rating": F}]}'),
  list("reserve_funds", "reserve fund required amount per cent notes principal deficiency interest only",
       '{"reserve_funds": [{"name": F, "amount": F, "percent": F, "basis": F, "can_cover_losses": F}]}'),
  list("priority_of_payments", "priority of payments order item paid",
       '{"priority_of_payments": {"combined": [F], "revenue": [F], "principal": [F]}}'),
  list("triggers", "trigger event test exceeds per cent sequential limit",
       '{"triggers": [{"name": F, "measure": F, "limit": F, "consequence": F}]}'),
  list("eligibility", "eligibility criteria warranties each loan", '{"eligibility_criteria": [F]}'),
  list("risk_retention", "risk retention retains 5 per cent net economic interest", '{"risk_retention": F}')
)

section_prompt <- function(pdf_path, name, query, template, top_k = 4) {
  passages <- search_document(pdf_path, query, top_k = top_k)$results
  text <- paste(vapply(passages, function(p) sprintf("[page %d] %s", as.integer(p$page), p$text), character(1)),
                collapse = "\n\n")
  sprintf("SECTION: %s\nFill this JSON template, where F means %s:\n%s\n\nPassages:\n%s",
          name, F_TEXT, gsub("F", F_TEXT, template, fixed = TRUE), text)
}

parse_reply <- function(content, name) {
  text <- trimws(content)
  text <- gsub("^```(?:json)?\\s*|\\s*```$", "", text, perl = TRUE)
  data <- jsonlite::fromJSON(text, simplifyVector = FALSE)
  if (!is.list(data) || is.null(names(data))) stop("the reply is not a JSON object", call. = FALSE)
  expected <- switch(name, overview = "deal_name", eligibility = "eligibility_criteria", name)
  for (key in expected) if (!(key %in% names(data))) stop(sprintf("the reply has no '%s' key", key), call. = FALSE)
  data
}

as_field <- function(x) {
  if (is.list(x) && "value" %in% names(x)) {
    page <- suppressWarnings(as.integer(if (is.null(x$page)) NA else x$page))
    return(field(if (is.null(x$value)) NA else x$value, page, if (is.null(x$quote)) NA else x$quote, "model"))
  }
  if (is.null(x)) field() else field(x, NA, NA, "model")
}

merge_section <- function(terms, name, data) {
  if (name == "overview") {
    terms$deal_name <- as_field(data$deal_name)
    terms$currency <- as_field(data$currency)
    terms$pool_balance <- as_field(data$pool_balance)
    for (k in names(PARTY_LABELS)) terms$parties[[k]] <- as_field(data$parties[[k]])
    for (k in names(DATE_LABELS)) terms$dates[[k]] <- as_field(data$dates[[k]])
  } else if (name %in% c("classes", "reserve_funds", "triggers")) {
    terms[[name]] <- lapply(if (is.null(data[[name]])) list() else data[[name]], function(item) lapply(item, as_field))
  } else if (name == "priority_of_payments") {
    pop <- if (is.null(data[[name]])) list() else data[[name]]
    terms[[name]] <- lapply(c(combined = "combined", revenue = "revenue", principal = "principal"),
                            function(k) lapply(if (is.null(pop[[k]])) list() else pop[[k]], as_field))
  } else if (name == "eligibility") {
    terms$eligibility_criteria <- lapply(if (is.null(data$eligibility_criteria)) list() else data$eligibility_criteria,
                                         as_field)
  } else if (name == "risk_retention") {
    terms$risk_retention <- as_field(data$risk_retention)
  }
  terms
}

extract_model <- function(pdf_path, brain) {
  terms <- empty_terms()
  log <- list()
  for (s in SECTIONS) {
    name <- s[[1]]
    memory <- list(list(role = "system", content = EXTRACT_SYSTEM_PROMPT),
                   list(role = "user", content = section_prompt(pdf_path, name, s[[2]], s[[3]])))
    for (attempt in 1:2) {
      reply <- brain$next_step(memory, list())
      content <- if (is.null(reply$content)) "" else reply$content
      result <- tryCatch(merge_section(terms, name, parse_reply(content, name)), error = function(e) e)
      if (!inherits(result, "error")) {
        terms <- result
        log[[length(log) + 1]] <- list(section = name, attempts = attempt, ok = TRUE)
        break
      }
      if (attempt == 2) {
        log[[length(log) + 1]] <- list(section = name, attempts = 2, ok = FALSE, error = conditionMessage(result))
      } else {
        memory <- c(memory, list(list(role = "assistant", content = content),
                                 list(role = "user", content = sprintf(
                                   "Your reply was not valid for this section: %s. Reply again with the JSON only.",
                                   conditionMessage(result)))))
      }
    }
  }
  terms$model_log <- log
  terms
}

# ---------------------------------------------------------------- the grounding check

fmt_g <- function(p) sprintf("%g", p)
candidates <- function(value) {
  if (is_missing(value) || is.logical(value)) return(character(0))
  if (is.numeric(value)) {
    v <- as.numeric(value)
    if (abs(v) > 0 && abs(v) < 1) {
      p <- v * 100
      forms <- unique(c(sprintf("%.2f", p), sub("0+$", "", sprintf("%.3f", p)), fmt_g(p)))
      return(sort(unique(c(outer(forms, c("%", " per cent"), paste0), sprintf("%.2f", p)))))
    }
    out <- c(formatC(v, format = "f", digits = 2, big.mark = ","), sprintf("%.2f", v))
    if (v == round(v)) out <- c(out, formatC(v, format = "f", digits = 0, big.mark = ","), sprintf("%.0f", v))
    return(sort(unique(out)))
  }
  text <- as.character(value)
  if (grepl("^\\d{4}-\\d{2}-\\d{2}$", text, perl = TRUE)) {
    d <- as.integer(strsplit(text, "-", fixed = TRUE)[[1]])
    return(c(text, sprintf("%d %s %d", d[3], month.name[d[2]], d[1])))
  }
  text
}

# A number written in the text as a whole number: "2.50" is not found inside "12.50" or "2.505".
number_in <- function(candidate, text) {
  escaped <- gsub("([][{}()+*^$|\\\\?.])", "\\\\\\1", candidate)
  grepl(paste0("(?<![0-9])(?<![0-9][.,])", escaped, "(?![0-9])(?![.,][0-9])"), text, perl = TRUE)
}

value_on_page <- function(value, page_text, key = "") {
  if (is.list(value)) {
    parts <- lapply(value, function(x) if (is.list(x)) x$limit else x)
    return(length(parts) > 0 && all(vapply(parts, value_on_page, logical(1), page_text = page_text)))
  }
  if (key == "currency" && identical(as.character(value), "GBP")) {
    return(any(vapply(c("GBP", "sterling", "Sterling", "\u00a3"), grepl, logical(1), x = page_text, fixed = TRUE)))
  }
  is_text <- is.character(value) && !grepl("^\\d{4}-\\d{2}-\\d{2}$", value, perl = TRUE)
  for (cand in candidates(value)) {
    if (is_text) {
      if (nchar(alnum(cand)) && grepl(alnum(cand), alnum(page_text), fixed = TRUE)) return(TRUE)
    } else if (number_in(cand, page_text)) return(TRUE)
  }
  FALSE
}

ground_field <- function(f, texts, key = "") {
  if (is_missing(f$value)) { f$grounded <- NA; return(f) }
  p <- f$page
  if (is_missing(p) || !is.numeric(p) || p < 1 || p > length(texts)) { f$grounded <- FALSE; return(f) }
  page_text <- texts[p]
  if (is.logical(f$value)) {
    # A yes/no value is never written as such: its quote must be on the page and must say the same thing.
    q <- if (is_missing(f$quote)) "" else f$quote
    reading <- if (nzchar(q)) reads_cover(q) else NA
    f$grounded <- nzchar(q) && all(words(q) %in% words(page_text)) && !is.na(reading) && identical(reading, f$value)
    return(f)
  }
  value_ok <- value_on_page(f$value, page_text, key)
  # A quote counts when all its words are on the page, in any order (PDF libraries order table cells differently).
  quote_ok <- is_missing(f$quote) || !nzchar(f$quote) || all(words(f$quote) %in% words(page_text))
  # A number or a date must also be written in its own quote (as in Python).
  v <- f$value
  if (!is_missing(f$quote) && nzchar(f$quote) && length(v) == 1 && !is.list(v) &&
      ((is.numeric(v) && !is.logical(v)) || (is.character(v) && grepl("^\\d{4}-\\d{2}-\\d{2}$", v, perl = TRUE)))) {
    quote_ok <- quote_ok && value_on_page(v, f$quote, key)
  }
  f$grounded <- isTRUE(value_ok && quote_ok)
  f
}

# Every field with a readable path, in the same order as Python: list(list(path, accessor), ...).
field_paths <- function(terms) {
  out <- as.list(SCALARS)
  for (i in seq_along(terms$classes)) out <- c(out, sprintf("classes[%d].%s", i - 1, names(terms$classes[[i]])))
  for (i in seq_along(terms$reserve_funds)) out <- c(out, sprintf("reserve_funds[%d].%s", i - 1, names(terms$reserve_funds[[i]])))
  for (kind in c("combined", "revenue", "principal")) {
    n <- length(terms$priority_of_payments[[kind]])
    if (n) out <- c(out, sprintf("priority_of_payments.%s[%d]", kind, seq_len(n) - 1))
  }
  for (i in seq_along(terms$triggers)) out <- c(out, sprintf("triggers[%d].%s", i - 1, names(terms$triggers[[i]])))
  n <- length(terms$eligibility_criteria)
  if (n) out <- c(out, sprintf("eligibility_criteria[%d]", seq_len(n) - 1))
  if (length(terms$definitions)) out <- c(out, paste0("definitions.", names(terms$definitions)))
  unlist(out)
}

# Read or write the field at a path such as "classes[1].margin" or "priority_of_payments.revenue[3]".
path_index <- function(path) {
  m <- match1("^([a-z_]+)(?:\\.([a-z_]+))?\\[(\\d+)\\](?:\\.([a-z_]+))?$", path)
  m
}
get_field <- function(terms, path) {
  if (startsWith(path, "definitions.")) return(terms$definitions[[sub("^definitions\\.", "", path)]])
  m <- path_index(path)
  if (is.null(m)) return(get_path(terms, path))
  node <- terms[[m[2]]]
  if (nzchar(m[3])) node <- node[[m[3]]]
  node <- node[[as.integer(m[4]) + 1]]
  if (nzchar(m[5])) node <- node[[m[5]]]
  node
}
set_field <- function(terms, path, f) {
  if (startsWith(path, "definitions.")) { terms$definitions[[sub("^definitions\\.", "", path)]] <- f; return(terms) }
  m <- path_index(path)
  if (is.null(m)) return(set_path(terms, path, f))
  i <- as.integer(m[4]) + 1
  if (nzchar(m[3]) && nzchar(m[5])) terms[[m[2]]][[m[3]]][[i]][[m[5]]] <- f
  else if (nzchar(m[3])) terms[[m[2]]][[m[3]]][[i]] <- f
  else if (nzchar(m[5])) terms[[m[2]]][[i]][[m[5]]] <- f
  else terms[[m[2]]][[i]] <- f
  terms
}

# Run the grounding check on every field: the terms with their flags, and the paths that failed.
ground_terms <- function(terms, pdf_path) {
  texts <- page_texts(pdf_path)
  failed <- character(0)
  for (path in field_paths(terms)) {
    f <- ground_field(get_field(terms, path), texts, key = path)
    terms <- set_field(terms, path, f)
    if (identical(f$grounded, FALSE)) failed <- c(failed, path)
  }
  list(terms = terms, failed = failed)
}

# ---------------------------------------------------------------- coverage, combining the layers, the tool

found_slot <- function(terms, path) {
  if (path %in% LISTS) {
    node <- terms[[path]]
    if (path == "priority_of_payments") return(any(lengths(node) > 0))
    return(length(node) > 0)
  }
  !is_missing(get_path(terms, path)$value)
}

coverage <- function(terms) {
  slots <- c(SCALARS, LISTS)
  found <- slots[vapply(slots, found_slot, logical(1), terms = terms)]
  list(schema_fields = length(slots), found = length(found), share = round(length(found) / length(slots), 4),
       missing = as.list(setdiff(slots, found)))
}

combine_layers <- function(rules, model) {
  out <- rules
  for (path in SCALARS) {
    if (is_missing(get_path(out, path)$value) && !is_missing(get_path(model, path)$value)) {
      out <- set_path(out, path, get_path(model, path))
    }
  }
  for (name in c("classes", "reserve_funds", "triggers", "eligibility_criteria")) {
    if (!length(out[[name]]) && length(model[[name]])) out[[name]] <- model[[name]]
  }
  if (!any(lengths(out$priority_of_payments) > 0)) out$priority_of_payments <- model$priority_of_payments
  out$model_log <- if (is.null(model$model_log)) list() else model$model_log
  out
}

# Tool entry point: the deal terms of any prospectus PDF, each value with its page, quote and grounding.
extract_deal_terms <- function(pdf_path, layer = "rules", brain = NULL) {
  if (!(layer %in% c("rules", "model", "both"))) stop("layer must be 'rules', 'model' or 'both'", call. = FALSE)
  if (layer %in% c("model", "both") && is.null(brain)) {
    stop(sprintf("layer '%s' needs a brain (rules, replay, live or record)", layer), call. = FALSE)
  }
  terms <- switch(layer,
                  rules = extract_rules(pdf_path),
                  model = extract_model(pdf_path, brain),
                  both = combine_layers(extract_rules(pdf_path), extract_model(pdf_path, brain)))
  g <- ground_terms(terms, pdf_path)
  terms <- g$terms
  terms$layer <- layer
  terms$coverage <- coverage(terms)
  terms$ungrounded <- as.list(g$failed)
  terms
}

# ---------------------------------------------------------------- scoring against an answer key

same_value <- function(a, b) {
  if (is_missing(a) || is_missing(b)) return(FALSE)
  if (is.numeric(a) && is.numeric(b)) return(abs(a - b) <= max(0.005, 1e-6 * abs(b)))
  if (is.list(a) && is.list(b)) {
    return(length(a) == length(b) && all(mapply(function(x, y) same_value(x$limit, y$limit), a, b)))
  }
  if (is.list(a) || is.list(b)) return(FALSE)
  alnum(a) == alnum(b)
}

score_against_key <- function(terms, key) {
  rows <- list()
  add <- function(path, got, expected) {
    rows[[length(rows) + 1]] <<- list(field = path, found = !is_missing(got), correct = same_value(got, expected))
  }
  for (path in SCALARS) add(path, get_path(terms, path)$value, get_path(key, path)$value)
  by_name <- function(items) {
    items <- Filter(function(x) !is_missing(x$name$value), items)
    setNames(items, vapply(items, function(x) alnum(x$name$value), character(1)))
  }
  got_classes <- by_name(terms$classes)
  for (c in key$classes) {
    g <- got_classes[[alnum(c$name$value)]]
    for (k in c("balance", "share", "margin", "rating")) {
      if (!is_missing(c[[k]]$value)) add(sprintf("classes.%s.%s", c$name$value, k), if (is.null(g)) NA else g[[k]]$value, c[[k]]$value)
    }
  }
  got_res <- by_name(terms$reserve_funds)
  for (r in key$reserve_funds) {
    g <- got_res[[alnum(r$name$value)]]
    for (k in c("amount", "percent", "can_cover_losses")) {
      if (!is.null(r[[k]])) add(sprintf("reserve_funds.%s.%s", r$name$value, k),
                                if (is.null(g) || is.null(g[[k]])) NA else g[[k]]$value, r[[k]]$value)
    }
  }
  for (kind in c("combined", "revenue", "principal")) {
    got <- vapply(Filter(function(x) !is_missing(x$value), terms$priority_of_payments[[kind]]),
                  function(x) alnum(x$value), character(1))
    for (x in key$priority_of_payments[[kind]]) {
      add(sprintf("priority_of_payments.%s.%s", kind, x$value), if (alnum(x$value) %in% got) x$value else NA, x$value)
    }
  }
  got_tr <- by_name(terms$triggers)
  for (t in key$triggers) {
    g <- got_tr[[alnum(t$name$value)]]
    add(sprintf("triggers.%s.name", t$name$value), if (is.null(g)) NA else t$name$value, t$name$value)
    add(sprintf("triggers.%s.limit", t$name$value), if (is.null(g)) NA else g$limit$value, t$limit$value)
  }
  got_el <- vapply(Filter(function(x) !is_missing(x$value), terms$eligibility_criteria), function(x) alnum(x$value), character(1))
  for (i in seq_along(key$eligibility_criteria)) {
    x <- key$eligibility_criteria[[i]]
    add(sprintf("eligibility_criteria.%d", i), if (alnum(x$value) %in% got_el) x$value else NA, x$value)
  }
  found <- sum(vapply(rows, function(r) r$found, logical(1)))
  correct <- sum(vapply(rows, function(r) r$correct, logical(1)))
  list(fields = length(rows), found = found, correct = correct,
       found_share = round(found / length(rows), 4), correct_share = round(correct / length(rows), 4), rows = rows)
}
