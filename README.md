# Learning AI from Zero — Volume 2: Building an AI Agent for Structured Finance

Companion repository for *Learning AI from Zero — Build Your Own AI Agent*, Volume 2, by Mohamed Miled.

| Folder | What it holds |
|---|---|
| `python/tar_agent/` | The structured finance agent in Python: five surveillance tools, registry, agent, evaluation, Excel export, agentic version, prospectus extraction and analysis |
| `r/taragent/` | The same agent in R |
| `python/agent_core/`, `r/agentcore/` | The agent loop and the four brains (rules, replay, live, record) |
| `python/vol2/chNN/`, `r/vol2/chNN/` | The code of each chapter, including the Shiny surveillance app (ch25), the Prospectus Analyser in Shiny (ch26) and in Dash (ch27) |
| `data/` | The Thames Auto Receivables 2026-1 deal pack, the Severn Residential Mortgages 2026-1 prospectus, the 40-question test set and the answer keys |
| `generator/` | The seeded scripts that rebuild both deals, their prospectuses and the answer keys |
| `python/tests/`, `r/tests/`, `tests/` | The tests that check every figure printed in the book |

## Run the apps

```bash
Rscript -e "shiny::runApp('r/vol2/ch25', launch.browser = TRUE)"   # surveillance app (Shiny)
Rscript -e "shiny::runApp('r/vol2/ch26', launch.browser = TRUE)"   # Prospectus Analyser (Shiny)
python python/vol2/ch27/app.py       # Prospectus Analyser (Dash)
```

## Set up

You need Python 3.13 and R 4.3 (Volume 1, chapter 2 walks through the installation on Windows, macOS and Linux).

```bash
pip install -r requirements.txt                    # Python packages, pinned
Rscript r/install_packages.R                       # R packages (the list and tested versions are in the file)
python tests/check_deal_pack.py                    # the deal pack: 188 consistency checks
cd python && python -m pytest -q                   # the Python tests
cd .. && Rscript -e "testthat::test_dir('r/tests')"   # the R tests
```

Some R tests and scripts compare R with Python, so run the R tests with Python and its packages installed.

## Model replies: rules, replay, live, record

Scripts that use a language model take `--mode rules|replay|live|record`. Rules and replay need no model.
Live and record need [Ollama](https://ollama.com) running locally with the pinned model:

```bash
ollama pull qwen2.5:7b
python python/record_all.py      # records every reply the book prints
```

You can also record on GitHub: **Actions > Record model replies > Run workflow**, then download the
`recordings` artifact and copy its files into `python/recordings/` and `r/recordings/`.

All names, loans and figures in the deal data are fictional.
