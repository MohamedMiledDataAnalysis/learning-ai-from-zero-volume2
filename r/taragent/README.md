# taragent — the structured finance agent in R

The R twin of `python/tar_agent`: the same five tools, the same registry, the same rule brain and the
same 40-question evaluation, for the fictional deal Thames Auto Receivables 2026-1 plc.

## Requirements

R 4.3 or later with the packages `jsonlite`, `httr2`, `pdftools`, `openxlsx`, `testthat` and, for the app,
`shiny` and `commonmark`. A live model needs [Ollama](https://ollama.com) with `ollama pull qwen2.5:7b`.

## Use

Run every command from the repository root (the folder that contains `book/` and `r/`).

```bash
Rscript r/taragent/cli.R ask "Run the trigger tests for period 10." --mode rules
Rscript r/taragent/cli.R ask "Which region holds most of the 90+ day arrears in October 2026?" --mode live
Rscript r/taragent/cli.R evaluate --mode rules
Rscript r/taragent/cli.R export --period 10 --out out
Rscript r/taragent/cli.R surveil --period 10 --approve
Rscript -e "shiny::runApp('r/vol2/ch25', launch.browser = TRUE)"
```

Modes: `rules` (no model), `live` (Ollama), `record` (live, and the replies are saved), `replay` (plays a
recording back).

In an R session: `source("r/taragent/load.R")`, then call any function, for example
`run_trigger_tests(10)` or `draft_surveillance_note(10)`.

## Files

| File | Content |
|---|---|
| `load.R` | sources the agent core and every file below |
| `data.R` | reading the deal pack |
| `tools/` | the five tools |
| `registry.R` | tool descriptions and schemas; `call_tool()` |
| `agent.R` | system prompt, rule brain, `ask()` |
| `evaluate.R` | scorer and `run_evaluation()` |
| `export.R` | the monthly Excel pack |
| `agentic.R` | the monthly surveillance cycle with human approval |
| `cli.R` | the command line |
| `load_analyser.R` | loads everything above plus the Prospectus Analyser tools of Part E |
| `tools/document.R`, `tools/extract.R`, `tools/extract_sim.R`, `tools/analyse.R` | read any PDF, extract the deal terms (rules / model / both, with the grounding check), the simulated model for tests, the analysis |
| `registry_analyser.R` | `ANALYSER_TOOLS` and `call_analyser_tool()` (the surveillance registry keeps its five tools) |

## Tests

```bash
Rscript -e "testthat::test_dir('r/tests')"
```

`r/tests/test_vol2_partD.R` compares every tool with the Python tool on the same data;
`r/tests/test_vol2_partE.R` does the same for the extraction and analysis of both prospectuses.
