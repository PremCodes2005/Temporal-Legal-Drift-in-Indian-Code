# Phase 4 — Materiality Engineering Status

**Phase 4 engineering workflow: IMPLEMENTED; engineering tests/reproduction passed**  
**Silver dataset: FROZEN; 50 machine-generated cases, not gold**  
**Legal validation: UNVERIFIED**  
**Validated legal materiality classifier: NOT CLAIMED**

## Frozen baseline and retained predictions

- The existing 50-case silver artifact is preserved at `data/silver/materiality_silver_labels.v1.json`. Its content SHA-256 is `d61f877a4a211de91927ea93f5994e0b6bf2c4a0f0818893e5a81ae2b8fce646`; its immutable freeze record is `reports/materiality/materiality_silver_frozen.lock.json`.
- Every row retains Rule A and Rule B labels, rationales, evidence/source links, and the pre-existing provisional tie-break. The tie-break is not an independent adjudication and is never described as truth.
- The two deterministic rules agree on 31/50 cases (62%); Cohen's kappa is 0.474. The 19 disagreements are Low-versus-Medium. These are rule-to-rule silver agreement statistics, not legal accuracy.
- `reports/materiality/silver_disagreement_review.v1.md` lists all 19 cases, competing predictions, rationale and available excerpts. It intentionally makes no resolution.
- `reports/materiality/silver_disagreement_review.v2.3.md` is the versioned source-re-extraction and rule-reassessment audit. It confirms five extraction/alignment defects, four compound clauses requiring review, ten cases aligned on re-extraction, and two full inserted-unit candidates requiring consolidated-source revalidation. V1 labels and evidence remain unchanged.
- Rule B v2 no longer treats low edit similarity alone as Medium. Across the 19, it emits two provisional High candidates (both held because the full inserted text did not match the available consolidated snapshot) and abstains on 17. There are no comparable eligible rule pairs, so v2 agreement is **not calculated**; zero remaining Low/Medium pairs is not evidence of agreement.

## Proposed operational rubric

- `configs/annotation/proposed_materiality_rubric.v1.json` defines version 1.0.0 and the four operational classes High, Medium, Low and None.
- The rubric is explicitly a proposed research rubric, **not legally validated guidance**. It separates materiality from temporal applicability and scenario-specific compliance consequence; it also separates the workflow statuses `REVIEW_REQUIRED` and `INSUFFICIENT_EVIDENCE` from materiality labels.
- Its current technical registry lists ten dimensions. Approval of the dimension count remains a project decision; no legal reviewer has approved it.

## LLM assessment and safeguards

- The independent assessment path sends each case's amendment operation, before/after text, linked source evidence and proposed rubric to the configured model. Structured output must include label, exact source quotes, rationale, uncertainty and insufficient-evidence flag.
- JSON shape and canonical classes are checked. Each cited quote must be present in the submitted text for the cited source ID. This establishes citation integrity only; it does **not** establish that the interpretation is legally correct.
- A single format-repair retry is allowed for malformed/schema-invalid output. Both attempts are retained; the same schema and provenance validation run again. There is no retry relaxation, and invalid cases remain `REVIEW_REQUIRED` without a label.
- A valid model label remains `REVIEW_REQUIRED`; an explicit abstention is `INSUFFICIENT_EVIDENCE` with a null materiality class. Individual rule predictions, LLM output, and optional reproducible majority ensemble remain distinct; no ensemble or model agreement is gold.
- A local smoke attempt with the currently configured Ollama/Qwen model echoed the input payload instead of returning the required assessment JSON. It was rejected by validation. The full 50-case LLM run has **not** completed; therefore no LLM silver-agreement result is reported. The CLI preserves each per-case failure and allows a bounded repair attempt when run.
- The Phase 4-focused test suite and fresh-environment repository reproduction passed. The real model's behavior after the new repair retry remains unverified; this engineering result does not imply legal validation.

## None-class search and class coverage

- `reports/materiality/none_coverage_search.v1.md` records a scan of 117 available graph transitions. One normalized-text-equal candidate was found, but it failed source/context corroboration and was rejected as a `None` example.
- No `None` label was created. The None category remains **unevaluated** on real corpus examples. Synthetic fixtures are used only in unit tests and are explicitly test-only.

## Properties testable without legal experts

Engineering can test deterministic outputs, schema conformance, data/provenance traceability, exact quote presence, unchanged frozen hashes, missing-class detection, abstention behavior, reproducible ensemble mechanics, and consistency under controlled input perturbations. These checks establish process reliability and evidence linkage—not legal interpretation validity.

Without qualified legal review, this project cannot claim legally correct materiality labels, an approved taxonomy, legal gold labels, legal accuracy/precision/recall/F1, or expert validation. Rule/LLM agreement against the silver labels may be reported only as **silver-label agreement**, with the shared-rule/circularity limitation stated.

## Commands

From the repository root, with the project's Python environment active:

```sh
python -m temporal_legal_drift.cli --project-root . freeze-materiality-silver
python -m temporal_legal_drift.cli --project-root . search-materiality-none
python -m temporal_legal_drift.cli --project-root . assess-materiality-with-llm
python -m temporal_legal_drift.cli --project-root . build-materiality-ensemble
```

The LLM command requires a configured, reachable provider. Assessment and ensemble outputs are immutable/versioned; choose a new output version rather than overwriting a different existing artifact. No Phase 5 work is authorized by this Phase 4 status report.
