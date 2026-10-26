# Source-monitoring runbook (India Code and e-Gazette, daily)

Commands (from the repository root, Python 3.11+ with `pypdf==6.16.2` installed):

| Purpose | Command |
| --- | --- |
| Daily run at 06:30 IST (safe to call hourly; at most one attempt per source per rolling 24 h) | `tldrift monitor-run --owner <host-name> --daily-at 06:30 --timezone Asia/Kolkata --notify` |
| Send pending alerts once each (exit 3 with `--check` if they could not be delivered) | `tldrift monitor-notify --check` |
| Audited manual retry inside the window (one source; the window is not moved) | `tldrift monitor-run --owner <host> --source egazette --manual-reason "<why>"` |
| Bounded history backfill (≤ 20 pages; does not move the daily window) | `tldrift monitor-backfill --owner <host> --pages N --reason "<why>"` |
| Health (also `GET /api/sources/health`) | `tldrift monitor-health` |
| Alert check (exit 3 on a missed run or stale ingestion) | `tldrift monitor-health --check` |

## Scheduling (ADR 0025)

- **Run time:** daily at **06:30 Asia/Kolkata (01:00 UTC)**. State is stored in UTC.
- **Trigger:** hourly at minute 30. The 06:30 trigger is the daily run. The other triggers start nothing unless a slot was
  missed.
- **The 24-hour rule is strict.** A start up to an hour after its slot is on time; the next start is eligible 24 h
  later. A start due within 10 minutes waits for it, so start-up jitter never moves the run to the next trigger.
- **Missed slot** (host asleep or off): the next trigger catches up. When that catch-up is more than an hour late, the
  run after it returns to 06:30, which can leave up to about 47 h between those two starts.
- **No overlapping runs** across processes: a state-file lock plus a 6 h lease per source. launchd and systemd also never
  start a second copy of the same job.
- **No crawling from the app.** Page views and questions read the ledger only.

**Alerts.** `monitor-run --notify` and `monitor-notify` send one message per invocation, through
`TLDRIFT_ALERT_COMMAND` (stdin). It covers new records, failed document versions, missed runs and stale sources. Each key
is sent once:
- a record: official id + content hash;
- a failure: document version and state;
- a source condition: the attempt that caused it.

Keys are recorded in `data/monitoring/alerts_sent.v1.jsonl` only after delivery succeeds. An undelivered alert is retried
at the next trigger.

**Operational responsibility.** A job on a developer laptop runs only while the laptop is awake. It is a demonstration, **not** an operational guarantee. A deployment must name a host that is always on, an owner, and an alert:
- alert when `scheduled_ingestion_healthy` is false;
- or when `lag_hours` exceeds 48.

## State and outputs (`data/monitoring/`, git-ignored operational data)

| File / directory | Contents |
| --- | --- |
| `state.v1.json` | Per-source `last_attempt_at`, `last_success_at`, `next_eligible_at`, `cursor`, lease. |
| `observations.v1.jsonl` | Append-only discovery and download observations. |
| `runs/` | Write-once run manifests. |
| `review_queue/` | One item per new or revised content hash, with its `machine_state`. Nobody has to act on it for the pipeline to finish. |
| `alerts_sent.v1.jsonl` | Alert keys already delivered (or recorded as a baseline on first use). |
| `stage_runs.v1.jsonl`, `normalized/`, `candidates/` | Stage cache keyed by content hash and stage version. |
| `data/raw/monitoring/sha256/` | Immutable artifacts. |
| `quarantine/` | Write-once records of withheld PDF text lines (`text-quality-v1`): Hindi text layer, legacy-font mojibake. |
| `commencement/` | Write-once commencement records: unreviewed `TemporalFact`s, conflicts, unresolved wording (`commencement-policy-v1`). |

## Safety

- **Allowlist.** Only `indiacode.gov.in` and `egazette.gov.in` are fetched, and redirects are validated. Limits: 50 MB per file, 2 s between requests, at most 5 pages × 20 items per run.
- **No automatic effect on the graph, base index or releases.** New or revised documents enter the review queue. Their text is served only through the monitored overlay (`data/runtime/rag_overlay`), labelled `monitored_unreviewed` / `HUMAN_REVIEW_PENDING`, bound to the base index identity and switched by an atomic pointer (ADR 0009). Graph v4, the base RAG index and every release are unchanged. Applicability stays `NOT_DETERMINED`; a publication is not commencement.
- **e-Gazette** is `SUPPORTED_FRAGILE_HTML_DISCOVERY` (`docs/sprint/s1_source_access_decision.v2.md`): a session listing of “Bills & Acts” plus static PDFs. A layout change fails visibly (`SourceShapeError`) and nothing new is served. `MonitoringService.manual_import` remains the fallback.
- **e-Gazette TLS:** the server omits its intermediate certificate. The connector pins Let's Encrypt's verified Gen-Y intermediates (ADR 0010). If the site moves to another CA, runs fail as `SOURCE_UNAVAILABLE`: verify and pin the new intermediate. Never disable verification.
- **Pause:** unload the launchd agent or disable the systemd timer (below). There is no hidden daemon.

## macOS host (launchd, ADR 0025)

