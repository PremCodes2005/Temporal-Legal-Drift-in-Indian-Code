# ADR 0008 — Incremental, 24-hour-gated official-source monitoring

Status: **accepted 2026-10-12** (implementation: `src/temporal_legal_drift/monitoring/`; plan.md §0.7; S1 decision record `docs/sprint/s1_source_access_decision.v1.md`).

## Decision

- **India Code:**
  - Discovery reads DSpace REST `discover/search/objects`, sorted by `dc.date.accessioned` descending, down to a persisted cursor.
  - At most one automatic attempt is made per source per rolling 24 hours. The gate and lease live in a state file under an `fcntl` lock, so restarts and concurrent workers cannot duplicate a run.
  - The served-bytes SHA-256 is the identity; the repository MD5 is recorded.
  - Unchanged bytes only append an observation. New or changed bytes get an immutable artifact, a revision link to the previous hash, cached parse and extract stages (keyed by content hash and stage version), and a review-queue item.
- **e-Gazette** is `ACCESS_LIMITED`, with a manual import that carries a reviewer and a reason.
- **New documents never activate a graph or index automatically.**

## Trade-off

- **Gating:** a file lock with a rolling window was chosen over a job service, as the smallest reliable mechanism. It needs a single shared filesystem and an always-on host for operational use (see the runbook).
- **No auto-activation:** this keeps legal effect behind review, at the cost of latency between discovery and the answers served.
