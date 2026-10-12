# ADR 0001 — Source provenance and version-coupled index

Status: **documented existing implementation**, not a reconstructed historical approval. Audit base: `6803087`.

## Observed decision

Legal artifacts carry source URLs, timestamps and SHA-256 hashes; duplicate bytes are reused and revised bytes form a new record. The local RAG index is versioned with dataset, graph and corpus/graph fingerprints; `ensure_index()` refuses an incompatible existing index instead of overwriting it. Evidence: `src/temporal_legal_drift/ingestion/pipeline.py`, `ingestion/metadata.py`, `rag/retriever.py`, `data/manifests/artifact_versions.json`, `reports/phase0/gate_status.md`.

## Consequence and boundary

This enables technical provenance and detects a stale index/graph pairing. **Inference:** auditability and reproducibility are likely motivations, but no decision record of that original rationale was found. A matching hash does not prove the downloaded text is the correct legal interpretation; source fidelity and legal review remain separate. Live India Code content is a supplement, not part of the frozen local corpus by implication.
