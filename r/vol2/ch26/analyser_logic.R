# Chapter 26: the Prospectus Analyser's logic, kept outside Shiny so it can be tested and run
# from a script. The app (app_ui.R, app_server.R) only calls these functions.
#
#   source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R")

PENDING <- "[Recording pending: run python record_all.py with Ollama installed, then rebuild]"

# The book's two prospectuses, offered as one-click samples. Only these have answer keys.
SAMPLES <- list(
  thames = list(label = "Thames Auto Receivables 2026-1 (auto loans)",
                pdf = file.path("data", "prospectus", "prospectus.pdf"),
                key = file.path("data", "schemas", "answers_thames.json")),
  severn = list(label = "Severn Residential Mortgages 2026-1 (UK mortgages)",
                pdf = file.path("data", "prospectus_rmbs", "prospectus.pdf"),
                key = file.path("data", "schemas", "answers_rmbs.json"))
)
sample_path <- function(name, what) file.path(repo_root(), SAMPLES[[name]][[what]])

SIMULATED_LABEL <- "simulated model: answers from the answer key, for teaching (not a language model)"

# ---------------------------------------------------------------- 1. the document

# Check an uploaded file before reading it: a PDF starts with the bytes "%PDF".
check_pdf <- function(path) {
  if (!file.exists(path)) return("The file was not found.")
  if (file.size(path) > 50 * 1024^2) return("The file is larger than 50 MB.")
  start <- readBin(path, "raw", n = 4)
  if (!identical(start, charToRaw("%PDF"))) return("This file is not a PDF.")
  NULL
}

# ---------------------------------------------------------------- 2. extraction

# Choose the brain for the model layer. Returns a brain, or a message (character) when none can run.
analyser_brain <- function(mode, sample = NULL, recording = NULL) {
  if (mode == "simulated") {
    if (is.null(sample)) return("The simulated model only works on the book's two sample prospectuses.")
    key <- jsonlite::fromJSON(sample_path(sample, "key"), simplifyVector = FALSE)
    return(simulated_model_brain(key))
  }
  name <- sprintf("vol2-partE-extract-%s.jsonl", if (is.null(sample)) "upload" else sample)
  if (is.null(recording)) recording <- file.path(repo_root(), "r", "recordings", name)
  if (mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) return(PENDING)
  make_brain(mode, recording)
}

# Run the extraction. Returns list(terms, message): terms is NULL when nothing could run.
run_extraction <- function(pdf, layer = "rules", mode = "simulated", sample = NULL) {
  if (all(nchar(trimws(page_texts(pdf))) == 0)) {
    return(list(terms = NULL, message = "The PDF has no text: a scanned document needs OCR (text recognition) first."))
  }
  brain <- NULL
  if (layer != "rules") {
    brain <- analyser_brain(mode, sample)
    if (is.character(brain)) {
      if (layer == "model") return(list(terms = NULL, message = brain))
      # "both" still gives the rules layer; the message says why the model layer is missing.
      return(list(terms = extract_deal_terms(pdf, "rules"), message = brain))
    }
  }
  terms <- tryCatch(extract_deal_terms(pdf, layer, brain),
                    error = function(e) structure(conditionMessage(e), class = "extract_error"))
  if (inherits(terms, "extract_error")) return(list(terms = NULL, message = paste("Extraction failed:", terms)))
  label <- if (layer == "rules") "rules" else if (mode == "simulated") paste(layer, "-", SIMULATED_LABEL) else paste(layer, "-", mode)
  list(terms = terms, message = sprintf("Layer: %s.", label))
}

