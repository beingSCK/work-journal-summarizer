# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Automated bi-weekly summary generator for Sean's work journal (`~/code_directory_top/_meta/work-journal/`). Runs daily via launchd, triggers summary generation if no summary exists for the past 14 days, and emails the draft for review.

## Commands

```bash
# Run the summarizer (checks if summary needed, generates if so)
uv run python -m summarizer

# Run with explicit date range
uv run python -m summarizer --days 14

# Dry run (show what would be summarized, don't call API)
uv run python -m summarizer --dry-run
```

## Architecture

```
src/summarizer/
├── main.py          # CLI entry point, orchestrates the flow
├── journal.py       # Reads work-journal/, parses dates, detects existing summaries
├── summarize.py     # Claude API integration, prompt construction
└── email_sender.py  # Gmail API + OAuth for sending drafts
```

**Flow**: main.py calls journal.py to gather entries → passes to summarize.py → saves draft + calls email_sender.py

## Key Paths

- Work journal source: `~/code_directory_top/_meta/work-journal/`
- Anthropic API key: `~/.secrets/anthropic-key-api.txt`
- Gmail OAuth credentials: `./credentials/client_secret.json`
- Gmail tokens: `./credentials/gmail_token.json`
- Config: `./config/config.yaml`

## Conventions

- Summary files: `YYYY-MM-DD-SUMMARY-14-days-DRAFT.md` (draft), `YYYY-MM-DD-SUMMARY-14-days.md` (finalized)
- Summaries are saved to the work-journal folder alongside regular entries
- Uses `uv` for package management
