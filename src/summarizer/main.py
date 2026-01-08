"""
Main entry point for the work journal summarizer.

This module orchestrates the full flow:
1. Check if a summary is needed
2. Gather journal entries
3. Generate summary via Claude API
4. Save the draft
5. (Future: send email notification)

Run with: uv run python -m summarizer
"""

import argparse  # Standard library for parsing command-line arguments
import sys  # System-specific parameters and functions (like sys.exit)

# Import from our sibling modules using relative imports
# The dot (.) means "from the current package"
from .journal import gather_entries, get_journal_path, needs_summary
from .summarize import generate_summary, save_draft


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Syntax notes:
    - argparse.ArgumentParser creates a parser that handles --help automatically
    - add_argument() defines each flag/option
    - "--dry-run" creates a flag that's False by default, True when present
    - "--days" creates an option that takes a value
    - parse_args() returns a Namespace object where args.dry_run, args.days, etc. exist

    Returns:
        Namespace object with parsed arguments as attributes.
    """
    # The description shows up when users run with --help
    parser = argparse.ArgumentParser(
        description="Generate bi-weekly summaries of work journal entries."
    )

    # action="store_true" means: if flag is present, set to True; otherwise False
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be summarized without calling the API.",
    )

    # type=int ensures the value is converted to an integer
    # default=14 means if not specified, use 14
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days to look back for entries (default: 14).",
    )

    # --force skips the "needs summary" check
    parser.add_argument(
        "--force",
        action="store_true",
        help="Generate summary even if a recent one exists.",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the summarizer.

    Syntax notes:
    - Returning an int from main() is a convention for exit codes
    - 0 means success, non-zero means error
    - sys.exit(code) would also work, but returning is cleaner

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args()
    journal_path = get_journal_path()

    # Check if we need to generate a summary
    if not args.force and not needs_summary(journal_path, args.days):
        print(f"A summary was generated within the last {args.days} days. Skipping.")
        print("Use --force to generate anyway.")
        return 0

    # Gather entries from the lookback period
    print(f"Gathering entries from the last {args.days} days...")
    entries = gather_entries(journal_path, args.days)

    if not entries:
        print("No journal entries found in the specified period.")
        return 1

    print(f"Found {len(entries)} entries:")
    for entry in entries:
        # entry["date"].isoformat() converts date to "YYYY-MM-DD" string
        # len(entry["content"]) gives the character count
        print(f"  - {entry['date'].isoformat()}: {len(entry['content']):,} chars")

    # In dry-run mode, stop here
    if args.dry_run:
        print("\n[Dry run] Would generate summary from these entries.")
        print("[Dry run] No API call made, no files written.")
        return 0

    # Generate the summary via Claude API
    print("\nGenerating summary via Claude API...")
    try:
        summary = generate_summary(entries)
    except FileNotFoundError:
        print("Error: API key not found at ~/.secrets/anthropic-key-api.txt")
        print("Please create this file with your Anthropic API key.")
        return 1
    except Exception as e:
        # Catch-all for API errors
        # In production code, you'd catch specific exception types
        print(f"Error calling Claude API: {e}")
        return 1

    # Save the draft
    draft_path = save_draft(summary, journal_path, entries)
    print(f"\nDraft saved to: {draft_path}")

    # Print a preview of the summary
    print("\n" + "=" * 60)
    print("SUMMARY PREVIEW (first 500 chars):")
    print("=" * 60)
    print(summary[:500])
    if len(summary) > 500:
        print(f"\n... ({len(summary) - 500} more characters)")

    return 0


# This block runs only when the script is executed directly,
# not when it's imported as a module.
# __name__ is a special variable Python sets to "__main__" for the entry script.
if __name__ == "__main__":
    sys.exit(main())
