#!/bin/sh
# launchd entry point (macOS): one hourly trigger. Daily run at 06:30 Asia/Kolkata unless overridden in the env file;
# the service enforces at most one start per source per 24 h, so the other 23 triggers start nothing unless a slot was missed.
set -u
root="$(cd "$(dirname "$0")/../.." && pwd)"
env_file="${TLDRIFT_ENV_FILE:-$HOME/.config/tldrift/tldrift.env}"
# shellcheck disable=SC1090
[ -f "$env_file" ] && . "$env_file"
export TLDRIFT_ALERT_COMMAND="${TLDRIFT_ALERT_COMMAND:-}"
cd "$root" || exit 1
run() { PYTHONPATH="$root/src" "$root/.venv/bin/python" -m temporal_legal_drift.cli "$@"; }
echo "== trigger $(date -u +%Y-%m-%dT%H:%M:%SZ) launchd@$(hostname -s)"
run monitor-run --owner "launchd@$(hostname -s)" --daily-at "${TLDRIFT_DAILY_AT:-06:30}" --timezone "${TLDRIFT_TIMEZONE:-Asia/Kolkata}" --notify
status=$?
run monitor-notify --check || status=$?
exit "$status"
