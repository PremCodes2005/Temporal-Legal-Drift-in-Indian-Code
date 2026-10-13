# ADR 0017: Separate Drift Explanation and Score Calculation views; rule-drift v1.2 (rag-answer-v5)

Status: **accepted 2026-10-13**. Method delta: `docs/methodology/legal_change_fingerprint.v1.2.md`. Report: `reports/analysis_workspace/report.v2.md`.

## Context

The v0.14.0 five-view workspace (ADR 0016) still had problems:

- **Answer view:** it listed Outcome and Materiality as "Cannot determine" or "needs your facts" next to valid answers. Composition also always added an "Effect on your question: your facts are needed" section.
- **Navigation:** the separate "Drift explanation" and "Score calculation" entries that v0.13 had were gone, folded into one dense "Scores & Method" view.
- **Scoring (audit of all 86 corroborated transitions):** rule-drift v1.1 had errors at their source:
  - **Wrong permissions:** inserted list items and Explanations scored their `may`/`shall` as new permissions or duties (IBC s.240, SEBI s.11B).
  - **Double counting:** one fine was counted as both penalty and threshold (MV s.180 and s.181), and an imprisonment term as both penalty and deadline (THOA s.20).
  - **Missed changes:** count limits (BR s.45ZC "not exceeding four"), approving authorities (Companies s.14 Tribunal → Central Government), "consecutive" periods (Companies s.124) and "three hundred and thirty days" were not detected.
  - **False zeros:** real changes were reported as 0/100 (Companies s.134 and s.164 new list items; MV s.170 cross-reference).
- **Footnote parsing:** footnote reconstruction failed on hyphenated or line-wrapped substituted words. So IBC s.99 "ten days" → "twenty-one days" (Act 6 of 2026) abstained.
- **Materiality triage:** on-the-fly triage ignored number words.
- **Outcome drift:** it asked for facts even when no fact could decide the change.

## Decision

- **Contract `rag-answer-v5`:**
  - `legal-change-fingerprint-v1.2` (rule-drift-v1.2) with `fingerprint.reading`: plain-language sentences built from the components' own details, with their evidence IDs;
  - `determinations-v4` (triage-input-v2 number normalisation);
  - `answer-composition-v2` (concise before/after excerpts, "Key change", an effect section only when facts were applied).
- **Version history:** the v4 schema and stored v4 records are kept; the UI opens both.
- **Rule drift v1.2:** see the methodology delta. A value is reported only when a supported field changed. Identical normalised text scores 0. Any other change without a supported field is "Not scored", with one of three reasons: CROSS_REFERENCE_ONLY, TERM_SUBSTITUTED or UNSUPPORTED_RULE_FIELD.
- **Outcome drift:** it asks for facts only when a fact could decide the change; otherwise it reports a method limit. `answer_change` mirrors this.
- **Six views of one stored analysis:** Answer, Compare Evidence, Drift Explanation, Score Calculation, Scenario & Impact, and Sources & Review.
  - **Answer view:** shows only supported values and one "Check your situation" action.
  - **Drift Explanation:** words, rule fields and why each matters, kept apart from the situation outcome.
  - **Score Calculation:** inputs, formulas, every field's weight and contribution, and links from each field to its exact words in Compare Evidence.
  - **Sidebar:** "Drift explanation" and "Score calculation" open those views of the current analysis.
  - **History:** tab changes are pushed to browser history, so back and forward work. Old `…/scores` links open Score Calculation.
- **Footnote parsing:** hyphenated and line-wrapped substituted words are matched.

## Rejected

- **Reverting to the v0.13 single-page explanation pages:** they recomputed from browser state and lost evidence on navigation.
- **One combined change score:** it hides the small-wording/large-rule disagreement, which is now explained in words instead.
- **Showing "Not scored" or "Cannot determine" cards on the Answer view:** the limits are explained in the views where the detail belongs.
