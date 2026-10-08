# Generalised Amendment Extraction Protocol v1

The extractor processes every corpus entry configured as an `amending_act`. It segments numbered clauses, detects amendment cues, identifies the principal Act and affected provision, classifies the operation, extracts explicit old/new wording, and records commencement evidence.

Every emitted event includes the source document hash, page, line and complete evidence clause. Machine confidence is extraction confidence, not legal correctness. Every event remains `HUMAN_REVIEW_PENDING`.

Failures are never discarded. They are assigned one or more canonical reasons: `target_not_found`, `ambiguous_section`, `unclear_operation`, `missing_old_text`, `missing_new_text`, `commencement_unclear`, or `parsing_failure`.

Real-corpus accuracy is not reported until reviewed gold labels exist. Phase 2 reports real-corpus field coverage and unresolved rates, plus exact-match accuracy on controlled parser fixtures.

## Automated silver labels

The silver labeller independently checks each extracted field against the source text. Target and operation labels require agreement between separate lexical and structural rules. Old/new wording must be exactly supported after conservative normalization. Dates must be present in the complete normalized document. A core disagreement causes the record to abstain rather than forcing a label.

The release reports auto-label coverage, abstention, per-field acceptance, exact evidence support and mean rule agreement. These metrics describe reproducibility and internal consistency. They are not precision, recall, or legal accuracy, and silver labels must not be used as gold test labels.
