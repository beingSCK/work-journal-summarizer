"""
Read and parse work journal entries.

This module handles all interactions with the work-journal directory:
- Finding journal entry files by date
- Detecting existing summary files
- Reading entry contents for summarization
"""

import re  # Regular expressions for pattern matching in strings
from datetime import date, timedelta  # date = calendar date, timedelta = duration between dates
from pathlib import Path  # Object-oriented filesystem paths (modern replacement for os.path)


def get_journal_path() -> Path:
    """
    Return the path to the work journal directory.

    Syntax notes:
    - `-> Path` is a "return type hint" - tells readers/tools this function returns a Path object
    - Type hints don't enforce anything at runtime; they're documentation that tools can check
    - Path.home() returns the user's home directory as a Path object
    - The `/` operator is overloaded on Path objects to join path segments (cleaner than os.path.join)
    """
    return Path.home() / "code_directory_top" / "_meta" / "work-journal"


def parse_date_from_filename(filename: str) -> date | None:
    """
    Extract date from a journal filename like '2026-01-07.md'.

    Syntax notes:
    - `date | None` means "returns either a date or None" (Python 3.10+ union syntax)
    - Older code writes this as `Optional[date]` using `from typing import Optional`
    - The `|` union syntax is preferred in modern Python

    Regex breakdown for r"^(\\d{4})-(\\d{2})-(\\d{2})\\.md$":
    - r"..." is a raw string (backslashes aren't escape sequences)
    - ^       = start of string
    - (\\d{4}) = capture group: exactly 4 digits (year)
    - -        = literal hyphen
    - (\\d{2}) = capture group: exactly 2 digits (month)
    - -        = literal hyphen
    - (\\d{2}) = capture group: exactly 2 digits (day)
    - \\.      = literal dot (escaped because . means "any char" in regex)
    - md      = literal "md"
    - $       = end of string

    Args:
        filename: Just the filename, not the full path (e.g., "2026-01-07.md")

    Returns:
        A date object if the filename matches the pattern, None otherwise.
    """
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})\.md$", filename)
    if match:
        # match.group(1) returns the first captured group (year)
        # match.group(2) returns the second captured group (month)
        # match.group(3) returns the third captured group (day)
        # int() converts the string "2026" to the integer 2026
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def find_latest_summary(journal_path: Path) -> date | None:
    """
    Find the most recent summary file and return its date.

    Summary files follow the pattern: YYYY-MM-DD-SUMMARY-14-days.md
    (or YYYY-MM-DD-SUMMARY-14-days-DRAFT.md for drafts)

    Syntax notes:
    - re.compile() pre-compiles a regex pattern for reuse (minor performance benefit)
    - journal_path.iterdir() yields each item in the directory as a Path object
    - file.name gives just the filename (not the full path)

    Returns:
        The date of the most recent summary, or None if no summaries exist.
    """
    # The .* near the end matches optional suffixes like "-DRAFT"
    summary_pattern = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-SUMMARY-14-days.*\.md$")
    latest = None  # Will hold the most recent summary date we find

    for file in journal_path.iterdir():
        match = summary_pattern.match(file.name)
        if match:
            summary_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            # Update latest if this is the first summary or more recent than previous
            if latest is None or summary_date > latest:
                latest = summary_date

    return latest


def needs_summary(journal_path: Path | None = None, lookback_days: int = 14) -> bool:
    """
    Check if a new summary is needed (no summary within lookback period).

    Syntax notes:
    - `Path | None = None` means: type is Path-or-None, default value is None
    - This pattern lets callers omit the argument while allowing explicit override for testing
    - `int = 14` means: type is int, default value is 14

    Args:
        journal_path: Override the default journal location (useful for testing)
        lookback_days: How many days back to check for existing summaries

    Returns:
        True if we should generate a new summary, False if a recent one exists.
    """
    if journal_path is None:
        journal_path = get_journal_path()

    latest_summary = find_latest_summary(journal_path)
    if latest_summary is None:
        return True  # No summaries exist, definitely need one

    # Calculate days elapsed since the last summary
    # Subtracting two date objects gives a timedelta; .days extracts the integer
    days_since_summary = (date.today() - latest_summary).days
    return days_since_summary >= lookback_days


def gather_entries(journal_path: Path | None = None, lookback_days: int = 14) -> list[dict]:
    """
    Gather journal entries from the last N days.

    Syntax notes:
    - `list[dict]` is a type hint meaning "a list containing dict objects"
    - More precise would be `list[dict[str, date | str]]` but that's verbose
    - timedelta(days=14) creates a duration of 14 days

    Args:
        journal_path: Override the default journal location (useful for testing)
        lookback_days: How many days of entries to gather

    Returns:
        List of dicts with 'date', 'filename', and 'content' keys,
        sorted by date ascending (oldest first for chronological reading).
    """
    if journal_path is None:
        journal_path = get_journal_path()

    # Calculate the oldest date we'll include
    # date.today() returns today's date; subtracting timedelta shifts it back
    cutoff = date.today() - timedelta(days=lookback_days)
    entries = []

    for file in journal_path.iterdir():
        entry_date = parse_date_from_filename(file.name)

        # Skip files that don't match the date pattern (like SUMMARY files)
        # Also skip entries older than our cutoff
        if entry_date and entry_date >= cutoff:
            entries.append({
                "date": entry_date,
                "filename": file.name,
                # file.read_text() reads the entire file as a string
                # Path objects have this method built in (no need for open())
                "content": file.read_text(),
            })

    # Sort entries by date, oldest first
    # key=lambda e: e["date"] tells sort() to compare entries by their "date" value
    # lambda creates a small anonymous function: takes e, returns e["date"]
    entries.sort(key=lambda e: e["date"])
    return entries
