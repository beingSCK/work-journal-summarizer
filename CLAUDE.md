# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Automated bi-weekly summary generator for work journals. Runs daily via launchd, triggers summary generation if no summary exists for the past 14 days, emails the draft for review, and processes email replies to approve or revise.

## Commands

```bash
# Run the summarizer (checks if summary needed, generates if so)
uv run python -m summarizer

# Force generation even if recent summary exists
uv run python -m summarizer --force

# Dry run (show what would be summarized, don't call API)
uv run python -m summarizer --dry-run

# Check for and process email replies
uv run python -m summarizer --check-replies

# Daily heartbeat: auto-wrapup stale checkpoints, send status email
uv run python -m summarizer --heartbeat

# Custom date range
uv run python -m summarizer --days 7
```

## Architecture

```
src/summarizer/
├── main.py              # CLI entry point, orchestrates the flow
├── journal.py           # Reads work-journal/, parses dates, detects existing summaries
├── summarize.py         # Claude API integration, prompt construction
├── email_sender.py      # Gmail API + OAuth for sending/reading emails
├── reply_processor.py   # Classifies replies with Haiku, takes action
├── heartbeat.py         # Daily heartbeat: auto-wrapup + status email
└── config.py            # Configuration management with defaults + YAML
```

**Main flow**: main.py → journal.py (gather) → summarize.py (Claude) → email_sender.py (send)

**Reply flow**: main.py --check-replies → reply_processor.py → Haiku classification → action + confirmation email

**Heartbeat flow**: main.py --heartbeat → heartbeat.py (check stale checkpoints, auto-wrapup, fun fact) → email_sender.py

## Key Paths

- Work journal base: Configured in `config/config.yaml` (default: `~/code-directory-top/_meta/work-journal/`)
  - Daily entries: `{base}/daily-entries/` - Journal entries (YYYY-MM-DD.md)
  - Summaries: `{base}/periodic-summaries/` - Bi-weekly summaries
  - Staging: `{base}/daily-staging/` - Checkpoint staging area
- Anthropic API key: `~/.secrets/shared/anthropic-api-key.txt`
- Gmail OAuth credentials: `~/.secrets/work-journal-summarizer/gmail-client-secret.json`
- Gmail tokens: `~/.secrets/work-journal-summarizer/gmail-token.json`
- Config: `config/config.yaml`

## Conventions

- Summary files: `YYYY-MM-DD-SUMMARY-14-days-DRAFT.md` (draft), `YYYY-MM-DD-SUMMARY-14-days.md` (finalized)
- Summaries are saved to the `periodic-summaries/` subfolder
- Uses `uv` for package management
- Extensive inline comments for educational purposes

## Scheduling

Three launchd jobs in `launchd/`:
- `com.sck.work-journal-summarizer` - Daily at 10am: Check if summary needed, generate and email
- `com.sck.work-journal-summarizer-replies` - Hourly: Check for email replies and process
- `com.das.heartbeat` - Daily at 1am: Auto-wrapup stale checkpoints, send heartbeat email

Install: `./scripts/install-scheduled-jobs.sh`
Uninstall: `./scripts/uninstall-scheduled-jobs.sh`

Verify: `launchctl list | grep -E 'work-journal|das'`
