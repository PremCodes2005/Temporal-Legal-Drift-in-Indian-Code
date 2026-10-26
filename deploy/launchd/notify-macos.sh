#!/bin/sh
# Alert channel for a Mac: the message (stdin) is appended to ~/Library/Logs/tldrift-alerts.log and shown as a notification.
log="$HOME/Library/Logs/tldrift-alerts.log"
message="$(cat)"
printf '%s\n\n' "$message" >> "$log" || exit 1
summary="$(printf '%s' "$message" | sed -n '2p' | cut -c1-180 | tr -d '"\\')"
osascript -e "display notification \"${summary:-see $log}\" with title \"Temporal Legal Drift\"" >/dev/null 2>&1 || true
