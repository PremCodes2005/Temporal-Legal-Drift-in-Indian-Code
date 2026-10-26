# ADR 0025: Unattended daily source monitoring (2026-10-26)

## Status

Accepted. Builds on ADR 0008 (24-hour gate), ADR 0009 (monitored overlay) and ADR 0011 (systemd deployment).

## Context

The monitoring pipeline already gated each source to one start per rolling 24 h, held a cross-process lock and lease,
versioned documents by SHA-256, resumed interrupted stages, quarantined unreadable text, extracted candidates, updated the
separate overlay and listed discoveries. Four gaps stopped it from running unattended:

1. **Lost retries.** India Code discovery lists only items accessioned after the saved cursor. A record whose download
   failed was never listed again, so it was never retried.
2. **No fixed run time.** An hourly trigger and "24 h after the last start" moved the daily run an hour later whenever start-up
   took a few seconds longer than the day before.
3. **No scheduler for macOS.** Only systemd units existed.
4. **Alerts.** Nothing alerted on new records, and the hourly health check re-alerted on the same stale condition every hour.

## Decision

- **Daily slot.** `monitor-run --daily-at 06:30 --timezone Asia/Kolkata` (01:00 UTC).
  - A start up to an hour after its slot is on time. The next eligible time is 24 h later, and a start due within
    10 minutes waits for it, so start-up jitter or a trigger offset by up to an hour never skips a day.
  - The strict 24-hour rule is unchanged: no source starts sooner than 24 h after its previous start.
- **Missed runs.** The trigger stays hourly, so a missed slot (host asleep or off) is caught up at the next trigger. A
  catch-up more than an hour late moves the next eligible time to the first slot at least 24 h later, so the run returns
  to the slot, which can leave up to about 47 h between those two starts (inside the 48 h
  stale threshold).
- **Retries.** After a successful listing, versions of that source that failed before download are retried from the
  ledger. The existing three-attempt bound applies, after which the version is `UNRESOLVED`.
- **Machine states,** derived from the persisted state machine and never requiring a person:
  - `DISCOVERED`, `PROCESSED`, `CANDIDATE_AMENDMENT` (machine extraction, unverified);
  - `QUARANTINED` (source or text quality could not be established);
  - `UNRESOLVED` (other abstentions, or attempts exhausted), `FAILED_RETRYING`.
  No state promotes a candidate to a verified amendment; that still needs a recorded qualified-review decision, which does
  not exist.
- **Alerts once per key.** `monitor-notify` (and `monitor-run --notify`) sends pending alerts through `TLDRIFT_ALERT_COMMAND`
  as one message. Keys:
  - a record: official id + content hash;
  - a failed version;
  - a source condition: tied to the attempt that caused it, or to the missed eligibility time.
  A key is written to `data/monitoring/alerts_sent.v1.jsonl` only after delivery succeeds. On first use, records already
  listed are recorded as a baseline instead of being announced.
- **Schedulers.** Both call the same CLI.
  - systemd (Linux): a timer every hour on the hour UTC (:30 IST), with `Persistent=true`.
  - launchd (macOS): a job hourly at :30 local time (IST on this host), which runs once on wake after sleep.

## Consequences

- Health reports, per source:
  - `last_attempt_at`, `last_success_at`, `last_completed_at`, `next_eligible_at`;
  - `last_run_counts` (listed, retried, new, revised, unchanged, failed, metadata-only);
  - `stage` (`IDLE` or `RUNNING` with the lease holder), `freshness`, `schedule`;
  - `machine_states` counts across documents.
- Page views and questions still only read the ledger. Only the scheduled job or an audited manual command contacts a
  source.
- The base corpus, released graph, base index and releases are untouched. New text reaches answers only through the
  monitored overlay, labelled as unreviewed monitored material.
- A laptop runs the job only while awake. It is not an always-on host.
