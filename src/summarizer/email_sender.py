"""
Gmail API integration for sending work journal summaries.

This module handles:
- OAuth 2.0 authentication flow with Gmail
- Token storage and automatic refresh
- Sending emails via the Gmail API

OAuth Flow Overview:
    1. First run: Opens browser for user to grant permission
    2. User logs in and clicks "Allow"
    3. Google redirects to localhost with an authorization code
    4. Code is exchanged for access + refresh tokens
    5. Tokens are saved locally for future runs
    6. On subsequent runs: tokens are loaded and auto-refreshed if expired

Why OAuth instead of password?
    - Google disabled "less secure app access" (plain passwords) in 2022
    - OAuth is more secure: you grant specific permissions, not full account access
    - Tokens can be revoked without changing your password
    - Apps only get the scopes they request (we only ask for "send email")
"""

import base64  # For encoding email content (Gmail API requires base64)
from email.message import EmailMessage  # Standard library for constructing emails (modern API)
from pathlib import Path

# Google API libraries - installed via: uv add google-auth-oauthlib google-api-python-client
# These are the official Google libraries for OAuth and API access
from google.auth.transport.requests import Request  # For refreshing expired tokens
from google.oauth2.credentials import Credentials  # Represents the user's tokens
from google_auth_oauthlib.flow import InstalledAppFlow  # Handles the OAuth dance
from googleapiclient.discovery import build  # Creates API client objects
from googleapiclient.errors import HttpError  # Gmail API error handling

# Import our config system for email addresses and paths
from . import config


# ---------------------------------------------------------------------------
# Path Configuration
# ---------------------------------------------------------------------------

def get_secrets_path() -> Path:
    """
    Return the path to this project's secrets folder.

    We store OAuth credentials in ~/.secrets/work-journal-summarizer/
    rather than in the project directory. This keeps all secrets
    in one organized location outside any git repos.

    The path comes from config, making it customizable if needed.

    Returns:
        Path object pointing to the project's secrets folder
    """
    return config.get_project_secrets_path()


def get_client_secret_path() -> Path:
    """
    Path to the OAuth client configuration (downloaded from Google Cloud Console).

    This file contains:
    - client_id: Identifies your app to Google
    - client_secret: "Secret" for desktop apps (see module docstring)
    - redirect_uris: Where Google sends the user after auth (localhost for us)

    Returns:
        Path to gmail-client-secret.json
    """
    return get_secrets_path() / "gmail-client-secret.json"


def get_token_path() -> Path:
    """
    Path to the stored OAuth tokens (created after first successful auth).

    This file contains:
    - access_token: Short-lived (1 hour), used for API calls
    - refresh_token: Long-lived, used to get new access tokens
    - token_uri: Where to send refresh requests
    - expiry: When the access token expires

    This file IS a secret - anyone with it can send email as you.

    Returns:
        Path to gmail-token.json
    """
    return get_secrets_path() / "gmail-token.json"


# ---------------------------------------------------------------------------
# OAuth Scopes
# ---------------------------------------------------------------------------

# Scopes define what permissions your app requests.
# We use the minimal scope needed: just sending emails.
#
# Available Gmail scopes (from most to least permissive):
#   - gmail (full access - read, write, delete, send)
#   - gmail.modify (read, write, but not delete)
#   - gmail.compose (create drafts and send)
#   - gmail.send (ONLY send, can't read inbox) <-- We use this
#   - gmail.readonly (only read, can't send)
#
# Principle of least privilege: request only what you need.
# If this app is compromised, attacker can only send emails, not read them.

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",      # Send emails
    "https://www.googleapis.com/auth/gmail.readonly",  # Read emails (for reply processing)
    "https://www.googleapis.com/auth/gmail.modify",    # Mark messages as read
]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def get_gmail_credentials() -> Credentials | None:
    """
    Get valid Gmail API credentials, handling token refresh and first-time auth.

    The OAuth flow (simplified):

        First run:
            1. No token file exists
            2. Open browser to Google's consent screen
            3. User logs in and grants permission
            4. Google redirects to http://localhost:PORT with auth code
            5. Exchange code for access + refresh tokens
            6. Save tokens to file

        Subsequent runs:
            1. Load tokens from file
            2. If access token expired, use refresh token to get new one
            3. If refresh token revoked, re-do the browser flow

    Syntax notes:
    - `Credentials | None` is Python 3.10+ union type (same as Optional[Credentials])
    - `creds.expired` is a property that checks if access_token is past expiry
    - `creds.refresh_token` exists if we can auto-refresh (not all OAuth grants have it)

    Returns:
        Credentials object ready for API calls, or None if auth failed/unavailable.
    """
    creds = None
    token_path = get_token_path()
    client_secret_path = get_client_secret_path()

    # Step 1: Try to load existing tokens
    if token_path.exists():
        # Credentials.from_authorized_user_file() reads a JSON file with:
        #   {"token": "...", "refresh_token": "...", "token_uri": "...", ...}
        # and creates a Credentials object
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Step 2: If no valid credentials, we need to authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Access token expired but we have a refresh token - get a new one
            # This happens automatically and doesn't require user interaction
            print("Refreshing expired Gmail token...")
            creds.refresh(Request())
        else:
            # No valid credentials at all - need user to authenticate via browser
            if not client_secret_path.exists():
                print(f"Gmail client secret not found at: {client_secret_path}")
                print("Download it from Google Cloud Console > APIs & Services > Credentials")
                return None

            print("Opening browser for Gmail authentication...")
            print("(You only need to do this once)")

            # InstalledAppFlow handles the entire OAuth dance:
            # 1. Starts a local HTTP server on a random port
            # 2. Opens browser to Google's consent screen
            # 3. Waits for redirect with authorization code
            # 4. Exchanges code for tokens
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path),
                SCOPES
            )

            # run_local_server() blocks until auth completes or fails
            # port=0 means "pick any available port"
            creds = flow.run_local_server(port=0)

        # Step 3: Save credentials for next run
        # .to_json() serializes the credentials to a JSON string
        token_path.write_text(creds.to_json())
        print(f"Gmail credentials saved to: {token_path}")

    return creds


