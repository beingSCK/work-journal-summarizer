# Work Journal Summarizer

An automated bi-weekly summary generator for your work journal. Runs daily via macOS launchd, generates AI-powered summaries using Claude, and emails them for your review.

## What This Does

Every day at 10:00 AM, this system:
1. Checks if 14 days have passed since your last summary
2. If yes: gathers the last 14 days of journal entries
3. Sends them to Claude Sonnet for summarization
4. Emails you the draft summary for review
5. Polls hourly for your email replies (approve/revise)

This is a **"Level 2.5" automation**: it creates drafts AND can finalize them based on your explicit email approval, but never takes action without your consent.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Set up secrets (see Secrets Setup below)

# 3. Configure (copy and edit)
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your settings

# 4. Test manually
uv run python -m summarizer --dry-run  # See what would happen
uv run python -m summarizer --force    # Actually generate a summary

# 5. Install automation (optional)
./scripts/install-scheduled-jobs.sh
```

## Secrets Setup

This project uses the `~/.secrets/` pattern to keep credentials out of the repo.

### 1. Anthropic API Key

```bash
# Create the shared folder (for keys used by multiple projects)
mkdir -p ~/.secrets/shared

# Add your Anthropic API key
echo "your-anthropic-api-key" > ~/.secrets/shared/anthropic-api-key.txt
```

### 2. Gmail OAuth (for sending/reading emails)

```bash
# Create project-specific folder
mkdir -p ~/.secrets/work-journal-summarizer

# Get OAuth credentials from Google Cloud Console:
# 1. Go to console.cloud.google.com
# 2. Create or select a project
# 3. Enable Gmail API (APIs & Services > Enable APIs)
# 4. Create OAuth credentials (APIs & Services > Credentials > Create > OAuth client ID)
# 5. Choose "Desktop app" as application type
# 6. Download the JSON file

# Save it as:
mv ~/Downloads/client_secret_*.json ~/.secrets/work-journal-summarizer/gmail-client-secret.json
```

On first run, a browser window will open for Gmail authorization. The resulting token is saved to `~/.secrets/work-journal-summarizer/gmail-token.json` and auto-refreshes.

## Commands

```bash
# Run the summarizer (checks if summary needed, generates if so)
uv run python -m summarizer

# Force generation even if recent summary exists
uv run python -m summarizer --force

# Preview without calling APIs
uv run python -m summarizer --dry-run

# Check for and process email replies
uv run python -m summarizer --check-replies

# Custom date range
uv run python -m summarizer --days 7
```

## Scheduling

### Install Automation

```bash
./scripts/install-scheduled-jobs.sh
```

This installs two launchd jobs:
- **Daily at 10:00 AM**: Check if summary needed, generate and email if so
- **Hourly**: Check for email replies and process them

### Manage Jobs

```bash
# See installed jobs
launchctl list | grep work-journal

# View logs
tail -f ~/Library/Logs/work-journal-summarizer.log

# Manually trigger
launchctl start com.yourname.work-journal-summarizer

# Disable temporarily (job stays installed)
launchctl unload ~/Library/LaunchAgents/com.yourname.work-journal-summarizer.plist

# Re-enable
launchctl load ~/Library/LaunchAgents/com.yourname.work-journal-summarizer.plist
```

### Uninstall Automation

```bash
./scripts/uninstall-scheduled-jobs.sh
```

This removes the scheduled jobs but preserves your journal entries, summaries, and configuration.

---

## 🎓 How It Works

This section explains the underlying concepts. Useful for learning or troubleshooting.

### launchd 101

**What is launchd?**
macOS's native task scheduler, replacing the older Unix `cron` system. It runs as a system service and manages background jobs.

**Why launchd over cron?**
- Handles sleep/wake cycles properly (catches up on missed jobs)
- Automatic retry on failure
- Integrated logging
- Can specify dependencies between jobs

**The plist file format:**
launchd uses Property List (plist) files - Apple's XML-based configuration format. Example structure:

```xml
<dict>
    <key>Label</key>           <!-- Unique job identifier -->
    <string>com.yourname.work-journal-summarizer</string>

    <key>ProgramArguments</key> <!-- Command to run -->
    <array>
        <string>/path/to/uv</string>
        <string>run</string>
        <string>python</string>
        <string>-m</string>
        <string>summarizer</string>
    </array>

    <key>StartCalendarInterval</key>  <!-- When to run -->
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
```

**Where jobs live:**
- `~/Library/LaunchAgents/` - User-level jobs (run when YOU log in)
- `/Library/LaunchAgents/` - System-wide, run for any user
- `/Library/LaunchDaemons/` - System-level, run even when no one logged in

### Naming Convention: com.yourname.project

The job name follows "reverse DNS" style:
- `com` = commercial (vs `org` for nonprofits, `edu` for education)
- `yourname` = your identifier (initials, username, or domain)
- `project` = project name

This convention prevents naming collisions between different developers' jobs. It's an Apple recommendation, not a technical requirement.

### OAuth Flow Explained

**Why can't we just use a password?**
Google disabled "less secure app access" (plain password auth) for security. OAuth is the modern replacement - it grants limited, revocable access without exposing your password.

**The OAuth dance:**

```
┌──────────────┐     1. Request auth      ┌─────────────┐
│  Your App    │ ────────────────────────>│   Google    │
│              │                          │             │
│              │     2. User consents     │             │
│              │ <────────────────────────│   (browser) │
│              │                          │             │
│              │     3. Access token      │             │
│              │ <────────────────────────│             │
└──────────────┘                          └─────────────┘
        │
        │ 4. Use token for API calls
        v
   ┌──────────┐
   │  Gmail   │
   │   API    │
   └──────────┘
