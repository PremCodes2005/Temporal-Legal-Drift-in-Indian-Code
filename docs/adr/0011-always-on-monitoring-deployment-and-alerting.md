# ADR 0011: Always-on deployment of the daily job with missed-run alerting

Status: **accepted 2026-10-12**. Implementation: `deploy/systemd/*`, `deploy/alert.sh`, `deploy/heartbeat.sh`, `MonitoringService.health()["alerts"]`, `tldrift monitor-health --check`. Tests: `tests/unit/test_deploy.py`.

## Decision

- **Scheduler:** systemd timers on a Linux host. Both timers are `Persistent=true`, so a reboot does not silently skip a run.
  - `tldrift-monitor.timer` fires hourly. The service enforces at most one start per source per 24 h, so hourly triggering is idempotent.
  - `tldrift-health.timer` runs `monitor-health --check` hourly on a separate unit, so a stalled or disabled monitor job is still detected.
- **Alert codes:**
  - `SCHEDULER_MISSED_RUN`: a source is more than 2 h past `next_eligible_at` with no new attempt, meaning the trigger is not firing.
  - `INGESTION_STALE`: no success for more than 48 h despite attempts.
  - `--check` exits 3 on any alert. The plain health report always exits 0.
- **Alert delivery:**
  - Both units declare `OnFailure=tldrift-alert@%n.service`, which runs `deploy/alert.sh`.
  - The script pipes the message, the health JSON and the journal tail to `$TLDRIFT_ALERT_COMMAND` (for example mail or a webhook wrapper). If that is unset or fails, it logs to syslog at `crit` and exits non-zero.
- **Host death:** an optional `TLDRIFT_HEARTBEAT_URL` dead-man's switch is pinged only after a healthy check. This covers the whole host being down, which no local timer can report.
- **Secrets:** they live in `/etc/tldrift/tldrift.env`, never in the repository; `deploy/systemd/tldrift.env.example` holds no secret.
- **Manual retries:** an audited manual retry must name one source (`--source`), so it never bypasses another source's 24 h window.

## Not verified

- No always-on host has been provisioned.
- The units were checked by tests that parse them and confirm they call real CLI commands, but `systemd-analyze verify` and a running systemd were not exercised (macOS development machine).
