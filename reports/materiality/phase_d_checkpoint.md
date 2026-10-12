# Phase D checkpoint — materiality re-assessment and LLM assessment

Date: 2026-10-12. Every label here is a machine opinion; **legal/research gate UNVERIFIED**. The frozen 50-case silver dataset (`d61f877a…`) and all earlier audits (v2–v2.4) are unchanged.

## Re-assessment v2.5 (`data/silver/materiality_reassessment.v2.5.json`)

All 50 frozen cases (the 19 original disagreements are a subset) were re-extracted with extraction v2.2.

**How cases are matched:**
- A split compound clause is matched to the one part whose target and v1 wording identify the case. Otherwise the case is not matched.
- Source support is checked against the layout-cleaned body.

**Extraction status by case group:**

| | 19 disagreements | 31 v1 agreements | Total |
| --- | --- | --- | --- |
| Confirmed v1 extraction/alignment defect | 5 | 9 | **14** |
| Re-extracted aligned | 11 | 20 | 31 |
| Review required (unmatched/compound) | 3 | 2 | 5 |

So 9 of the 31 cases where the two v1 rules *agreed* were agreements on defective fragments.

**Rule outputs:**
- Rule A emits 42 labels and Rule B 22.
- Among the 20 cases where both emit an eligible label, they agree on all 20. That is rule-to-rule silver agreement from rules that share cues, not validity.
- The four 31A/6A Rule A/B labels are held for cross-source review, because the frozen round attached the s.31/s.6 consolidated snapshot rather than s.31A/s.6A.

**Defect fixed during this phase:** for whole-section substitutions (Disaster Management s.11, s.23), v2.2 correctly has no old/new operands. The audit turned `None` into `""`, and both rules then emitted **None** ("identical text"). Missing required operands now route to REVIEW_REQUIRED with no label (regression test added). The latent flaw existed in the v2.4 code path too.

## None class

`reports/materiality/none_coverage_search.v2.*` scanned graph v4's 136 transitions and found 0 normalized-identical candidates. The None class remains **unevaluated**. The search command now writes versioned, write-once outputs; it previously replaced v1 in place.

## LLM assessment v2 (`data/assessments/materiality_llm_assessments.v2.json`)

**Configuration:**
- Local Ollama 0.33.2, `qwen3:4b` (Q4_K_M, digest `359d7dd4…`), temperature 0, thinking disabled, JSON format.
- Inputs: corrected v2.2 fragments from re-assessment v2.5 plus the proposed rubric v1.
- 40 cases had a supported fragment. 10 were **not sent to the model** (`NOT_ASSESSED_FRAGMENT_UNRESOLVED`).

**Results:**

| | Count |
| --- | --- |
| Schema- and citation-valid | 37 |
| Rejected: output fields did not match the schema (retained with raw output) | 3 |
| Not assessed (unresolved fragment) | 10 |
| Valid labels | High 34, Low 3, Medium 0, None 0 |
| Insufficient-evidence abstentions | 0 |

**Silver-label agreement only** (not accuracy):
- LLM vs the v1 tie-break: 12/37 (32.4%). That reference partly rests on defective v1 fragments.
- LLM vs v2.5 Rule A on the same corrected fragments: 13/37.
  - The disagreements are almost all the LLM saying High where Rule A says Low (15) or Medium (9).

**Interpretation.** The model strongly favours High and never abstained. The data does not support treating it as a reliable materiality signal, and no ensemble was built from it. Citation integrity means each quote occurs in the supplied text; it does not validate the interpretation.

## Gates

- Engineering: materiality tests pass (20), including new tests for override routing and missing operands.
- Legal/research: **UNVERIFIED**. No gold labels, and no precision/recall/F1.
