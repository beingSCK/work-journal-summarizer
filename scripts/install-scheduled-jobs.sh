#!/bin/bash
# ==============================================================================
# Install Scheduled Jobs for Work Journal Summarizer
# ==============================================================================
#
# What this script does:
# 1. Creates the log directory if needed
# 2. Copies plist files to ~/Library/LaunchAgents/
# 3. Loads the jobs so they start running on schedule
#
# Run with: ./scripts/install-scheduled-jobs.sh
#
# Shebang explanation (#!/bin/bash):
# - #! is the "shebang" - tells the OS what interpreter to use
# - /bin/bash is the path to the Bash shell
# - Without this, the OS wouldn't know how to run this file
#
# ==============================================================================

# Exit on any error (set -e)
# - Normally, bash continues after errors
# - set -e makes the script stop immediately on any failed command
# - This prevents cascading failures and makes debugging easier
set -e

# Get the directory where this script lives
# - $0 is the path to this script
# - dirname $0 gives the directory containing this script
# - cd ... && pwd gives the absolute path (handles relative paths)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Go up one level to get the project root
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Define paths
# - LaunchAgents is where user-level scheduled jobs live
# - Logs go in the standard macOS logs location
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs"
PLIST_DIR="$PROJECT_DIR/launchd"

echo "Installing work-journal-summarizer launchd jobs..."
echo "Project directory: $PROJECT_DIR"

# Create directories if they don't exist
# - mkdir -p creates parent directories as needed and doesn't error if exists
echo "Ensuring directories exist..."
mkdir -p "$LAUNCH_AGENTS"
mkdir -p "$LOG_DIR"

# Copy plist files
# - cp copies files; we're going from our repo to the system location
echo "Copying plist files to $LAUNCH_AGENTS..."
cp "$PLIST_DIR/com.sck.work-journal-summarizer.plist" "$LAUNCH_AGENTS/"
cp "$PLIST_DIR/com.sck.work-journal-summarizer-replies.plist" "$LAUNCH_AGENTS/"

# Load the jobs
# - launchctl load tells launchd to start managing this job
# - The job won't run immediately (RunAtLoad is false), but will run at scheduled time
echo "Loading jobs..."
launchctl load "$LAUNCH_AGENTS/com.sck.work-journal-summarizer.plist"
launchctl load "$LAUNCH_AGENTS/com.sck.work-journal-summarizer-replies.plist"

echo ""
echo "Installation complete!"
echo ""
echo "Jobs installed:"
echo "  - com.sck.work-journal-summarizer (daily at 10:00 AM)"
echo "  - com.sck.work-journal-summarizer-replies (hourly)"
echo ""
echo "Verify with: launchctl list | grep work-journal"
echo "View logs:   tail -f ~/Library/Logs/work-journal-summarizer.log"
echo ""
echo "To test manually:"
echo "  launchctl start com.sck.work-journal-summarizer"
echo "  launchctl start com.sck.work-journal-summarizer-replies"
echo ""
echo "To uninstall: ./scripts/uninstall-scheduled-jobs.sh"