# How a value is shown: percentages for rates and shares, pounds for amounts, text otherwise.
show_value <- function(path, value) {
  if (is.null(value) || (is.atomic(value) && length(value) == 1 && is.na(value))) return("—")
  if (is.list(value)) {
    if (all(vapply(value, function(s) is.list(s) && !is.null(s$periods), logical(1)))) {   # a trigger schedule
      return(paste(vapply(value, function(s) sprintf("%s: %.2f%%", s$periods, s$limit * 100), ""), collapse = "; "))
    }
    return(paste(unlist(value), collapse = ", "))        # a list of names, e.g. the classes a reserve is based on
  }
  if (is.numeric(value)) {
    if (grepl("margin|share|percent|limit", path)) return(sprintf("%.3f%%", value * 100))
    if (grepl("balance|amount", path)) return(paste0("£", formatC(value, format = "f", digits = 2, big.mark = ",")))
  }
  as.character(value)
}

# One row per extracted value: what the analyst checks.
terms_table <- function(terms) {
  paths <- field_paths(terms)
  rows <- lapply(paths, function(p) {
    f <- get_field(terms, p)
    if (is.null(f) || is_missing(f$value)) return(NULL)
    data.frame(Field = p, Value = show_value(p, f$value), Page = if (is_missing(f$page)) NA_integer_ else as.integer(f$page),
               Source = as.character(f$source),
               Grounded = if (isTRUE(f$grounded)) "grounded" else if (identical(f$grounded, FALSE)) "NOT grounded" else "—",
               Quote = if (is_missing(f$quote)) "" else as.character(f$quote), stringsAsFactors = FALSE)
  })
  do.call(rbind, Filter(Negate(is.null), rows))
}

coverage_text <- function(terms) {
  cv <- terms$coverage
  missing <- unlist(cv$missing)
  sprintf("%d of %d schema fields found%s. Values that failed the page grounding check: %d.",
          cv$found, cv$schema_fields,
          if (length(missing)) paste0(" (missing: ", paste(missing, collapse = ", "), ")") else "",
          length(terms$ungrounded))
}

# ---------------------------------------------------------------- 3. analysis

ce_table <- function(analysis) {
  ce <- analysis$credit_enhancement
  if (!length(ce)) return(NULL)
  data.frame(Class = vapply(ce, function(r) as.character(r$class), ""),
             Balance = vapply(ce, function(r) paste0("£", formatC(r$balance, format = "f", digits = 0, big.mark = ",")), ""),
             `Share of notes` = vapply(ce, function(r) sprintf("%.2f%%", r$share_of_notes * 100), ""),
             Subordination = vapply(ce, function(r) sprintf("%.3f%%", r$subordination * 100), ""),
             `Reserve support` = vapply(ce, function(r) sprintf("%.3f%%", r$reserve_support * 100), ""),
             `Credit enhancement` = vapply(ce, function(r) sprintf("%.3f%%", r$credit_enhancement * 100), ""),
             Rating = vapply(ce, function(r) if (is.null(r$rating)) "" else as.character(r$rating), ""),
             check.names = FALSE)
}

checks_table <- function(analysis) {
  data.frame(Check = vapply(analysis$checks, function(c) c$check, ""),
             Result = vapply(analysis$checks, function(c) if (is.na(c$passed)) "not possible" else if (c$passed) "pass" else "FAIL", ""),
             Detail = vapply(analysis$checks, function(c) c$detail, ""))
}

trigger_table <- function(terms) {
  if (!length(terms$triggers)) return(NULL)
  val <- function(t, k) if (is.null(t[[k]])) NA else t[[k]]$value
  data.frame(Trigger = vapply(terms$triggers, function(t) as.character(val(t, "name")), ""),
             Measure = vapply(terms$triggers, function(t) as.character(val(t, "measure")), ""),
             Limit = vapply(terms$triggers, function(t) show_value("limit", val(t, "limit")), ""),
             Consequence = vapply(terms$triggers, function(t) as.character(val(t, "consequence")), ""))
}

