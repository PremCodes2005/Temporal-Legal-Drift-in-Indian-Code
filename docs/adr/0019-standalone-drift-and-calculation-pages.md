# ADR 0019: Standalone Drift explanation and Score calculation pages

Status: **accepted 2026-10-13**. UI reference: v0.13.0 (commit `6db1c49`), components `DriftExplanation` and `ScoreCalculation` in `frontend/src/App.jsx`.

## Context

v0.15 and v0.16 showed "Drift Explanation" and "Score Calculation" as two of six tabs inside the analysis workspace. The project owner asked for the earlier standalone sidebar pages at `#drift` and `#calculation`: their layout, navigation and clarity. Scoring and backend contracts were to stay unchanged.

## Decision

- **Two sidebar pages:** `frontend/src/ExplanationPages.jsx` renders "Drift explanation" (`#drift/<id>`) and "Score calculation" (`#calculation/<id>`) as standalone pages. Both read the same stored analysis as the assistant.
  - **Addresses:** plain `#drift` and `#calculation` open the analysis last shown. Old `#analysis/<id>/drift|calculation|scores` links open the pages.
  - **Navigation:** refresh and back/forward keep the page and the analysis.
  - **Workspace:** the analysis workspace keeps four tabs (Answer, Compare Evidence, Scenario & Impact, Sources & Review).
- **Layout adapted from v0.13.0:**
  - **Drift explanation:** a level guide, a "Calculated classification" breakdown, the whole before and after clauses side by side, the detected changes and the evidence list.
    - Each side names its document, page and line, and whether the text is verbatim or derived.
  - **Score calculation:** the compared clauses with their sources and SHA-256, why these clauses were compared, the values and formulas, the rule-field contribution table, the worked combined calculation, and the separate situation outcome.
- **Scores displayed (unchanged methodology):**
  - Wording drift and rule drift (legal-change-fingerprint-v1.2) as the separate measures.
  - The tlds-v1 combined indicator as the only combined score, with legal-effect drift shown beside it.
  - Legacy drift-metrics-v3 only in a collapsed section labelled "superseded, not the combined indicator".
  - The browser computes no score.
- **Guide levels:** the three levels group the tlds-v1 provisional bands: Very low and Low → Low; Moderate; High and Very high → High. Their names and ranges are read from the stored analysis, and no new thresholds are introduced.

## Rejected

- **Restoring v0.13's page code verbatim:** it read the fragment-based v3 score as the overall score, and showed "Evidence unavailable" when a chunk was missing.
- **Showing the v3 overall beside TLDS:** two unexplained combined scores.
