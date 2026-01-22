"""
Process email replies to work journal summaries.

This module implements the feedback loop:
1. Poll Gmail for unread replies to summary emails
2. Classify user intent using Claude Haiku (fast + cheap)
3. Take action based on classification
4. Send confirmation email

Classification categories:
- APPROVE: User approves the draft (finalize it)
- REVISE: User wants changes (store feedback for next summary)
- UNCLEAR: Can't determine intent (ask for clarification)

Why Claude Haiku?
- Fast: ~200ms response time
- Cheap: ~$0.25 per million input tokens, ~$1.25 per million output tokens
- Smart enough: Intent classification is a simple task
- Compared to Sonnet/Opus, this saves 10-20x on a task that doesn't need deep reasoning
"""

import json
import re
from datetime import datetime
from pathlib import Path

import anthropic  # For calling Claude Haiku

# Import our config system
from . import config

# Import Gmail utilities from our email_sender module
from .email_sender import (
    get_gmail_credentials,
    send_email,
    get_secrets_path,
)
from .summarize import get_anthropic_key

# Google API for reading emails
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ---------------------------------------------------------------------------
# Gmail Reading
# ---------------------------------------------------------------------------

def get_unread_replies() -> list[dict]:
    """
    Fetch unread emails that are replies to our summary emails.

    Gmail search query breakdown:
    - `in:inbox`: Only look in inbox (not spam, trash, etc.)
    - `is:unread`: Only unread messages
    - `subject:"[Work Journal]"`: Must have our subject prefix

    Returns:
        List of dicts, each containing:
        - 'id': Gmail message ID
        - 'thread_id': Thread ID (for conversation grouping)
        - 'subject': Email subject line
        - 'body': Plain text body content
        - 'from': Sender email address
    """
    creds = get_gmail_credentials()
    if not creds:
        print("Failed to get Gmail credentials. Cannot check replies.")
        return []

    try:
        # Build the Gmail API client
        service = build("gmail", "v1", credentials=creds)

        # Search for unread replies to our summary emails
        # The query syntax is Gmail's search syntax (same as the Gmail web UI)
        # Subject prefix comes from config
        subject_prefix = config.get("email.subject_prefix")
        query = f'in:inbox is:unread subject:"{subject_prefix}"'

        # users().messages().list() returns message IDs matching the query
        # We need to fetch full message content separately
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=10  # Limit to 10 most recent
        ).execute()

        # Get the list of message IDs (may be empty)
        # .get() with default [] handles the case where 'messages' key doesn't exist
        messages = results.get("messages", [])

        if not messages:
            return []

        # Fetch full content for each message
        replies = []
        for msg in messages:
            # users().messages().get() fetches the full message
            # format="full" includes headers and body
            full_msg = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="full"
            ).execute()

            # Extract the data we need
            reply = {
                "id": msg["id"],
                "thread_id": full_msg.get("threadId"),
                "subject": _get_header(full_msg, "Subject"),
                "from": _get_header(full_msg, "From"),
                "body": _get_body(full_msg),
            }
            replies.append(reply)

        return replies

    except HttpError as error:
        print(f"Gmail API error: {error}")
        return []


def _get_header(message: dict, header_name: str) -> str:
    """
    Extract a header value from a Gmail message.

    Gmail API returns headers as a list of {"name": "...", "value": "..."} dicts.
    This helper finds the header by name.

    Syntax notes:
    - The `next()` function returns the first item from an iterator
    - Generator expression `(h for h in headers if ...)` creates an iterator
    - The second argument to next() is the default if iterator is empty

    Args:
        message: Gmail message dict (from API)
        header_name: Header to find (e.g., "Subject", "From")

    Returns:
        Header value, or empty string if not found
    """
    headers = message.get("payload", {}).get("headers", [])
    # Find the header with matching name (case-insensitive)
    return next(
        (h["value"] for h in headers if h["name"].lower() == header_name.lower()),
        ""  # Default if not found
    )


def _get_body(message: dict) -> str:
    """
    Extract plain text body from a Gmail message.

    Email structure can be complex:
    - Simple emails: body is directly in payload.body.data
    - Multipart emails: body is in one of payload.parts[]

    We look for text/plain content type and decode it.

    Syntax notes:
    - Email bodies are base64url-encoded (for safe transmission)
    - We decode to get the actual text

    Args:
        message: Gmail message dict (from API)

    Returns:
        Plain text body content
    """
    import base64

    payload = message.get("payload", {})

    # Try to get body directly (simple non-multipart messages)
    body_data = payload.get("body", {}).get("data")
    if body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8")

    # For multipart messages, look through parts
    parts = payload.get("parts", [])
    for part in parts:
        # Look for text/plain content
        if part.get("mimeType") == "text/plain":
            part_data = part.get("body", {}).get("data")
            if part_data:
                return base64.urlsafe_b64decode(part_data).decode("utf-8")

        # Recursively check nested parts (for complex emails)
        nested_parts = part.get("parts", [])
        for nested in nested_parts:
            if nested.get("mimeType") == "text/plain":
                nested_data = nested.get("body", {}).get("data")
                if nested_data:
                    return base64.urlsafe_b64decode(nested_data).decode("utf-8")

    return ""  # No plain text body found


