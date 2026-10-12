#!/bin/sh
# Send one alert for a failed tldrift unit. Message on stdin to $TLDRIFT_ALERT_COMMAND; syslog if unset or failing.
unit="${1:-unknown-unit}"
message="tldrift alert on $(hostname): $unit failed at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
details="$(cd "${TLDRIFT_ROOT:-/srv/temporal-legal-drift}" 2>/dev/null && "${TLDRIFT_BIN:-.venv/bin/tldrift}" monitor-health 2>&1 | head -c 4000)"
if command -v journalctl >/dev/null 2>&1; then
  details="$details
$(journalctl -u "$unit" -n 30 --no-pager 2>&1)"
fi
if [ -n "$TLDRIFT_ALERT_COMMAND" ] && printf '%s\n\n%s\n' "$message" "$details" | sh -c "$TLDRIFT_ALERT_COMMAND"; then
  exit 0
fi
logger -p user.crit -t tldrift "$message (alert command missing or failed)" 2>/dev/null
echo "$message" >&2
exit 1
