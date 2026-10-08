# Phase 2 Gate Status

**Engineering/automated gate: PASSED**

**Generalised amendment-extraction checkpoint: PASSED (37 amending Acts)**

**Fidelity and qualified legal-review gate: PENDING**

## Implemented

- Deterministic plain-text, HTML, and XML parsers.
- Optional PDF text extraction with explicit scanned-PDF failure.
- Raw and normalized text preservation at block level.
- Unicode NFC, LF line endings, and documented whitespace normalization.
- Parser/version/source-hash provenance.
- Immutable normalized documents.
- Quarantine records for malformed, unsupported, unreadable, or integrity-invalid input.
- Synthetic unit and integration tests.
- Normalization of all 100 configured PDFs with source hashes and parser provenance.
- Generalised numbered-clause segmentation and amendment-cue detection.
- Principal-Act and target-provision identification without relying on the one explicit relation configuration.
- Operation classification for `INSERT`, `SUBSTITUTE`, `OMIT`, `REPEAL`, `RENUMBER`, `REPLACE`, `MODIFY`, and `UNKNOWN`.
- Explicit old/new wording and commencement extraction where the source states them.
- Evidence-linked amendment events containing source hash, page, line and full clause text.
- Canonical unresolved reasons and mandatory human-review status.
- Coverage and unresolved-rate metrics across all 37 configured amending Acts.
- Exact-match accuracy on eight controlled parser fixtures; real-corpus legal accuracy remains unreported without gold labels.
- Evidence-constrained silver labels with independent target/operation checks, exact wording support, confidence tiers and explicit abstention.
- Silver-label coverage, field acceptance, agreement and evidence-support metrics without misrepresenting them as legal accuracy.

## Human-review and fidelity blockers

- The Phase 1 pilot corpus is available locally but is not legally approved.
- No hand-checked fixtures derived from authoritative Indian legal sources exist.
- Parsing and fidelity thresholds are not approved.
- OCR policy has no implemented OCR engine and requires later method/version review.
- The 2008 IT Amendment PDF has legacy/garbled extracted glyphs and requires OCR or manual fidelity review before downstream legal use.
- Cross-reference and legal-structure fidelity have not received expert validation.
- Automated silver labels remain machine weak-supervision outputs rather than legal gold labels.
- The Phase 2 output contains machine candidates, not approved amendments or reconstructed legal transitions.

The frozen `v0.1` graph's 175 unresolved records remain preserved. Phase 2 produces 1,525 reason records across its candidate events; this number is not directly comparable because one event can receive multiple unresolved reasons. The extractor does not implement temporal applicability, materiality, compliance decisions, or autonomous legal conclusions.
