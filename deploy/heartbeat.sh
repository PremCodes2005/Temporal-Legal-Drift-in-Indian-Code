#!/bin/sh
# Ping the optional dead-man's-switch URL after a healthy check; does nothing when unset.
[ -z "$TLDRIFT_HEARTBEAT_URL" ] && exit 0
exec curl -fsS -m 10 --retry 2 -o /dev/null "$TLDRIFT_HEARTBEAT_URL"
