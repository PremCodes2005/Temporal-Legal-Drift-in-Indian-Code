# Source-monitoring runbook (India Code and e-Gazette, daily)

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

- **Allowlist.** Only `indiacode.gov.in` and `egazette.gov.in` are fetched, and redirects are validated. Limits: 50 MB per file, 2 s between requests, at most 5 pages × 20 items per run.
- **No automatic effect on the graph, base index or releases.** New or revised documents enter the review queue. Their text is served only through the monitored overlay (`data/runtime/rag_overlay`), labelled `monitored_unreviewed` / `HUMAN_REVIEW_PENDING`, bound to the base index identity and switched by an atomic pointer (ADR 0009). Graph v4, the base RAG index and every release are unchanged. Applicability stays `NOT_DETERMINED`; a publication is not commencement.
- **e-Gazette** is `SUPPORTED_FRAGILE_HTML_DISCOVERY` (`docs/sprint/s1_source_access_decision.v2.md`): a session listing of “Bills & Acts” plus static PDFs. A layout change fails visibly (`SourceShapeError`) and nothing new is served. `MonitoringService.manual_import` remains the fallback.
- **Known e-Gazette TLS issue (2026-10-12):** the server omits its intermediate certificate, so Python reports `CERTIFICATE_VERIFY_FAILED`. Do **not** disable verification. Fix by pinning the official Let's Encrypt intermediate for that host (open follow-up).
- **Pause:** remove the cron entry. There is no hidden daemon.
