# Phase F checkpoint — RAG answers, scores and UI honesty

Date: 2026-10-12. Engineering results only; **legal/research gate UNVERIFIED**.

## Defects reproduced and fixed at source

| # | Defect (reproduced) | Root cause | Fix | Regression test |
| --- | --- | --- | --- | --- |
| 1 | "What changed in the IT Act … data privacy?" showed garbled IT 2008 OCR as **"Pre-amendment baseline"** and an unrelated consolidated passage (s.67A offences) as **"Post-amendment revision"**, and scored drift between them. | `_select_scoring_evidence` fell back to two best-matching excerpts with no provision alignment. | Drift is computed only for aligned versions: a consolidated-text footnote reconstruction of the queried section, or the before/after fragments of exactly one strongly corroborated graph-v4 transition whose clause appears in the retrieved instruction (via `graph-consumer-v1`). Otherwise `pair_status = instruction_and_consolidated_text_not_aligned`, metrics are `null`, and the "aligned pre/post" verification check fails. | `test_unaligned_instruction_and_consolidated_text_get_no_drift_scores` |
| 2 | Arbitration s.7 questions retrieved the IT Amendment 2008 instruction. | `relation_for_results` accepted a relation when only its target was retrieved; the amending Act's score was 0. | A relation needs both its amending Act and its target in the retrieved results. | `test_unrelated_amendment_is_not_paired_when_its_act_was_not_retrieved` |
| 3 | The extractive fallback text read "Amendment instruction used for baseline reconstruction" when nothing was reconstructed. | Fixed label | Now "Amendment instruction (source excerpt; no earlier version was reconstructed)". | test 1 |
| 4 | Sources with a known text-fidelity risk were quoted with no warning. | — | `source_fidelity_warnings` from the corpus manifest, shown in the UI as "Source text unreadable". | test 1 |
| 5 | The UI called feature-hash cosine "Semantic drift … meaning-level distance between embeddings". | Label | "Vector drift (feature-hash)" with an accurate description; API calculation trace states the method. JSON keys unchanged for compatibility. | `test_frontend_contract` |
| 6 | Extractive answers were indistinguishable from model output unless a configured model *failed*. | Warning only on failure | Every answer shows its generation method ("Extractive evidence summary … not a language-model conclusion"). | `test_frontend_contract`, `test_model_timeout_or_provider_error_yields_labelled_extractive_fallback` |
| 7 | Answer headings always said pre/post amendment. | Static labels | Headings follow `pair_status`: graph fragments, footnote reconstruction, or "Amendment instruction / Consolidated text (source excerpt)". Citation tags no longer say Baseline/Revision. | `test_frontend_contract` |

Retained aligned behaviour: "Compare Section 19 before and after the IT Amendment Act, 2008" uses the India Code consolidated-text substitution footnote (`consolidated_footnote_reconstruction`). It still scores drift, and now also warns that the IT 2008 source text is unreliable.

## Mode contracts

Generic and specific modes keep distinct output contracts (existing `test_specific_and_generic_modes_have_distinct_response_contracts`). The score basis is mode-independent (existing test).

## Frontend

- `npm run build` regenerated `web/`, and the committed assets are checked against the source bundle.
- CI's frontend job rebuilds with `npm ci` and diffs against `web/`.
- No JavaScript test runner is installed. `tests/unit/test_frontend_contract.py` checks the source and built assets statically.

## Not done

- **No browser or mobile audit.** Desktop/mobile visual, keyboard and contrast checks were not run in a browser; existing markup includes a skip link, `role="status"/"alert"` on the new notices, and focusable controls.
- **No live provider runs.** Live India Code and remote OpenAI-compatible providers were not exercised. The local Ollama model was used only for the Phase D materiality run.
- **Graph-aligned answers are rare.** They are reachable only for the 86 strongly corroborated v4 transitions with a matching amending Act in the retrieval relations config. Most comparison questions will now correctly show excerpts without drift scores.

## Gates

- Engineering: RAG, webapp and frontend-contract tests pass.
- Legal/research: **UNVERIFIED**. Scores remain diagnostics, not legal accuracy.
