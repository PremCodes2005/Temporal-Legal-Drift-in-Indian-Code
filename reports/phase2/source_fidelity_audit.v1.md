# Stage 3A source-fidelity and extraction audit — v1

Date: 2026-10-12. Base commit `bd43b4d5bd3e3187f916661887b4dd84a55a51de` (`main`, clean before this work). Scope: the 2008 IT Amendment PDF and the five `CONFIRMED_EXTRACTION_DEFECT` rows of `reports/materiality/silver_disagreement_review.v2.3.md`. Machine findings only; **no legal correctness, gold label or expert validation is claimed.**

## Provenance chain

`configs/corpus/pilot_v1.json` (entry, URL, `known_extraction_risk`) → `reports/corpus/india-code-temporal-pilot-v1.lock.json` (SHA-256, `normalized_document_id`) → `data/normalized/<doc>.json` (pypdf text, `pdf:page:N` anchors; gitignored, local only) → `amendment_extraction/extractor.py` (clause segmentation, operation, operands, page/line, evidence text) → `data/processed/amendments/v2.1/extraction.json` (new) → `materiality/audit.py` → `data/silver/materiality_disagreement_audit.v2.4.json` + `reports/materiality/silver_disagreement_review.v2.4.md` (new).

## Finding 1 — the extractor in Git no longer reproduces the frozen v1 artifact

Regenerating in memory with the code at the base commit gives SHA-256 `d86c4361…` instead of the frozen `e7cd6fe1…` (`data/processed/amendments/v1/extraction.json`), while still labelling output `generalised-amendment-extractor-v1`. 155 event IDs differ, 123 shared IDs changed content, `UNKNOWN` operations rose 237 → 340 (compound clauses now abstain). The v1 file itself is intact and still matches its provenance hash. **Action:** the current behaviour is now labelled `generalised-amendment-extractor-v2.1` and written as a separate artifact; v1 is untouched. The v1 builder (`build-amendment-extraction-checkpoint`) would now refuse to write (`atomic_write_new` rejects non-identical overwrite) — that is intended.

## Finding 2 — 2008 IT Amendment text layer is unreliable OCR

Source `it-amendment-act-2008`, SHA-256 `f623743ebe88795caa83e8506319e53963005512f43c451fb61698e65fb4293d`, pypdf 1.0.0 parser, 20 blocks. The PDF's embedded text layer is low-quality OCR: e.g. page 1 masthead `~h~ ~a~ette (j{ ~i4`, clause 12 `other otrtCen and employees`, clause 32 `'dahonestly' / 'ftaudulently'`, `shall be insened`, `substiwltd`. No OCR engine (`tesseract`, `ocrmypdf`) is installed, so the text **cannot be read reliably** here.

Downstream reach (graph v2, `data/interim/temporal_legal_knowledge_graph.v2.json`): 35 amendment events; 32 unresolved transitions; **3 transitions** built from garbled operands — `transition_2014c6dc44b528934e3bbe2e` and `transition_53226993cc42430fbd1236bb` (`MACHINE_INTERNAL_CHECKS_ONLY`, `old_new_fragments_reconstructable: true`) and `transition_b8344a08e81a3a697186dfe5` (`MACHINE_CROSS_SOURCE_CORROBORATED`, "digital signature" → "electronic signature"). None of the 50 silver materiality tasks uses this source.

**Action:** every event from a manifest entry with `known_extraction_risk` now carries unresolved reason `source_text_unreliable` (35 records). Graph v2 is not rebuilt here; the three transitions must be demoted or re-evidenced in Stage 3B. Resolution requires an approved OCR method or a manually verified authoritative text.

## Finding 3 — the five confirmed defects

| # | Case (source page/line) | v1 defect | Status in v2.1 |
| --- | --- | --- | --- |
| 2 | Arbitration 1996 s.31 → **31A** (p8 l5) | anchor/inner-definition `costs` taken as payload; target was anchor section 31 | Target 31A and full payload extracted. **Residual:** payload contains page furniture → `operand_contains_page_furniture`; this explains the consolidated-snapshot mismatch. |
| 6 | Motor Vehicles 1988 s.74 (p13 l16) | compound clause (proviso + sub-clause) reduced to one operand | Abstains: `UNKNOWN` + `unclear_operation`. Not split. |
| 11 | Wild Life 1972 s.50 (p12 l2) | insertion anchor `derivative thereof` recorded as inserted text; 3-part compound | Abstains: `UNKNOWN` + `unclear_operation`. Not split. |
| 16 | IBC 2016 s.21 (p3 l28) | anchor `convertible into equity shares` recorded as inserted text | **Fixed:** `or completion of such transactions as may be prescribed,`; consolidated snapshot supports it. |
| 18 | Competition 2002 s.6 → **6A** (p6 l46) | inner definition `open offer` taken as payload; wrong target | Target 6A extracted. **Residual:** payload includes `IndiaCode`, `SEC. 1] THE GAZETTE OF INDIA EXTRAORDINARY 7`, and margin notes (`15 of 1992.`, `Insertion of a new section 6A.`, `Open offers, etc.`) → flagged. |

Classification: confirmed and fixed — 16, and target/payload boundary for 2 and 18; confirmed and abstaining (compound) — 6, 11; residual confirmed defect (page furniture/margin notes) — 2, 18. No case in this set is a genuine rule disagreement.

Page furniture affects 14/864 v2.1 operands overall. Running headers and the watermark are detectable; margin notes are interleaved in normalized text without layout coordinates, so the operand is **flagged, not cleaned**. Evidence text is preserved verbatim.

## Outputs and counts

- `data/processed/amendments/v2.1/extraction.json` — SHA-256 `91a453ad37eb0271652c672ecb683186231c8ac999a007373da4ff451503dc5d`; 37 Acts, 864 events, 1,508 unresolved records (v1: 1,525). Rebuild is deterministic (second run accepted as identical).
- `data/manifests/amendment_extraction_v2.1.provenance.json` — v1 hash, v1-vs-v2.1 comparison.
- `data/silver/materiality_disagreement_audit.v2.4.json`, `reports/materiality/silver_disagreement_review.v2.4.md` — read the frozen v2.1 artifact instead of re-running the extractor live. Counts equal v2.3 (5 defect, 4 review, 10 aligned, 2 cross-source); rows 2 and 18 gain `operand_contains_page_furniture`. Silver v1 (`d61f877a…`) and the v1/v2.x audit reports are unchanged.

## Not done / still unresolved

- Compound clauses (340 `UNKNOWN` events) are not split into sub-events; abstention is retained.
- Margin-note separation needs layout-aware parsing (re-normalizing all hash-locked documents) — not attempted.
- IT 2008 text needs OCR or manual authoritative text.
- Graph v2, the materiality round and the 50-case silver set are not regenerated from v2.1.
- `tests/unit/test_amendment_extraction.py::test_all_configured_amending_acts_are_accounted_for…` reads gitignored `data/normalized/`; it passes locally but would be expected to fail in a clean CI checkout (remote CI not inspected).

## Gates

- Engineering: 118 tests ran, 117 pass. The 1 failure is the Phase 11 reproducibility gate, `artifact_checksums_reconcile`: `reproducibility-v0.1.0` checksums the exact source files edited here. `validate-contract` exit 0; `check-gates` exit 2 (Phases 0–10 true, Phase 11 false).
- Legal/research: **UNVERIFIED**. Nothing here is legal validation.
