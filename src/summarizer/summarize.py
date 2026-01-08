"""
Generate summaries using the Claude API.

This module handles:
- Loading the Anthropic API key from ~/.secrets/
- Building the summarization prompt
- Calling the Claude API
- Formatting the response
"""

from datetime import date
from pathlib import Path

# The anthropic package is the official Python SDK for Claude
# Installed via: uv add anthropic
import anthropic


def get_anthropic_key() -> str:
    """
    Read the Anthropic API key from the secrets file.

    Syntax notes:
    - Path.home() returns your home directory as a Path object
    - .read_text() reads the entire file as a string
    - .strip() removes leading/trailing whitespace (including newlines)

    The key file should contain just the key, nothing else:
        sk-ant-api03-xxxxx...

    Returns:
        The API key as a string.

    Raises:
        FileNotFoundError: If ~/.secrets/anthropic-key-api.txt doesn't exist.
    """
    key_path = Path.home() / ".secrets" / "anthropic-key-api.txt"
    return key_path.read_text().strip()


def build_prompt(entries: list[dict]) -> str:
    """
    Build the summarization prompt from journal entries.

    Syntax notes:
    - Triple-quoted strings (triple double-quotes) can span multiple lines
    - f-strings (f"...") allow embedding expressions in curly braces
    - The backslash at end of lines continues the string without adding newlines
      (but we use triple quotes here so we don't need that)

    Args:
        entries: List of dicts with 'date', 'filename', and 'content' keys.
                 Expected to be sorted by date ascending.

    Returns:
        The complete prompt string to send to Claude.
    """
    # Get the date range for the summary title
    # entries[0] is the first (oldest) entry, entries[-1] is the last (newest)
    # -1 is Python's way of indexing from the end of a list
    start_date = entries[0]["date"]
    end_date = entries[-1]["date"]

    # Build the entries section by concatenating each entry's content
    # We include clear separators so Claude can distinguish between entries
    entries_text = ""
    for entry in entries:
        # .isoformat() converts a date to "YYYY-MM-DD" string format
        entries_text += f"\n{'='*60}\n"  # 60 equals signs as a separator
        entries_text += f"DATE: {entry['date'].isoformat()}\n"
        entries_text += f"{'='*60}\n\n"
        entries_text += entry["content"]
        entries_text += "\n"

    # The main prompt with instructions for Claude
    # We're explicit about the output format we want
    prompt = f"""Please analyze these work journal entries and create a bi-weekly summary.

DATE RANGE: {start_date.isoformat()} to {end_date.isoformat()}

## Output Format

Create a summary using this exact structure:

# Bi-Weekly Summary: {start_date.isoformat()} to {end_date.isoformat()}

## Overview
[2-3 sentence synthesis of what the past two weeks were about]

## Projects Touched
- **[Project Name]** - [Status/progress summary]

## Key Decisions Made
- [Decision] - [Brief rationale]

## Things Learned
- [Learning with context]

## Friction Points / Blockers
- [What slowed things down]

## Surprises / Contrary to Expectations
- [What happened that you didn't predict]
- [Pattern note if this keeps showing up]

## Looking Ahead
- [Open threads, unresolved questions, momentum to carry forward]

## Journal Entries

{entries_text}

---

Now generate the summary following the format above. Focus on synthesis and patterns rather than just listing what happened. Be concise but insightful."""

    return prompt


def generate_summary(
    entries: list[dict],
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> str:
    """
    Call the Claude API to generate a summary of journal entries.

    Syntax notes:
    - Function parameters can have default values (model="...", max_tokens=4096)
    - Parameters with defaults must come after parameters without defaults
    - anthropic.Anthropic() creates a client; it reads ANTHROPIC_API_KEY env var
      or we can pass api_key= explicitly (which we do here)

    Args:
        entries: List of journal entry dicts from gather_entries().
        model: The Claude model to use. Defaults to Claude Sonnet 4.
        max_tokens: Maximum tokens in the response.

    Returns:
        The generated summary as a string.

    Raises:
        anthropic.APIError: If the API call fails.
        FileNotFoundError: If the API key file doesn't exist.
    """
    # Create the API client with our key
    # We pass the key explicitly rather than using environment variables
    # to keep our secrets management pattern consistent
    client = anthropic.Anthropic(api_key=get_anthropic_key())

    # Build the prompt from the entries
    prompt = build_prompt(entries)

    # Call the Claude API
    # messages.create() is the main method for sending messages to Claude
    # It returns a Message object with the response
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    # Extract the text from the response
    # message.content is a list of content blocks (usually just one for text)
    # content[0].text gets the actual text string
    # We use [0] because the response could theoretically have multiple blocks
    return message.content[0].text


def save_draft(summary: str, journal_path: Path, entries: list[dict]) -> Path:
    """
    Save the summary as a draft file in the journal directory.

    Syntax notes:
    - Path objects support / operator for joining paths
    - .write_text() writes a string to a file (creates or overwrites)
    - f-strings can contain any valid Python expression in the braces

    Args:
        summary: The generated summary text.
        journal_path: Path to the work-journal directory.
        entries: The entries that were summarized (to get the date range).

    Returns:
        The Path to the saved draft file.
    """
    # Use today's date for the filename (when the summary was generated)
    today = date.today().isoformat()
    filename = f"{today}-SUMMARY-14-days-DRAFT.md"
    draft_path = journal_path / filename

    draft_path.write_text(summary)
    return draft_path
