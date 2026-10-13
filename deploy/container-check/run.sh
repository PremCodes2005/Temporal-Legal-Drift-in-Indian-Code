#!/bin/sh
# Run the systemd units under real systemd in a throwaway container with NO network, so no official
# source is contacted and no 24 h window is consumed. Verifies unit syntax, timer scheduling, the
# monitor job, duplicate suppression, the health check and OnFailure alert delivery.
# This is a harness, not a deployment: it proves nothing about an always-on host.
set -eu
repo="$(cd "$(dirname "$0")/../.." && pwd)"
work="$(mktemp -d)"
trap 'docker rm -f tldrift-sysd >/dev/null 2>&1 || true; rm -rf "$work"' EXIT
mkdir "$work/app"
(cd "$repo" && git ls-files --cached --others --exclude-standard -z | rsync -a --from0 --files-from=- ./ "$work/app/")
cp "$repo/deploy/container-check/Dockerfile" "$work/"
docker build -q -t tldrift-systemd-check:local "$work" >/dev/null
docker run -d --name tldrift-sysd --privileged --cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  --network none --tmpfs /run --tmpfs /run/lock tldrift-systemd-check:local >/dev/null
d() { docker exec tldrift-sysd "$@"; }
for _ in $(seq 1 30); do state="$(d systemctl is-system-running 2>/dev/null || true)"; [ "$state" = running ] && break; sleep 1; done
d sh -c "systemd-analyze verify /etc/systemd/system/tldrift-*.service /etc/systemd/system/tldrift-*.timer"
d systemctl start tldrift-monitor.service
d systemctl start tldrift-monitor.service                       # inside the window: must start no source run
test "$(d sh -c 'ls /srv/temporal-legal-drift/data/monitoring/runs | wc -l')" -eq 2
d systemctl start tldrift-health.service && { echo "expected the health check to fail (sources unreachable)"; exit 1; } || true
sleep 3
d grep -q "tldrift-health.service failed" /var/tmp/tldrift-alerts.log
echo "PASS: units verify, monitor ran once per source, repeat suppressed, health check failed and alert delivered"
