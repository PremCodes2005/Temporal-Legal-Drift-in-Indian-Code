# ADR 0003 — Keep drift, materiality and risk separate

Status: **documented existing implementation**, not a reconstructed historical approval. Audit base: `6803087`.

## Observed decision

`src/temporal_legal_drift/rag/metrics.py` calculates diagnostic textual/vector/conceptual drift and a separate retrieval/evidence-alignment score. `materiality/` assigns provisional amendment significance labels with separate review states. `risk/engine.py` evaluates a selected obligation against scenario facts and consequences; its scenario schema has no drift input, and an unassessed materiality field does not prevent risk assessment. See `schemas/risk/compliance_scenario.v1.schema.json`, `reports/materiality/implementation_status.md`, `reports/risk/checkpoint.v1.md`.

## Consequence and boundary

A high drift percentage cannot itself imply high legal materiality, a changed compliance answer, or high operational risk. **Inference:** separation guards against substituting textual distance for legal effect. Current materiality labels are silver, risk examples are conditional, and neither is independently legally validated.
