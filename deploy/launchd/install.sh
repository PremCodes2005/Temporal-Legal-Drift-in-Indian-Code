#!/bin/sh
# Install (or reinstall) the hourly launchd agent for this checkout. Usage: sh deploy/launchd/install.sh
# Remove: launchctl bootout "gui/$(id -u)/in.tldrift.monitor" && rm ~/Library/LaunchAgents/in.tldrift.monitor.plist
set -eu
root="$(cd "$(dirname "$0")/../.." && pwd)"
label=in.tldrift.monitor
plist="$HOME/Library/LaunchAgents/$label.plist"
env_file="$HOME/.config/tldrift/tldrift.env"
test -x "$root/.venv/bin/python" || { echo "missing $root/.venv (create it and install the package first)" >&2; exit 1; }
mkdir -p "$root/logs" "$HOME/Library/LaunchAgents" "$(dirname "$env_file")"
if [ ! -f "$env_file" ]; then
  umask 077
  printf '%s\n' "# Alert channel: command that receives the alert text on stdin." \
    "TLDRIFT_ALERT_COMMAND=\"sh '$root/deploy/launchd/notify-macos.sh'\"" \
    "TLDRIFT_DAILY_AT=06:30" "TLDRIFT_TIMEZONE=Asia/Kolkata" > "$env_file"
fi
cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>$root/deploy/launchd/run.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Minute</key><integer>30</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$root/logs/monitor.log</string>
  <key>StandardErrorPath</key><string>$root/logs/monitor.log</string>
</dict>
</plist>
PLIST
plutil -lint "$plist"
launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl print "gui/$(id -u)/$label" | grep -E "state|path|runs" || true
echo "Installed $label: hourly at :30; daily run 06:30 Asia/Kolkata (see $env_file)."
