# Thames Auto Receivables 2026-1 — surveillance agent

A surveillance assistant for the securitisation Thames Auto Receivables 2026-1 plc.
Run every command from the `python/` folder.

## Install

    pip install -r ../requirements.txt
    ollama pull qwen2.5:7b          # only for --mode live

## Daily use

| Task | Command |
|---|---|
| Ask a question | `python -m tar_agent.agent "Run the trigger tests for period 10."` |
| Ask with the local model | add `--mode live` |
| Answer only, no steps | add `--quiet` |
| Excel pack for a month | `python -m tar_agent.export --period 10 --out ../out` |
| Monthly surveillance cycle | `python -m tar_agent.agentic --period 10` (asks before sending) |
| Score the agent | `python -m tar_agent.evaluate run --mode rules` |
| Run all tests | `python -m pytest -q` |

## Modes

`rules` (default): fixed rules, no model, same result everywhere.
`live`: the local model in Ollama decides. `record`: live, and saves the replies.
`replay`: plays back saved replies.

## What the agent will not do

It answers only from the five tools. It does not give investment advice. It never sends a note without a
human's approval, and never sends one whose self-check failed. The `--approve` flag is the one exception
you choose yourself: it sends without asking, so nobody reads the note first.
