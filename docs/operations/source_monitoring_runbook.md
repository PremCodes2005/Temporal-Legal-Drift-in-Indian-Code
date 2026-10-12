# Source-monitoring runbook (India Code, daily)

Commands (from the repository root, Python 3.11+ with `pypdf==6.16.2` installed):

| Purpose | Command |
| --- | --- |
| Daily run (safe to call hourly; at most one attempt per source per rolling 24 h, UTC) | `tldrift monitor-run --owner <host-name>` |
| Audited manual retry inside the window | `tldrift monitor-run --owner <host> --manual-reason "<why>"` |
| Bounded history backfill (≤ 20 pages; does not move the daily window) | `tldrift monitor-backfill --owner <host> --pages N --reason "<why>"` |
| Health (also `GET /api/sources/health`) | `tldrift monitor-health` |

## Scheduling

Times are stored in **UTC**; display local time separately. Recommended trigger: an hourly cron or launchd job calling `monitor-run`. The 24-hour gate and the cross-process state lock make repeated calls idempotent.

```cron
17 * * * * cd /srv/temporal-legal-drift && .venv/bin/tldrift monitor-run --owner $(hostname) >> logs/monitor.log 2>&1
```

**Operational responsibility.** A job on a developer laptop runs only while the laptop is awake. It is a demonstration, **not** an operational guarantee. A deployment must name a host that is always on, an owner, and an alert:
- alert when `scheduled_ingestion_healthy` is false;
- or when `lag_hours` exceeds 48.

## State and outputs (`data/monitoring/`, git-ignored operational data)

| File / directory | Contents |
| --- | --- |
| `state.v1.json` | Per-source `last_attempt_at`, `last_success_at`, `next_eligible_at`, `cursor`, lease. |
| `observations.v1.jsonl` | Append-only discovery and download observations. |
| `runs/` | Write-once run manifests. |
| `review_queue/` | One item per new or revised content hash. |
| `stage_runs.v1.jsonl`, `normalized/`, `candidates/` | Stage cache keyed by content hash and stage version. |
| `data/raw/monitoring/sha256/` | Immutable artifacts. |

## Safety

- **Allowlist.** Only `indiacode.gov.in` is fetched, and redirects are validated. Limits: 50 MB per file, 2 s between requests, at most 5 pages × 20 items per run.
- **No automatic effect on the graph or index.** New or revised documents only enter the review queue; they never change the active graph v4, the RAG index or any release. A publication is not commencement.
- **e-Gazette is `ACCESS_LIMITED`:** use `MonitoringService.manual_import` with a reviewer and a reason.
- **Pause:** remove the cron entry. There is no hidden daemon.