# ---------------------------------------------------------------------------
# Email Sending
# ---------------------------------------------------------------------------

def create_message(to: str, subject: str, body: str, from_addr: str) -> dict:
    """
    Create an email message in the format Gmail API expects.

    Gmail API requires emails as base64-encoded RFC 2822 messages.
    The EmailMessage class from Python's email library handles the RFC 2822 part,
    then we base64-encode it.

    RFC 2822 format looks like:
        From: sender@example.com
        To: recipient@example.com
        Subject: Hello

        This is the body.

    Syntax notes:
    - EmailMessage() creates a new email message object (modern API, replaces MIMEText)
    - message["To"] = ... sets headers (EmailMessage acts like a dict for headers)
    - .set_content(body) sets the email body (cleaner than MIMEText constructor)
    - .as_bytes() converts the whole thing to RFC 2822 format as bytes
    - base64.urlsafe_b64encode() encodes bytes to base64 (URL-safe variant)
    - .decode("utf-8") converts base64 bytes back to string (for JSON)

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Plain text email body
        from_addr: Sender email address

    Returns:
        Dict with 'raw' key containing base64-encoded message
    """
    # Create the email using Python's modern email library (EmailMessage)
    # This is the recommended approach as of Python 3.6+
    message = EmailMessage()
    message["To"] = to
    message["From"] = from_addr
    message["Subject"] = subject
    message.set_content(body)  # Sets the body as plain text

    # Gmail API expects the message as a base64url-encoded string
    # .as_bytes() gives us the full RFC 2822 message as bytes
    # urlsafe_b64encode handles the encoding (uses - and _ instead of + and /)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    return {"raw": raw}


def send_email(to: str, subject: str, body: str, from_addr: str | None = None) -> bool:
    """
    Send an email via the Gmail API.

    This is the main function you'll call from other modules.
    It handles authentication, message creation, and sending.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Plain text email body
        from_addr: Sender address (must match authenticated Gmail account)

    Returns:
        True if email was sent successfully, False otherwise.

    Example:
        >>> send_email(
        ...     to="robots@das.llc",
        ...     subject="[Work Journal] Bi-Weekly Summary",
        ...     body="Here's your summary..."
        ... )
        True
    """
    # Use config value if from_addr not explicitly provided
    if from_addr is None:
        from_addr = config.get("email.from")

    # Get authenticated credentials (may trigger browser auth on first run)
    creds = get_gmail_credentials()
    if not creds:
        print("Failed to get Gmail credentials. Email not sent.")
        return False

    try:
        # build() creates an API client for a specific Google service
        # "gmail" is the service name, "v1" is the API version
        # credentials=creds attaches our OAuth tokens
        service = build("gmail", "v1", credentials=creds)

        # Create the message in Gmail's expected format
        message = create_message(to, subject, body, from_addr)

        # Send the email
        # users().messages().send() is the Gmail API endpoint
        # userId="me" means "the authenticated user"
        # body=message contains our base64-encoded email
        # .execute() actually makes the API call
        result = service.users().messages().send(userId="me", body=message).execute()

        print(f"Email sent successfully! Message ID: {result['id']}")
        return True

    except HttpError as error:
        # HttpError is raised for API errors (rate limits, permission denied, etc.)
        print(f"Gmail API error: {error}")
        return False


def send_summary_email(summary: str, date_range: str) -> bool:
    """
    Send a work journal summary email.

    This is a convenience wrapper around send_email() with our standard
    formatting for summary emails.

    Args:
        summary: The generated summary text (Markdown)
        date_range: Human-readable date range, e.g., "2026-01-01 to 2026-01-08"

    Returns:
        True if email was sent successfully, False otherwise.
    """
    subject = f"[Work Journal] Bi-Weekly Summary: {date_range}"

    # Email body includes instructions for the feedback loop
    body = f"""Here's your bi-weekly work journal summary for review.

---

{summary}

---

To approve this summary, reply with: "approve" or "looks good"
To request changes, reply describing what you'd like different.

This is an automated message from work-journal-summarizer.
"""

    # Use config for email addresses - no hardcoded values
    return send_email(
        to=config.get("email.to"),
        subject=subject,
        body=body,
        from_addr=config.get("email.from"),
    )


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick test: run this file directly to test authentication
    # python -m summarizer.email_sender (from src/ directory)
    print("Testing Gmail authentication...")
    creds = get_gmail_credentials()
    if creds:
        print("Authentication successful!")
        print(f"Token expires: {creds.expiry}")
    else:
        print("Authentication failed.")
