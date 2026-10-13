#!/bin/sh
# Real VoiceOver reading pass of the comparison result; records what VoiceOver actually speaks.
# Prerequisites (a person must do these; this script never changes accessibility settings):
#   1. VoiceOver Utility > General > "Allow VoiceOver to be controlled with AppleScript" (on).
#   2. Grant the terminal Accessibility/Automation permission when macOS asks.
#   3. Dashboard running: PYTHONPATH=src python -m temporal_legal_drift.cli serve-dashboard --port 8799
# Usage: sh frontend/scripts/voiceover-reading-pass.sh [output-file] [steps]
# VoiceOver will speak aloud and move focus in Safari while this runs (about 2-3 minutes).
set -eu
out="${1:-voiceover-transcript.txt}"
steps="${2:-300}"
url="http://127.0.0.1:8799/#assistant?q=Compare%20Section%2019%20before%20and%20after%20the%20IT%20Amendment%20Act%2C%202008."
if [ "$(defaults read com.apple.VoiceOver4/default SCREnableAppleScript 2>/dev/null || echo 0)" != "1" ]; then
  echo "VoiceOver AppleScript control is off; enable it in VoiceOver Utility > General, then rerun." >&2
  exit 2
fi
open -a Safari "$url"
sleep 12
osascript - "$steps" > "$out" <<'APPLESCRIPT'
on run argv
  set stepCount to (item 1 of argv) as integer
  set transcript to ""
  tell application "VoiceOver" to activate
  delay 4
  tell application "VoiceOver"
    repeat stepCount times
      tell vo cursor to move right
      delay 0.5
      set transcript to transcript & (content of last phrase) & linefeed
    end repeat
    quit
  end tell
  return transcript
end run
APPLESCRIPT
echo "Transcript: $out ($(wc -l < "$out") phrases)"
for cue in "Legal-version status" "Textual drift" "Open source PDF at page" "removed:" "inserted:" "How this score was calculated"; do
  if grep -q "$cue" "$out"; then echo "HEARD     $cue"; else echo "NOT HEARD $cue"; fi
done
