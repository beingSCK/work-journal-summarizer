#!/bin/bash
# ==============================================================================
# Uninstall launchd Jobs for Work Journal Summarizer
# ==============================================================================
#
# What this script does:
# 1. Unloads the jobs (stops launchd from managing them)
# 2. Removes the plist files from ~/Library/LaunchAgents/
#
# Run with: ./scripts/uninstall-scheduled-jobs.sh
#
# When to use this:
# - You want to stop the automatic daily summaries
# - You're cleaning up after uninstalling the project
# - You want to reinstall with different settings
#
# Note: This does NOT delete your journal entries, summaries, or config files.
# It only removes the scheduling automation.
#
# ==============================================================================

set -e

LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "Uninstalling work-journal-summarizer launchd jobs..."

# Unload jobs (stop launchd from managing them)
# - launchctl unload tells launchd to stop this job
# - We use 2>/dev/null to suppress "not loaded" errors if already unloaded
# - || true prevents the script from exiting if the job wasn't loaded
echo "Unloading jobs..."
launchctl unload "$LAUNCH_AGENTS/com.sck.work-journal-summarizer.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS/com.sck.work-journal-summarizer-replies.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS/com.das.heartbeat.plist" 2>/dev/null || true

# Remove the plist files
# - rm -f removes files without error if they don't exist
echo "Removing plist files..."
rm -f "$LAUNCH_AGENTS/com.sck.work-journal-summarizer.plist"
rm -f "$LAUNCH_AGENTS/com.sck.work-journal-summarizer-replies.plist"
rm -f "$LAUNCH_AGENTS/com.das.heartbeat.plist"

echo ""
echo "Uninstallation complete!"
echo ""
echo "The following have been preserved:"
echo "  - Your journal entries and summaries (in work-journal/)"
echo "  - Your configuration (config/config.yaml)"
echo "  - Your OAuth tokens (~/.secrets/work-journal-summarizer/)"
echo ""
echo "To reinstall: ./scripts/install-scheduled-jobs.sh"
echo ""
