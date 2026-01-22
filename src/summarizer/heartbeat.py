"""
Daily heartbeat for Work Continuity System.

This module runs at 1am to:
1. Check for stale checkpoint files from yesterday
2. If stale files exist → run auto-wrapup (synthesize journal entry)
3. Read yesterday's work journal
4. Fetch a real "on this day" fact from Wikipedia
5. Send heartbeat email proving the system is alive

Why heartbeat > silent auto-wrapup:
- Silence is ambiguous (working? broken? nothing to do?)
- Daily email proves system is running
- Fun fact makes it worth opening (not just noise)

Why fetch facts from Wikipedia instead of generating them:
- LLMs hallucinate plausible-sounding but false facts
- Even with "cite your source" prompts, they invent fake citations
- Fetching from a real API ensures verifiable, accurate facts
"""

import re
from datetime import date, timedelta
from pathlib import Path

import anthropic
import requests  # For fetching Wikipedia API

from . import config
from .email_sender import send_email


def get_yesterday() -> date:
    """Get yesterday's date."""
    return date.today() - timedelta(days=1)


def check_stale_staging(staging_path: Path | None = None) -> list[date]:
    """
    Check for stale checkpoint files in daily-staging/.

    Returns list of dates that have stale checkpoints (not today).
    """
    if staging_path is None:
        staging_path = config.get_staging_path()

    if not staging_path.exists():
        return []

    stale_dates = []
    today = date.today()

    # Pattern: YYYY-MM-DD-checkpoints.md
    checkpoint_pattern = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-checkpoints\.md$")

    for file in staging_path.iterdir():
        match = checkpoint_pattern.match(file.name)
        if match:
            file_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if file_date < today:
                stale_dates.append(file_date)

    return sorted(stale_dates)


def read_checkpoint_file(checkpoint_date: date, staging_path: Path | None = None) -> str | None:
    """Read checkpoint file for a specific date."""
    if staging_path is None:
        staging_path = config.get_staging_path()

    filename = f"{checkpoint_date.isoformat()}-checkpoints.md"
    filepath = staging_path / filename

    if filepath.exists():
        return filepath.read_text()
    return None


def read_journal_entry(entry_date: date, entries_path: Path | None = None) -> str | None:
    """Read journal entry for a specific date."""
    if entries_path is None:
        entries_path = config.get_entries_path()

    filename = f"{entry_date.isoformat()}.md"
    filepath = entries_path / filename

    if filepath.exists():
        return filepath.read_text()
    return None


def synthesize_journal_from_checkpoints(checkpoint_content: str, target_date: date) -> str:
    """
    Use Claude to synthesize checkpoint notes into a journal entry.

    This is a simplified auto-wrapup that creates a basic journal entry
    from checkpoint files when no manual wrap-up was done.
    """
    api_key_path = config.get_shared_secrets_path() / "anthropic-api-key.txt"
    api_key = api_key_path.read_text().strip()
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Please synthesize these checkpoint notes from {target_date.isoformat()} into a concise work journal entry.

The entry should follow this structure:

# Work Journal: {target_date.isoformat()}

## Session 1: [Derive focus from checkpoints]

### What Was Worked On
- [Bullet points from checkpoints]

### Current Status
[State at end of day]

---

Here are the checkpoint notes to synthesize:

{checkpoint_content}

---