# The capital structure: one stacked bar, Class A at the top, labelled with credit enhancement.
capital_structure_plot <- function(analysis) {
  ce <- analysis$credit_enhancement
  if (!length(ce)) return(NULL)
  d <- data.frame(class = vapply(ce, function(r) as.character(r$class), ""),
                  share = vapply(ce, function(r) r$share_of_notes, 0),
                  ce = vapply(ce, function(r) r$credit_enhancement, 0))
  d$label <- sprintf("Class %s: %.2f%% of notes, CE %.2f%%", d$class, d$share * 100, d$ce * 100)
  d$label <- factor(d$label, levels = d$label)           # legend in seniority order, Class A first
  d$class <- factor(d$class, levels = rev(d$class))      # first class (A) drawn on top of the bar
  ggplot2::ggplot(d, ggplot2::aes(x = "Notes", y = share, fill = label, group = class)) +
    ggplot2::geom_col(width = 0.5, colour = "white") +
    ggplot2::scale_fill_manual(values = grDevices::colorRampPalette(c("#1F2F54", "#B8892B"))(nrow(d)), name = NULL) +
    ggplot2::scale_y_continuous(labels = function(x) paste0(x * 100, "%")) +
    ggplot2::labs(x = NULL, y = "Share of the notes", title = analysis$deal) +
    ggplot2::theme_minimal(base_size = 12) + ggplot2::theme(legend.position = "bottom", legend.direction = "vertical")
}

# The waterfall as numbered steps (one list, or revenue and principal side by side).
waterfall_steps <- function(analysis) {
  w <- analysis$waterfall
  steps <- function(x) vapply(x, function(v) if (is.null(v)) "—" else as.character(v), "")
  if (identical(w$type, "separate")) list(`Revenue priority of payments` = steps(w$revenue),
                                          `Principal priority of payments` = steps(w$principal))
  else list(`Priority of payments` = steps(w$combined))
}

# ---------------------------------------------------------------- 4. questions

# Answer a question from the uploaded PDF. "rules" returns the best passages without a model;
# replay/live/record ask a model to answer only from the passages and cite the page.
# A recording replays the answer to the question it was made with, so the app replays only that one.
ASK_RECORDED <- list(sample = "severn", question = "What is the limit of the arrears trigger?")
ask_recording <- function(sample) file.path(repo_root(), "r", "recordings", sprintf("vol2-ch26-question-%s.jsonl", sample))
ask_document <- function(pdf, question, mode = "rules", recording = NULL, sample = NULL) {
  hits <- tryCatch(search_document(pdf, question, top_k = 3)$results, error = function(e) conditionMessage(e))
  if (is.character(hits)) return(list(answer = hits, passages = list()))
  if (!length(hits)) return(list(answer = "No passage of the document matches the question.", passages = list()))
  if (mode == "rules") {
    top <- hits[[1]]
    return(list(answer = sprintf("Best passage (page %d, no model used): %s", top$page, top$text), passages = hits))
  }
  if (mode == "replay" && is.null(recording)) {
    if (!identical(sample, ASK_RECORDED$sample) || !identical(trimws(question), ASK_RECORDED$question)) {
      return(list(answer = sprintf("Replay holds one recorded answer: the Severn sample, question \"%s\". Choose rules, or live with Ollama.",
                                   ASK_RECORDED$question), passages = hits))
    }
    recording <- ask_recording(sample)
  }
  if (is.null(recording)) recording <- tempfile(fileext = ".jsonl")    # live: nothing is kept
  if (mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) return(list(answer = PENDING, passages = hits))
  context <- paste(vapply(hits, function(h) sprintf("[page %d] %s", h$page, h$text), ""), collapse = "\n")
  memory <- list(list(role = "system", content = paste(
                   "You answer questions about a securitisation prospectus.",
                   "Use only the passages given. Cite the page as (page N). If the passages do not answer, say so.")),
                 list(role = "user", content = paste0("Passages:\n", context, "\n\nQuestion: ", question)))
  reply <- tryCatch(make_brain(mode, recording)$next_step(memory, list()),
                    error = function(e) list(content = paste("The model could not run:", conditionMessage(e))))
  list(answer = reply$content, passages = hits)
}