```

**Token lifecycle:**
- **Access token**: Short-lived (1 hour), used for API calls
- **Refresh token**: Long-lived, used to get new access tokens
- Both stored in `gmail-token.json`
- The google-auth library handles refresh automatically

**"Client secret isn't really secret":**
For desktop apps, the client secret in `gmail-client-secret.json` isn't truly secret - anyone with the file could use it. The real security comes from:
1. The user must consent in a browser
2. Tokens are stored locally and per-user
3. Access can be revoked at any time in Google account settings

### Where Secrets Live

```
~/.secrets/
├── README.md                          # Index of what's here
├── shared/                            # Cross-project credentials
│   └── anthropic-api-key.txt          # Used by multiple projects
└── work-journal-summarizer/           # Project-specific
    ├── gmail-client-secret.json       # OAuth client (from Google Cloud)
    └── gmail-token.json               # Your auth tokens (auto-generated)
```

**Why this structure?**
- **Discoverability**: `ls ~/.secrets/` shows all projects at a glance
- **Cleanup**: Delete a project folder when you're done
- **Shared vs specific**: Clear which credentials are reusable
- **Outside repo**: Never accidentally committed

### The Feedback Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Daily @ 10am                        Hourly                     │
│  ┌─────────────┐                    ┌─────────────────────────┐ │
│  │ Generate    │                    │ Check for email replies │ │
│  │ summary     │                    │                         │ │
│  │ (Claude     │ ──> Email ──> You  │ ┌─────────────────────┐ │ │
│  │  Sonnet)    │     draft     │    │ │ Classify with       │ │ │
│  └─────────────┘               │    │ │ Claude Haiku        │ │ │
│                                │    │ │ (fast + cheap)      │ │ │
│                                │    │ └─────────────────────┘ │ │
│                                │    │          │              │ │
│                                └────│──────────┘              │ │
│                                     │     │                   │ │
│                                     │     v                   │ │
│                                     │ ┌─────────────────────┐ │ │
│                                     │ │ APPROVE: finalize   │ │ │
│                                     │ │ REVISE: save note   │ │ │
│                                     │ │ UNCLEAR: ask again  │ │ │
│                                     │ └─────────────────────┘ │ │
│                                     └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Why two Claude models?**
- **Sonnet** for summaries: Needs deep understanding, worth the cost
- **Haiku** for classification: Simple yes/no task, 10-20x cheaper, faster

---

## Configuration

All settings in `config/config.yaml`:

```yaml
journal:
  path: "~/path/to/your/work-journal"    # Your journal location
  summary_prefix: "SUMMARY-14-days"       # Output filename pattern
  lookback_days: 14                       # Days to include

email:
  to: "you@example.com"           # Where to send summaries
  from: "robot@example.com"       # Sender address (must match OAuth)
  subject_prefix: "[Work Journal]"

anthropic:
  summary_model: "claude-sonnet-4-5"    # For generating summaries
  classify_model: "claude-haiku-4-5"    # For classifying replies
  max_tokens: 4096

secrets:
  base_path: "~/.secrets"
```

## Troubleshooting

### "Gmail credentials not found"
Run `uv run python -m summarizer --force` manually first. It will open a browser for OAuth. Once authorized, the scheduled jobs will work.

### "No entries found for the last 14 days"
Check that your journal path is correct in `config.yaml` and that you have `.md` files with date filenames like `2026-01-08.md`.

### Job doesn't seem to run
```bash
# Check if job is loaded
launchctl list | grep work-journal

# Check logs for errors
tail -50 ~/Library/Logs/work-journal-summarizer.log

# Test manually
launchctl start com.yourname.work-journal-summarizer
```

### Email not sending
1. Verify OAuth is set up: `ls ~/.secrets/work-journal-summarizer/gmail-token.json`
2. Check that `email.from` in config matches an email address you authorized
3. Check logs for specific error messages

## Project Structure

```
work-journal-summarizer/
├── src/summarizer/
│   ├── main.py              # CLI entry point
│   ├── journal.py           # Journal file reading/parsing
│   ├── summarize.py         # Claude API integration
│   ├── email_sender.py      # Gmail OAuth + sending
│   ├── reply_processor.py   # Reply classification + actions
│   └── config.py            # Configuration management
├── config/
│   ├── config.yaml          # Your settings (gitignored)
│   └── config.example.yaml  # Template (committed)
├── launchd/
│   ├── com.yourname.work-journal-summarizer.plist         # Daily job
│   └── com.yourname.work-journal-summarizer-replies.plist # Hourly job
└── scripts/
    ├── install-scheduled-jobs.sh
    └── uninstall-scheduled-jobs.sh
```

## License

MIT License - see [LICENSE](LICENSE) for details.