Create a concise journal entry. Focus on what was accomplished, not process details. If multiple sessions are evident from time gaps, create multiple session sections."""

    message = client.messages.create(
        model=config.get("anthropic.summary_model"),
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def auto_wrapup(target_date: date) -> bool:
    """
    Run automatic wrap-up for a specific date.

    1. Read checkpoint file
    2. Synthesize into journal entry
    3. Write journal entry
    4. Clear checkpoint file

    Returns True if successful, False if no checkpoints found.
    """
    staging_path = config.get_staging_path()
    entries_path = config.get_entries_path()

    # Read checkpoints
    checkpoint_content = read_checkpoint_file(target_date, staging_path)
    if not checkpoint_content:
        return False

    # Check if journal already exists (don't overwrite)
    existing_journal = read_journal_entry(target_date, entries_path)
    if existing_journal:
        # Journal exists, just clear the stale checkpoint
        checkpoint_file = staging_path / f"{target_date.isoformat()}-checkpoints.md"
        checkpoint_file.unlink()
        return True

    # Synthesize journal entry
    journal_content = synthesize_journal_from_checkpoints(checkpoint_content, target_date)

    # Write journal entry
    entries_path.mkdir(parents=True, exist_ok=True)
    journal_file = entries_path / f"{target_date.isoformat()}.md"
    journal_file.write_text(journal_content)

    # Clear checkpoint file
    checkpoint_file = staging_path / f"{target_date.isoformat()}-checkpoints.md"
    checkpoint_file.unlink()

    return True


# ---------------------------------------------------------------------------
# News Headlines (replaces fun facts with real, verifiable content)
# ---------------------------------------------------------------------------

# RSS feeds that have been verified to work (Jan 2026)
NEWS_FEEDS = {
    "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
    "Caixin": "https://gateway.caixin.com/api/data/global/feedlyRss.xml",
    "Rest of World": "https://restofworld.org/feed/latest",
    "FT": "https://www.ft.com/rss/home",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
}


def fetch_rss_headlines(feed_url: str, max_items: int = 3) -> list[dict]:
    """
    Fetch headlines from an RSS feed.

    Returns list of dicts with 'title' and 'link' keys.
    """
    import xml.etree.ElementTree as ET

    try:
        # Follow redirects, set timeout, add user agent
        response = requests.get(
            feed_url,
            timeout=10,
            allow_redirects=True,
            headers={"User-Agent": "WorkContinuityBot/1.0"}
        )
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # RSS feeds have items under channel/item
        items = root.findall(".//item")[:max_items]

        headlines = []
        for item in items:
            title_elem = item.find("title")
            link_elem = item.find("link")

            if title_elem is not None and title_elem.text:
                # Clean up CDATA wrappers if present
                title = title_elem.text.strip()
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""

                headlines.append({"title": title, "link": link})

        return headlines

    except Exception as e:
        print(f"  Warning: Failed to fetch {feed_url}: {e}")
        return []


def fetch_all_headlines() -> dict[str, list[dict]]:
    """
    Fetch headlines from all configured news sources.

    Returns dict mapping source name to list of headlines.
    """
    all_headlines = {}

    for source_name, feed_url in NEWS_FEEDS.items():
        print(f"  Fetching {source_name}...")
        headlines = fetch_rss_headlines(feed_url, max_items=3)
        if headlines:
            all_headlines[source_name] = headlines
            print(f"    Got {len(headlines)} headlines")
        else:
            print(f"    No headlines (feed may be down)")

    return all_headlines


def synthesize_news_vibe(headlines: dict[str, list[dict]]) -> str:
    """
    Use Claude to synthesize a brief "news vibe" from real headlines.

    The output includes actual links so facts are verifiable.
    """
    if not headlines:
        return "📰 *News feeds unavailable today*"

    # Build the headlines text
    headlines_text = ""
    for source, items in headlines.items():
        headlines_text += f"\n**{source}:**\n"
        for item in items:
            headlines_text += f"- {item['title']}\n"

    api_key_path = config.get_shared_secrets_path() / "anthropic-api-key.txt"
    api_key = api_key_path.read_text().strip()
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Here are today's headlines from several news sources:

{headlines_text}

Write a brief "news vibe" summary (3-5 sentences) that captures the overall mood/themes of today's news. Don't try to cover everything - just give a sense of what's happening in the world.

Requirements:
- Conversational tone, like a friend giving you the gist
- Don't be overly dramatic or sensational
- You can note interesting patterns or contrasts across regions
- No AI-speak ("notably", "significantly", "it's worth noting")
- End with one specific headline that caught your attention (include the source)

Example output style:
"Feels like a tech-heavy news day with AI chips and e-commerce regulation dominating the Asia coverage. Europe is dealing with political fallout from [topic]. Meanwhile in the US, [topic]. The headline that caught my eye: '[specific headline]' (Source)"
"""

    message = client.messages.create(
        model=config.get("anthropic.summary_model"),  # Use Sonnet for quality
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    # Build the full section with links for verification
    vibe = message.content[0].text.strip()

    # Add the raw headlines with links for reference
    links_section = "\n\n**Headlines sourced from:**\n"
    for source, items in headlines.items():
        links_section += f"- {source}: "
        links_section += ", ".join([f"[{i+1}]({item['link']})" for i, item in enumerate(items) if item['link']])
        links_section += "\n"

    return vibe + links_section


def build_heartbeat_email(
    yesterday: date,
    journal_content: str | None,
    auto_wrapup_ran: bool,
    news_vibe: str,
) -> tuple[str, str]:
    """
    Build the heartbeat email subject and body.

    Returns (subject, body) tuple.
    """
    today = date.today()

    subject = f"☀️ Daily Heartbeat: {today.isoformat()}"

    # Journal summary section
    if journal_content:
        # Extract just the first ~500 chars for the summary
        journal_preview = journal_content[:800]
        if len(journal_content) > 800:
            journal_preview += "\n\n[... full entry in work-journal]"
        journal_section = f"""## Yesterday's Work ({yesterday.isoformat()})

{journal_preview}"""
    else:
        journal_section = f"""## Yesterday's Work ({yesterday.isoformat()})

_No journal entry found for yesterday._"""

    # Status section
    status = "✅ Auto-wrapup ran (synthesized from checkpoints)" if auto_wrapup_ran else "✅ Journal already existed"

    body = f"""Good morning!

Your Work Continuity System is running.

---

{journal_section}

---

## System Status

{status}

---

## News Vibe

{news_vibe}

---

_Heartbeat sent at {today.isoformat()} 01:00_
_Work Continuity System | work-journal-summarizer_
"""

    return subject, body


def send_heartbeat_email(subject: str, body: str) -> bool:
    """Send the heartbeat email."""
    return send_email(
        to=config.get("email.to"),
        subject=subject,
        body=body,
        from_addr=config.get("email.from"),
    )


def run_heartbeat() -> int:
    """
    Main heartbeat function. Called at 1am daily.

    Returns:
        0 for success, 1 for error
    """
    yesterday = get_yesterday()
    print(f"Running daily heartbeat for {date.today().isoformat()}...")
    print(f"Checking work from {yesterday.isoformat()}...")

    # Step 1: Check for stale checkpoints
    stale_dates = check_stale_staging()
    auto_wrapup_ran = False

    if stale_dates:
        print(f"Found stale checkpoints for: {[d.isoformat() for d in stale_dates]}")

        # Process each stale date (usually just yesterday)
        for stale_date in stale_dates:
            print(f"  Running auto-wrapup for {stale_date.isoformat()}...")
            if auto_wrapup(stale_date):
                print(f"  ✓ Auto-wrapup complete for {stale_date.isoformat()}")
                if stale_date == yesterday:
                    auto_wrapup_ran = True
            else:
                print(f"  ✗ No checkpoints found for {stale_date.isoformat()}")
    else:
        print("No stale checkpoints found.")

    # Step 2: Read yesterday's journal (may have just been created)
    journal_content = read_journal_entry(yesterday)
    if journal_content:
        print(f"Found journal entry for {yesterday.isoformat()} ({len(journal_content):,} chars)")
    else:
        print(f"No journal entry found for {yesterday.isoformat()}")

    # Step 3: Fetch news headlines and synthesize
    print("Fetching news headlines...")
    try:
        headlines = fetch_all_headlines()
        print("Synthesizing news vibe...")
        news_vibe = synthesize_news_vibe(headlines)
        print(f"News vibe: {news_vibe[:80]}...")
    except Exception as e:
        print(f"Error fetching/synthesizing news: {e}")
        news_vibe = "📰 *News unavailable today - feeds may be down*"

    # Step 4: Build and send email
    subject, body = build_heartbeat_email(yesterday, journal_content, auto_wrapup_ran, news_vibe)

    print("\nSending heartbeat email...")
    if send_heartbeat_email(subject, body):
        print("✓ Heartbeat email sent!")
        return 0
    else:
        print("✗ Failed to send heartbeat email")
        return 1


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.exit(run_heartbeat())