# ---------------------------------------------------------------- 5. surveillance with the extracted limits

# For the Thames sample data: the trigger tests rerun with the limits read from the prospectus,
# compared period by period with the agent's own trigger tool (which uses the deal terms file).
extracted_limits <- function(terms) {
  find <- function(word) Filter(function(t) grepl(word, tolower(as.character(t$measure$value)), fixed = TRUE), terms$triggers)
  cum <- find("cumulative"); arr <- find("arrears")
  list(cumulative = if (length(cum)) cum[[1]]$limit$value else NULL,
       arrears = if (length(arr)) arr[[1]]$limit$value else NULL)
}

schedule_limit <- function(schedule, period) {
  if (is.numeric(schedule)) return(schedule)
  for (s in schedule) {
    bounds <- as.integer(regmatches(s$periods, gregexpr("[0-9]+", s$periods))[[1]])
    if (period >= bounds[1] && period <= bounds[length(bounds)]) return(s$limit)
  }
  NA_real_
}

surveillance_table <- function(terms) {
  lim <- extracted_limits(terms)
  if (is.null(lim$cumulative) || is.null(lim$arrears)) return(NULL)
  rows <- lapply(seq_len(N_PERIODS), function(p) {
    r <- recompute(p)
    agent <- run_trigger_tests(p)$tests
    agent_breach <- vapply(agent, function(t) t$breached, logical(1))
    cum_limit <- schedule_limit(lim$cumulative, p)
    ours <- c(r$cumulative_default_ratio > cum_limit, r$arrears_90_ratio > lim$arrears)
    data.frame(Period = p,
               `Cum. default` = sprintf("%.3f%%", r$cumulative_default_ratio * 100),
               `Its limit` = sprintf("%.2f%%", cum_limit * 100),
               `90+ arrears` = sprintf("%.3f%%", r$arrears_90_ratio * 100),
               `Its limit ` = sprintf("%.2f%%", lim$arrears * 100),
               Result = if (any(ours)) "BREACHED" else "pass",
               `Agent agrees` = if (identical(as.logical(ours), as.logical(agent_breach))) "yes" else "NO",
               check.names = FALSE)
  })
  do.call(rbind, rows)
}

# An uploaded investor report (JSON, Thames format): its reported ratios against the extracted limits.
report_against_limits <- function(report_path, terms) {
  rep <- jsonlite::fromJSON(report_path, simplifyVector = FALSE)
  lim <- extracted_limits(terms)
  p <- as.integer(rep$period)
  cum <- rep$triggers$cumulative_default_ratio$value
  arr <- rep$triggers$arrears_90_ratio$value
  data.frame(Test = c("Cumulative default ratio", "90+ day arrears ratio"),
             Reported = sprintf("%.3f%%", c(cum, arr) * 100),
             `Limit (prospectus)` = sprintf("%.2f%%", c(schedule_limit(lim$cumulative, p), lim$arrears) * 100),
             Result = ifelse(c(cum > schedule_limit(lim$cumulative, p), arr > lim$arrears), "BREACHED", "pass"),
             check.names = FALSE)
}

# ---------------------------------------------------------------- 6. export

export_json <- function(terms, analysis, path) {
  writeLines(jsonlite::toJSON(list(terms = terms, analysis = analysis), auto_unbox = TRUE, null = "null",
                              na = "null", digits = NA, pretty = TRUE), path, useBytes = TRUE)
}

export_excel <- function(terms, analysis, path) {
  wb <- openxlsx::createWorkbook()
  sheets <- list(`Deal terms` = terms_table(terms), `Credit enhancement` = ce_table(analysis),
                 `Checks` = checks_table(analysis), `Triggers` = trigger_table(terms))
  for (name in names(sheets)) {
    openxlsx::addWorksheet(wb, name)
    if (!is.null(sheets[[name]])) openxlsx::writeData(wb, name, sheets[[name]])
  }
  openxlsx::saveWorkbook(wb, path, overwrite = TRUE)
}
