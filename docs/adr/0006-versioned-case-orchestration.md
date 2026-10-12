# ADR 0006 — Versioned, idempotent case orchestration

Status: **accepted 2026-10-12** (implementation: `src/temporal_legal_drift/orchestration/pipeline.py`, CLI `run-case`).

## Decision

One case flows through the stages source → graph → applicability → materiality → risk → explanation → review state. Stages are connected only by versioned interfaces:
- `graph-consumer-v1` on graph v4;
- the hash-checked risk registry;
- re-assessment v2.5 for silver materiality;
- `structured-explanation-v1`.

**Idempotence.** The correlation ID is a hash of the pipeline version, the case and the SHA-256 of every input. A rerun or restart therefore produces the same record, written once to `data/runs/<id>.json`.

**Failure handling.** A stage exception is recorded as `FAILED`, later stages are `SKIPPED_UPSTREAM_FAILURE`, and the case ends `ESCALATED_UNRESOLVED`.

**Fidelity.** A fragment whose amending instrument has a known text-fidelity risk is `UNRESOLVED`.

**Applicability.** This is `NOT_DETERMINED_NO_APPROVED_TEMPORAL_FACTS` until reviewed temporal facts exist. As a result every real case currently ends escalated, by design.

## Trade-off

A synchronous, in-process pipeline over frozen artifacts was chosen over a job queue: it is the smallest reliable option for a single-user research prototype. Observability comes from the per-stage record rather than live metrics. Risk uses its own stipulated applicability; whether risk should consume graph applicability is an open decision (`docs/implementation-plan.md`).