Install from the repository root (needs `.venv` with the package's dependencies):

```sh
sh deploy/launchd/install.sh
```

This writes and loads `~/Library/LaunchAgents/in.tldrift.monitor.plist`, which runs `deploy/launchd/run.sh` hourly at :30.
The script runs `monitor-run --daily-at 06:30 --timezone Asia/Kolkata --notify`, then `monitor-notify --check`.

- **Settings:** `~/.config/tldrift/tldrift.env`, holding the alert command, `TLDRIFT_DAILY_AT` and `TLDRIFT_TIMEZONE`. The
  default alert channel is `deploy/launchd/notify-macos.sh`: it appends to `~/Library/Logs/tldrift-alerts.log` and shows a
  macOS notification.
- **Log:** `logs/monitor.log`.
- **Verify a scheduled run:**
  - `launchctl print gui/$(id -u)/in.tldrift.monitor | grep -E "state|runs|last exit"`;
  - `grep '== trigger' logs/monitor.log | tail`;
  - a run manifest in `data/monitoring/runs/` with `"owner": "launchd@<host>"` and `"mode": "SCHEDULED"`;
  - `tldrift monitor-health` shows `last_attempt_at` near 01:00 UTC.
- **Limits:**
  - An agent runs only while you are logged in and the Mac is awake.
  - After sleep, launchd starts one missed trigger on wake.
  - While the Mac is off, nothing runs, and the next trigger catches up.
  - A laptop is **not** an always-on host.
  - To wake for the slot: `sudo pmset repeat wakeorpoweron MTWRFSU 06:25:00`.
- **Rollback:**
  - `launchctl bootout gui/$(id -u)/in.tldrift.monitor`, then `rm ~/Library/LaunchAgents/in.tldrift.monitor.plist`.
  - The ledger in `data/monitoring/` stays and is read-only for the app.

## Always-on deployment (systemd, ADR 0011)

1. **Install.** On a Linux host that stays on, create the user `tldrift` and check out the repository at `/srv/temporal-legal-drift`. Then run:
   - `python3 -m venv .venv`
   - `.venv/bin/pip install -e '.[pdf]'`
   - `.venv/bin/tldrift restore-release-inputs`
2. **Configure alerts.** Copy `deploy/systemd/tldrift.env.example` to `/etc/tldrift/tldrift.env` (mode 0640, `root:tldrift`). Set `TLDRIFT_ALERT_COMMAND`, and optionally a dead-man's-switch `TLDRIFT_HEARTBEAT_URL`.
3. **Enable the timers.**
   - Copy `deploy/systemd/*.service` and `*.timer` to `/etc/systemd/system/`.
   - Run `systemctl daemon-reload && systemctl enable --now tldrift-monitor.timer tldrift-health.timer`.
4. **Test the alert path once.** Run `systemctl start tldrift-alert@manual-test.service` and confirm the message arrives.
5. **Observe.**
   - `systemctl list-timers 'tldrift-*'`
   - `journalctl -u tldrift-monitor.service`
   - `tldrift monitor-health`

**What alerts:**
- `SCHEDULER_MISSED_RUN`: the trigger is not firing.
- `INGESTION_STALE`: no success for more than 48 h.
- Any non-zero exit of the monitor job.
- The heartbeat stopping: the whole host is down. This needs the external heartbeat service.

**Pause:** `systemctl disable --now tldrift-monitor.timer`. Keep the health timer so the pause is visible.

**Rollback** to the previous behaviour:
- `git checkout <previous release commit> -- deploy/systemd`;
- copy the units again and run `systemctl daemon-reload`.

The alert ledger is ignored by the older units.

## Verifying the units before deployment (no network, no live sources)

Run `sh deploy/container-check/run.sh` (needs Docker). It boots real systemd in a throwaway Debian 12 container with `--network none`, then checks:
- `systemd-analyze verify` passes on all units;
- the monitor job runs once per source;
- a repeat inside the window starts nothing;
- the health check fails on stale ingestion;
- the `OnFailure=` alert is delivered.

This verifies the units only; it is not a deployment.

## Exact installation on an always-on host (Debian/Ubuntu with systemd)

```sh
sudo useradd --system --create-home tldrift
sudo git clone https://github.com/PremCodes2005/Temporal-Legal-Drift-in-Indian-Code.git /srv/temporal-legal-drift
cd /srv/temporal-legal-drift && sudo git checkout <release commit>
sudo python3 -m venv .venv && sudo .venv/bin/pip install -e . "pypdf==6.16.2"
sudo .venv/bin/tldrift restore-release-inputs
sudo chown -R tldrift:tldrift /srv/temporal-legal-drift
sudo install -d -m 0750 /etc/tldrift
sudo install -m 0640 -g tldrift deploy/systemd/tldrift.env.example /etc/tldrift/tldrift.env   # then edit: alert command, heartbeat URL
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/tldrift-*.service /etc/systemd/system/tldrift-*.timer
sudo systemctl daemon-reload && sudo systemctl enable --now tldrift-monitor.timer tldrift-health.timer
sudo systemctl start tldrift-alert@install-test.service      # confirm the alert arrives
systemctl list-timers 'tldrift-*'
```

Record the host name, owner and the first scheduled run time in `docs/verification.md`.

**Copying existing state:** if `data/monitoring/` is copied from another machine, its 24 h windows are kept. A fresh host starts with all sources eligible.
