# ADR 0009 — Per-document state machine, cross-portal linking and index overlay

Status: **accepted 2026-10-12**. Extends ADR 0008. Implementation: `monitoring/service.py` (`source-monitoring-v2`), `monitoring/egazette.py`, `rag/retriever.py` (`update_monitored_overlay`), `versioning/consumer.py` (`candidate_target`).

## Decision

1. **Persisted state machine per document version.**
   - The states are DISCOVERED → FETCHED → HASHED → VERIFIED → EXTRACTION_PENDING → PROCESSED, or REVIEW_REQUIRED / FAILED. Each transition is persisted before the next stage, in `data/monitoring/documents/`.
   - `resume_incomplete` finishes only the missing stages from the stored artifact.
   - FAILED versions retry at the next eligible run; after three attempts they become REVIEW_REQUIRED.
2. **Identities.**
   - The official ID identifies a source record, and the raw SHA-256 identifies bytes.
   - A metadata fingerprint (repository MD5, size, `lastModified`, listing fields) avoids re-downloading when the source describes unchanged content.
   - A normalised-evidence-text fingerprint links the same amendment discovered in both portals into **one** candidate with two provenance entries. It never replaces the raw hash.
3. **Downstream through existing interfaces:** parser, extractor (`generalised-amendment-extractor-v2.2`), read-only graph-v4 target mapping, applicability recorded as `NOT_DETERMINED` with publication as an unapproved fact, and Rule A materiality triage as non-gold. Every document then enters review.
4. **Index overlay.**
   - Processed documents are chunked into a small, content-addressed overlay bound to the base index's `index_identity`. It is activated by an atomic pointer swap, and the previous overlay's hash is recorded for rollback.
   - The retriever ignores an overlay that has been tampered with or is bound to another base, and labels overlay chunks `monitored_unreviewed`.
   - The 100-document base index is never rebuilt for a new document.

## Trade-off

- **Overlay vs. new index version:** the overlay keeps new documents searchable without breaking the frozen index's fingerprint. Promoting reviewed documents into a new base-index version stays a deliberate, versioned step.
- **Text fingerprint:** linking only by normalised evidence text misses cross-portal pairs whose PDFs extract differently. Those stay as separate candidates for review, which is the safe failure.
- **Migration:** documents ingested by `source-monitoring-v1` have observations but no state records. v2 will process them once on their next discovery.
