# ADR 0007 — Append-only, hash-chained review ledger

Status: **accepted 2026-10-12** (implementation: `src/temporal_legal_drift/review/ledger.py`).

## Decision

Reviewer actions on case runs are appended to `data/reviews/ledger.v1.jsonl`. Each entry carries:
- a sequence number and the SHA-256 of the previous entry;
- the reviewer ID and role from `configs/review/reviewers.v1.json`;
- the prior and new state, a mandatory reason, and a UTC timestamp;
- `legal_validation: UNVERIFIED`.

**Rules:**
- **Stale state:** a write must state the expected prior state, so a stale view cannot overwrite a newer decision.
- **Tampering:** detected by re-hashing; it blocks further entries.
- **No legal approval:** the four actions (acknowledge, request changes, escalate, record opinion) never yield a "legally approved" state, and the registry currently lists no qualified legal reviewer.

## Trade-off

A JSON Lines file with an in-process lock suits a single-host research prototype. It is not a multi-host database: concurrent writers on different hosts would need a database with serializable transactions.
