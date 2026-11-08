# tar_agent — design note (for the R mirror in Volume 2 Part D)

Every public function below takes plain arguments and returns plain data (numbers, strings, lists,
dictionaries), so each one can be written the same way in R (lists and data frames, `jsonlite` for JSON).

## data.py — reading the deal pack
| Function | Arguments | Returns |
|---|---|---|
| `deal_terms()` | — | dict from `data/deal_terms.json` |
| `investor_report(period)` | period 1–12 | dict from `data/investor_reports/investor_report_2026_MM.json` |
| `servicer_report(period)` | period 1–12 | data frame, one row per region |
| `loan_performance()` | — | data frame from `data/loan_performance.csv` |
| `check_period(period)` | any | raises `ValueError` unless a whole number 1–12 |

## tools/ — the five tools (each returns a dict; `registry.call_tool` turns it into JSON)
| Function | Arguments | Returns (keys) |
|---|---|---|
| `validate_loan_tape(path=None)` | optional path | rows_received, loans_after_cleaning, issues_found, issues_by_rule, issues[loan_id, column, value, rule, fix], balance_after_cleaning, initial_pool_balance_in_deal_terms, reconciles |
| `find_issues(tape)` / `clean_tape(tape, issues)` / `load_clean_tape()` | data frame | list of issues / cleaned data frame |
| `stratify_pool(by, period=0, measure="balance")` | by ∈ FIELDS, period 0–12, measure ∈ balance, count, balance_90plus | period, by, measure, total, loans_in_pool, rows[group, <measure>, share_of_total, (ratio_within_group)] sorted by value descending |
| `run_trigger_tests(period)` | 1–12 | period, payment_date, tests[test, value, limit, headroom, breached, reported_value, agrees_with_report], reserve_fund_shortfall, trigger_event_this_period, first_breach_period, principal_payment_mode, report_shows_mode |
| `first_breach_period(up_to=12)` | int | int or None |
| `search_prospectus(query, top_k=3)` | text, 1–5 | query, results[page, section, score, text] — BM25, k1 = 1.5, b = 0.75, chunks of 5 lines every 3 lines |
| `draft_surveillance_note(period)` | 1–12 | period, note_markdown, key_figures{arrears_90_ratio, cumulative_default_ratio, principal_payment_mode, main_arrears_region} |

## registry.py
| Function | Returns |
|---|---|
| `tool_schemas()` | list of `{"type": "function", "function": {name, description, parameters}}` |
| `call_tool(name, arguments)` | JSON text; errors are returned as `{"error": "..."}`, never raised |

## agent.py — the agent (chapter 11)
| Name | Role |
|---|---|
| `SYSTEM_PROMPT` | the six rules given to the model |
| `find_period(text)` | 0 (cut-off), 1–12, or None, from "period N", a month name or "cut-off" |
| `choose_tool(question)` | (tool name, arguments) by keyword rules; stratification words are checked before "pool balance" |
| `answer_from_result(question, name, result)` | the final answer text built from one tool result |
| `finance_rules(memory)` | RuleBrain function: one tool call, then the answer |
| `ask(question, mode, recording, log, max_steps=6)` | runs `agent_core.loop.run_agent`; returns answer, stopped_because, steps, memory |
| CLI | `python -m tar_agent.agent "question" --mode rules|live|record|replay [--quiet]` |

## evaluate.py — the 40-question test set (chapter 13)
| Name | Role |
|---|---|
| `build_questions()` / `write_questions()` | computes the 40 questions and expected answers → `data/eval/questions.jsonl` |
| expected answer | `{"kind": "number", "value", "tolerance"}` or `{"kind": "text", "contains": [...]}`, optional `"page"` |
| `PCT_TOL = 0.006` | percentages are printed with 2 decimals |
| `score_answer(answer, expected)` | (correct, reason): any number in the answer within tolerance / all texts present (case-insensitive) / "page N" present |
| `run_evaluation(mode)` | mode, score, out_of, results[id, correct, reason, tools_used, right_tools, steps] |

## export.py (chapter 14)
`export_monthly_pack(period, out_dir)` → path of `surveillance_pack_2026_MM.xlsx`, sheets Summary, Triggers,
Arrears by region, Note.

## agentic.py (chapter 15)
| Name | Role |
|---|---|
| `CHECKLIST` | 4 required steps: run_trigger_tests; stratify_pool(region, balance_90plus); stratify_pool(region, balance); draft_surveillance_note |
| `rule_plan(period)` / `model_plan(brain, period, feedback=None)` | plan = list of {tool, arguments, why}; a model reply that is not a JSON list gives []; feedback = problems of the previous plan, sent when replanning |
| `check_plan(plan, period)` | (completed plan, missing checklist items, rejected steps {step, reason}); rejects unknown tools and steps whose period differs from the goal's |
| `find(results, tool, **args)` / `errors(results)` | first successful result matching tool and arguments (error results skipped) / list of failed steps |
| `self_check(results, period)` | 90+ ratio = stratify(balance_90plus).total / stratify(balance).total vs trigger tool; agree if difference < 1e-6; a missing or failed result gives agree False with `error` |
| `latest_before(memory, period)` | (most recent earlier period in memory, its figures) or (None, None) |
| `load_memory` / `save_memory` | `data/memory/surveillance_memory.json`, keyed by period |
| `compare(previous, current, previous_period=None)` | list of sentences: change in 90+ ratio, payment mode change, main region change |
| `run_surveillance(period, plan_source, brain, memory_dir, out_dir, approve)` | approve True/False/None (None asks with input()); exactly one replan if the plan is rejected/empty or a step fails (model plans only); status "sent", "held for approval" (declined) or "held" (self-check failed, result missing, note not drafted; `reason` set, approval ignored); writes out/outbox or out/drafts/note_2026_MM.md; memory saved only when not held |

## Volume 2 Part E — the Prospectus Analyser tools
Design note for the app chapters: `book/vol2/notes/extract-design.md`.

| Module | Public functions |
|---|---|
| `tools/document.py` | `normalise_line(line)`; `read_pages(pdf_path)` → list of clean lines per page (running header and page numbers removed); `page_texts(pdf_path)`; `document_chunks(pdf_path)`; `search_document(pdf_path, query, top_k=3)` → `{query, results[{page, score, text}]}` |
| `tools/extract.py` | `extract_deal_terms(pdf_path, layer="rules"\|"model"\|"both", brain=None)` → terms (schema `data/schemas/deal_terms.schema.json`) + `layer`, `coverage`, `ungrounded` (+ `model_log` for model/both); `extract_rules`, `extract_model(pdf_path, brain)`, `ground_terms(terms, pdf_path)`, `coverage(terms)`, `combine(rules, model)`, `score_against_key(terms, key)`, `all_fields(terms)`, `SECTIONS`, `SYSTEM_PROMPT` |
| `tools/extract_sim.py` | `simulated_model_brain(answer_key, plant=None)`: a RuleBrain that answers each section from an answer key (NOT a language model) |
| `tools/analyse.py` | `analyse_deal_terms(terms)` → `{deal, credit_enhancement[...], checks[...], checks_passed, checks_failed, checks_not_possible, waterfall, ungrounded_values}` |
| `registry.py` (end of file) | `ANALYSER_TOOLS` (extract_deal_terms, analyse_deal_terms, search_document; each takes `pdf_path`), `analyser_schemas()`, `call_analyser_tool(name, arguments)`. The surveillance `TOOLS` are unchanged (five tools). |