def mark_as_read(message_id: str) -> bool:
    """
    Mark a Gmail message as read by removing the UNREAD label.

    Gmail uses labels for status. UNREAD is a special system label.
    Removing it marks the message as read.

    Args:
        message_id: Gmail message ID

    Returns:
        True if successful, False otherwise
    """
    creds = get_gmail_credentials()
    if not creds:
        return False

    try:
        service = build("gmail", "v1", credentials=creds)

        # Modify labels: remove UNREAD
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()

        return True

    except HttpError as error:
        print(f"Failed to mark message as read: {error}")
        return False


# ---------------------------------------------------------------------------
# Intent Classification
# ---------------------------------------------------------------------------

def classify_reply(reply_body: str) -> tuple[str, str]:
    """
    Use Claude Haiku to classify the user's reply intent.

    We use a simple, structured prompt that asks for classification
    and optional feedback extraction.

    Why Haiku?
    - This is a simple classification task
    - Speed matters (we might process multiple replies)
    - Cost matters (this runs potentially hourly)
    - Haiku is plenty smart for "did the user say yes or no?"

    Args:
        reply_body: The text of the user's email reply

    Returns:
        Tuple of (classification, feedback):
        - classification: "APPROVE", "REVISE", or "UNCLEAR"
        - feedback: Extracted feedback text (empty for APPROVE/UNCLEAR)
    """
    # Create the API client with our key
    client = anthropic.Anthropic(api_key=get_anthropic_key())

    # The classification prompt
    # We're very explicit about output format to make parsing easy
    prompt = f"""Classify this email reply to a work journal summary.

The user received an automated bi-weekly summary of their work journal.
They replied to that email. Your job is to determine their intent.

<reply>
{reply_body}
</reply>

Classification rules:
- APPROVE: User wants to approve/accept the summary (e.g., "looks good", "yes", "approve", "ship it", "👍", "thanks", "great")
- REVISE: User wants changes or has feedback (e.g., "not quite", "more focus on X", "try again", "change...")
- UNCLEAR: Can't determine intent (empty, off-topic, confusing)

Respond in this exact format:
CLASSIFICATION: [APPROVE/REVISE/UNCLEAR]
FEEDBACK: [If REVISE, one sentence summarizing their feedback. Otherwise, leave empty.]

Examples:
---
Reply: "Looks good, thanks!"
CLASSIFICATION: APPROVE
FEEDBACK:
---
Reply: "Can you focus more on the Calendar project next time?"
CLASSIFICATION: REVISE
FEEDBACK: Focus more on the Calendar project.
---
Reply: "Hey, what's the weather like?"
CLASSIFICATION: UNCLEAR
FEEDBACK:
---

Now classify the reply above."""

    # Call Haiku (model from config - fast + cheap for classification)
    message = client.messages.create(
        model=config.get("anthropic.classify_model"),
        max_tokens=100,  # Short response expected
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse the response
    response_text = message.content[0].text

    # Extract classification using regex
    # re.search() finds a pattern anywhere in the string
    # (?:...) is a non-capturing group
    class_match = re.search(r"CLASSIFICATION:\s*(APPROVE|REVISE|UNCLEAR)", response_text)
    classification = class_match.group(1) if class_match else "UNCLEAR"

    # Extract feedback
    feedback_match = re.search(r"FEEDBACK:\s*(.+)", response_text)
    feedback = feedback_match.group(1).strip() if feedback_match else ""

    return classification, feedback


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def get_pending_feedback_path() -> Path:
    """
    Path to the file storing pending feedback for the next summary.

    When a user requests revisions, we store their feedback here.
    The next summary generation can read this to adjust its prompt.

    Returns:
        Path to pending-feedback.json
    """
    return get_secrets_path() / "pending-feedback.json"


def save_feedback(feedback: str) -> None:
    """
    Save user feedback to be incorporated into the next summary.

    The feedback file is JSON with a list of feedback items,
    each timestamped. This allows accumulating multiple pieces
    of feedback if the user replies multiple times.

    Args:
        feedback: The feedback text to save
    """
    feedback_path = get_pending_feedback_path()

    # Load existing feedback (if any)
    if feedback_path.exists():
        existing = json.loads(feedback_path.read_text())
    else:
        existing = []

    # Add new feedback with timestamp
    existing.append({
        "feedback": feedback,
        "timestamp": datetime.now().isoformat(),
    })

    # Save back to file
    feedback_path.write_text(json.dumps(existing, indent=2))
    print(f"Feedback saved to: {feedback_path}")


def finalize_draft(date_str: str | None = None) -> bool:
    """
    Rename the most recent draft to finalized (remove -DRAFT suffix).

    When a user approves a summary, we rename:
        2026-01-08-SUMMARY-14-days-DRAFT.md → 2026-01-08-SUMMARY-14-days.md

    Args:
        date_str: Optional date string (YYYY-MM-DD) to find specific draft.
                  If None, finds the most recent draft.

    Returns:
        True if a draft was finalized, False if no draft found
    """
    from .journal import get_summaries_path

    summaries_path = get_summaries_path()

    # Find draft files in the periodic-summaries/ subfolder
    # glob() returns an iterator of Path objects matching the pattern
    drafts = list(summaries_path.glob("*-SUMMARY-*-DRAFT.md"))

    if not drafts:
        print("No draft files found to finalize.")
        return False

    # Sort by modification time (most recent first)
    # key=lambda p: p.stat().st_mtime gets the modification timestamp
    drafts.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Get the most recent draft
    draft_path = drafts[0]

    # New name: remove -DRAFT
    # .stem gives filename without extension
    # .parent gives the directory
    new_name = draft_path.stem.replace("-DRAFT", "") + ".md"
    final_path = draft_path.parent / new_name

    # Rename the file
    draft_path.rename(final_path)
    print(f"Finalized: {draft_path.name} → {final_path.name}")

    return True


def send_confirmation_email(classification: str, feedback: str = "") -> bool:
    """
    Send a confirmation email based on the classification.

    Args:
        classification: "APPROVE", "REVISE", or "UNCLEAR"
        feedback: Extracted feedback (for REVISE case)

    Returns:
        True if email sent successfully
    """
    if classification == "APPROVE":
        subject = "[Work Journal] Summary Approved"
        body = """Got it! Your summary has been approved.

The draft has been converted to a finalized summary in your work journal.

- work-journal-summarizer bot
"""

    elif classification == "REVISE":
        subject = "[Work Journal] Feedback Received"
        body = f"""Understood! Your feedback has been noted.

Your feedback: "{feedback}"

The next summary will incorporate this feedback. The current draft remains unchanged.

- work-journal-summarizer bot
"""

    else:  # UNCLEAR
        subject = "[Work Journal] Clarification Needed"
        body = """I couldn't quite understand your reply.

Please respond with one of:
- "approve" or "looks good" - to finalize the summary
- Describe what you'd like changed - to request revisions

- work-journal-summarizer bot
"""

    # Use config for email addresses - no hardcoded values
    return send_email(
        to=config.get("email.to"),
        subject=subject,
        body=body,
        from_addr=config.get("email.from"),
    )


# ---------------------------------------------------------------------------
# Main Processing Loop
# ---------------------------------------------------------------------------

def process_replies() -> int:
    """
    Check for and process any unread replies to summary emails.

    This is the main entry point for reply processing.
    Called via: uv run python -m summarizer --check-replies

    Returns:
        Number of replies processed
    """
    print("Checking for replies to summary emails...")

    replies = get_unread_replies()

    if not replies:
        print("No unread replies found.")
        return 0

    print(f"Found {len(replies)} unread reply(s).")

    processed = 0
    for reply in replies:
        print(f"\nProcessing reply from: {reply['from']}")
        print(f"  Subject: {reply['subject']}")

        # Classify the reply
        classification, feedback = classify_reply(reply["body"])
        print(f"  Classification: {classification}")
        if feedback:
            print(f"  Feedback: {feedback}")

        # Take action based on classification
        if classification == "APPROVE":
            finalize_draft()
        elif classification == "REVISE":
            save_feedback(feedback)
        # UNCLEAR: just send clarification request, no other action

        # Send confirmation email
        send_confirmation_email(classification, feedback)

        # Mark the original reply as read
        mark_as_read(reply["id"])

        processed += 1

    print(f"\nProcessed {processed} reply(s).")
    return processed


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick test: run this file directly to check for replies
    # python -m summarizer.reply_processor (from src/ directory)
    process_replies()
