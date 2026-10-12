# Claim-to-evidence matrix (2026-10-12)

Every claim below is an **engineering** claim with the evidence that supports it. Nothing here is legal validation. Rows marked *not claimed* are things this repository must not be described as having.

| Claim | Evidence (artifact / command) | How verified | Limit |
| --- | --- | --- | --- |
| A clean checkout reproduces gates and tests | `data/releases/active_release.json` → commit-bound release manifest and lock; `tldrift restore-release-inputs`; CI `tests.yml` | `verify-reproducibility` runs a `git archive` of the source commit in a fresh venv without site-packages; remote CI observed green on `58c9868` | Normalized text, layout runs and OCR candidates are frozen inputs, not regenerated |
| Prior releases are immutable | v0.1.0 manifest `c85bb0c4…`, v0.2.0 `da07a1dd…` | Hashes checked at every release; `test_reproducibility.py` refuses re-cutting existing IDs, dirty trees and tampered inputs | — |
| Extraction is deterministic and source-anchored | `data/processed/amendments/v2.2/extraction.json`, provenance manifest | Write-once rebuild in each release accepted as byte-identical | Machine extraction; 232 UNKNOWN; no real-corpus accuracy |
| Page furniture cannot become parsed statutory text | `data/processed/layout/v1/gazette_furniture.json`; `layout_cleaning` on events | Regression test on Competition 6A verbatim pages; graph and gate rules | Gazette-specific rules; 2 operands still flagged |
| Unreliable source text never becomes a transition | Graph v4 `source_fidelity_flags`; Phase 3 gate `v4_weak_or_unreliable_evidence_never_strong_transition` | Gate re-checks the graph file | IT 2008 OCR candidate unverified |
| Short-fragment matches are not strong corroboration | `protocols/temporal_graph_protocol.v3.md`; 6 `MACHINE_SHORT_FRAGMENT_MATCH_ONLY` | Unit test and gate | Policy is a machine heuristic |
| Point-in-time answers are bounded | `graph-consumer-v1` | Tests: fragment labelling, abstention reasons, hash refusal | Only 5 dated transitions; fragments are not consolidations |
| Temporal applicability abstains on unsupported cases | `applicability/resolver.py` | Tests for publication-only, assent-only, deferred, partial, transitional, retrospective, conflicting, uncertain and multiple-active cases | Resolver needs **approved** facts; none exist for the real corpus |
| Materiality re-assessment is versioned and traceable | `data/silver/materiality_reassessment.v2.5.json` | 50 cases; 14 v1 extraction defects; missing operands never read as "identical" (test) | Silver/rule outputs only |
| LLM materiality assessments are schema- and citation-validated | `data/assessments/materiality_llm_assessments.v2.json` | qwen3:4b, temperature 0: 37/50 valid, 3 schema failures retained, 10 not assessed; exact-quote check | 34/37 labelled High; 13/37 agreement with Rule A; citation presence ≠ interpretation |
| Risk never uses drift and never turns unknown into "None" | `risk/engine.py`; `tests/unit/test_risk.py` | 26 risk tests | 2 conditional demonstrations only; stipulated applicability |
| RAG drift scores compare only aligned versions | `rag_pipeline.py`; `tests/unit/test_rag.py` | Regression tests for the unaligned-pair and wrong-relation defects | Feature-hash vectors, not semantic embeddings |
| India Code is checked at most once per 24 h and only new/revised bytes are processed | `monitoring/`, `data/monitoring/state.v1.json` (operational, git-ignored) | 9 monitoring tests; real bounded run: 3 new → review, repeat run 3 unchanged | e-Gazette access-limited; no always-on host; not complete coverage |
| Every displayed drift number recomputes from the response | drift-metrics-v2 | `tests/unit/test_drift_scoring.py` formula reproduction | Heuristic diagnostics, not legal accuracy or probability |
| Comparisons state their support and abstain honestly | comparison-record-v1 | `tests/unit/test_rag.py` | No PDF-coordinate highlighting |
| *Legal gold labels, legal accuracy, precision/recall/F1* | — | *not claimed* | No independent legal reviewer |
| *Frozen scientific benchmark* | `reports/phase7` (dry run only) | Gate `non_gold_release_cannot_freeze` | Freeze refused without gold and scenario expectations |
| *Temporal-drift model performance* | `reports/phase9` smoke run | — | Unscored without ExpectedChange labels |
| *Complete historical consolidations or comprehensive India Code coverage* | — | *not claimed* | 100-document pilot; fragments only |
