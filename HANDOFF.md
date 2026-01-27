# HANDOFF - smart-pigeon 🐦
_Last updated: 2026-01-27_

## Session Recap

**2026-01-27: Renamed to smart-pigeon + VPS deployment**
- Renamed project: work-journal-summarizer → smart-pigeon
- GitHub repo renamed via `gh repo rename`
- Updated all references in CLAUDE.md files, HANDOFF.md, launchd plists
- Deploying to VPS with git-based sync for work-journal and claude-steering docs

**2026-01-22 (PM): Reply processor bug fix + first PR**
- Diagnosed bug: `finalize_draft()` searched wrong directory (base instead of `periodic-summaries/`)
- Fixed and manually finalized the pending summary draft
- Created PR #1 with all uncommitted work (6 commits)
- Ran 5-agent code review, found 2 issues (config path, stale OAuth comment)
- Fixed issues, merged to main: https://github.com/beingSCK/smart-pigeon/pull/1

**2026-01-22 (AM): Full automation deployed**
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
| Reply processing | ✅ Complete (fixed `finalize_draft` path bug) |
| Heartbeat module | ✅ Daily email with auto-wrapup + news |
| Config system | ✅ Complete (fixed paths) |
| Mac launchd scheduling | ✅ Installed (but Mac sleeps at 1am) |
| VPS systemd scheduling | 🚧 In progress |

## Scheduling

### Mac (launchd)

```bash
launchctl list | grep -E 'smart-pigeon|das'
```

| Job | Schedule | Purpose |
|-----|----------|---------|
| `com.sck.smart-pigeon` | 10am daily | Bi-weekly summary generation |
| `com.sck.smart-pigeon-replies` | Hourly | Process email replies |
| `com.das.heartbeat` | 1am daily | Auto-wrapup + news vibe email |

**Logs:** `tail -f ~/Library/Logs/smart-pigeon.log`

### VPS (systemd)

```bash
systemctl --user list-timers
```

| Timer | Schedule | Purpose |
|-------|----------|---------|
| `smart-pigeon.timer` | 1am UTC daily | Full heartbeat (auto-wrapup + news) |

**Logs:** `journalctl --user -u smart-pigeon.service`

## Heartbeat Module Details

The heartbeat (`heartbeat.py`) runs at 1am and:
1. Checks for stale checkpoint files from yesterday
2. If found, auto-synthesizes journal entry from checkpoints
3. Fetches headlines from 5 RSS feeds (Bloomberg, Caixin, Rest of World, FT, NPR)
4. Uses Claude Sonnet to synthesize a "news vibe" summary
5. Sends email with: yesterday's work, system status, news vibe with source links

**Why news instead of fun facts:** LLMs hallucinate "facts" even when asked to cite sources. RSS feeds provide ground truth; Claude synthesizes. Each component does what it's good at.

## Folder Structure

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

# Mac launchd management
launchctl start com.das.heartbeat          # Test heartbeat now
./scripts/uninstall-scheduled-jobs.sh      # Remove all jobs
./scripts/install-scheduled-jobs.sh        # Reinstall all jobs

# VPS systemd management
systemctl --user start smart-pigeon.service  # Test heartbeat now
systemctl --user status smart-pigeon.timer   # Check timer status
```

## Recommended Next Action

**Complete VPS deployment:**
1. Clone smart-pigeon to VPS
2. Transfer secrets (Anthropic key, Gmail OAuth tokens)
3. Set up systemd timer
4. Verify heartbeat email from VPS

## Future Enhancements (Lower Priority)

- **HTML email templates**: Convert markdown to styled HTML
- **Batch API**: 50% cost savings (non-urgent, current costs are minimal)
- **Additional news sources**: Add/swap feeds as preferences evolve
- **Dashboard**: Web UI for viewing journals + summaries

## Architecture Quick Reference

```
src/summarizer/
├── main.py              # CLI entry point
├── journal.py           # Reads work-journal/ subfolders
├── summarize.py         # Claude API for summaries
├── heartbeat.py         # Daily heartbeat + auto-wrapup
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
