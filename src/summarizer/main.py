"""
Main entry point for the work journal summarizer.

This module orchestrates the full flow:
1. Check if a summary is needed
2. Gather journal entries
3. Generate summary via Claude API
4. Save the draft
5. Send email notification for review

Run with: uv run python -m summarizer
"""

import argparse  # Standard library for parsing command-line arguments
import sys  # System-specific parameters and functions (like sys.exit)

# Import from our sibling modules using relative imports
# The dot (.) means "from the current package"
from .email_sender import send_summary_email
from .journal import gather_entries, get_journal_path, needs_summary
from .reply_processor import process_replies
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

    # --no-email skips sending the email (useful for testing)
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip sending email notification (just save draft locally).",
    )

    # --check-replies runs in "reply processing" mode instead of summary mode
    # This is a separate mode - it doesn't generate summaries, just processes replies
    parser.add_argument(
        "--check-replies",
        action="store_true",
        help="Check for and process replies to summary emails (run hourly via launchd).",
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

    # Handle --check-replies mode (separate from summary generation)
    # This mode processes email replies and doesn't generate summaries
    if args.check_replies:
        print("Running in reply-processing mode...")
        processed = process_replies()
        return 0 if processed >= 0 else 1

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
        print("Error: API key not found at ~/.secrets/shared/anthropic-api-key.txt")
        print("Please create this file with your Anthropic API key.")
        print("See ~/.secrets/README.md for the secrets organization pattern.")
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

    # Send email notification (unless --no-email flag is set)
    if args.no_email:
        print("\n[--no-email] Skipping email notification.")
    else:
        # Build date range string from the entries
        # entries[0] is oldest (first), entries[-1] is newest (last)
        # .isoformat() converts date object to "YYYY-MM-DD" string
        start_date = entries[0]["date"].isoformat()
        end_date = entries[-1]["date"].isoformat()
        date_range = f"{start_date} to {end_date}"

        print(f"\nSending email notification...")
        if send_summary_email(summary, date_range):
            print("Email sent! Check robots@das.llc for the summary.")
        else:
            # Email failure shouldn't fail the whole run - the draft is saved
            print("Warning: Email failed to send, but draft was saved locally.")

    return 0


# This block runs only when the script is executed directly,
# not when it's imported as a module.
# __name__ is a special variable Python sets to "__main__" for the entry script.
if __name__ == "__main__":
    sys.exit(main())
