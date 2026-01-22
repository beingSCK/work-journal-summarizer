# HANDOFF - Work Journal Summarizer
_Last updated: 2026-01-22_

## Session Recap

**2026-01-22: Full automation deployed**
- Fixed path bug (`code_directory_top` → `code-directory-top`) in config + launchd plists
- Reorganized work-journal folder: `daily-entries/`, `daily-staging/`, `periodic-summaries/`
- Built heartbeat module with "News Vibe" feature (real RSS headlines, not hallucinated facts)
- Installed all 3 launchd jobs - system is now running automatically

## Current State

| Component | Status |
|-----------|--------|
| Journal reading | ✅ Complete (updated for subfolder structure) |
| Claude summarization | ✅ Complete |
| Gmail email sending | ✅ Complete |
| Reply processing | ✅ Complete |
| Heartbeat module | ✅ **NEW** - Daily email with auto-wrapup + news |
| Config system | ✅ Complete (fixed paths) |
| launchd scheduling | ✅ **INSTALLED** |

**All known issues resolved.**

## launchd Jobs Running

```bash
launchctl list | grep -E 'sck|das'
```

| Job | Schedule | Purpose |
|-----|----------|---------|
| `com.sck.work-journal-summarizer` | 10am daily | Bi-weekly summary generation |
| `com.sck.work-journal-summarizer-replies` | Hourly | Process email replies |
| `com.das.heartbeat` | 1am daily | Auto-wrapup + news vibe email |

**Logs:** `tail -f ~/Library/Logs/work-journal-summarizer.log`

## Heartbeat Module Details

The heartbeat (`heartbeat.py`) runs at 1am and:
1. Checks for stale checkpoint files from yesterday
2. If found, auto-synthesizes journal entry from checkpoints
3. Fetches headlines from 5 RSS feeds (Bloomberg, Caixin, Rest of World, FT, NPR)
4. Uses Claude Sonnet to synthesize a "news vibe" summary
5. Sends email with: yesterday's work, system status, news vibe with source links

**Why news instead of fun facts:** LLMs hallucinate "facts" even when asked to cite sources. RSS feeds provide ground truth; Claude synthesizes. Each component does what it's good at.

## Folder Structure (New)

```
_meta/work-journal/
├── daily-entries/           # Journal entries (YYYY-MM-DD.md)
├── daily-staging/           # Checkpoint staging (cleared by wrap-up)
└── periodic-summaries/      # Bi-weekly summaries
```

## Commands

```bash
# Manual runs
uv run python -m summarizer --dry-run      # Preview what would be summarized
uv run python -m summarizer --force        # Force summary generation
uv run python -m summarizer --heartbeat    # Run daily heartbeat
uv run python -m summarizer --check-replies # Process email replies

# launchd management
launchctl start com.das.heartbeat          # Test heartbeat now
./scripts/uninstall-scheduled-jobs.sh      # Remove all jobs
./scripts/install-scheduled-jobs.sh        # Reinstall all jobs
```

## Recommended Next Action

**Verify automation over 24-48 hours:**
1. Tomorrow at 1am: Heartbeat email should arrive automatically
2. Check logs if it doesn't: `tail ~/Library/Logs/work-journal-summarizer.log`
3. In ~14 days: Bi-weekly summary should trigger at 10am

The system is fully operational. No action needed unless something breaks.

## Future Enhancements (Lower Priority)

- **HTML email templates**: Convert markdown to styled HTML
- **Batch API**: 50% cost savings (non-urgent, current costs are minimal)
- **Additional news sources**: Add/swap feeds as preferences evolve
- **Dashboard**: Web UI for viewing journals + summaries (Phase 4 of Work Continuity roadmap)

## Architecture Quick Reference

```
src/summarizer/
├── main.py              # CLI entry point
├── journal.py           # Reads work-journal/ subfolders
├── summarize.py         # Claude API for summaries
├── heartbeat.py         # NEW: Daily heartbeat + auto-wrapup
├── email_sender.py      # Gmail OAuth + sending
├── reply_processor.py   # Classifies replies with Haiku
└── config.py            # Centralized configuration
```

**RSS Feeds (verified working):**
- Bloomberg: `https://feeds.bloomberg.com/markets/news.rss`
- Caixin: `https://gateway.caixin.com/api/data/global/feedlyRss.xml`
- Rest of World: `https://restofworld.org/feed/latest`
- FT: `https://www.ft.com/rss/home`
- NPR: `https://feeds.npr.org/1001/rss.xml`
