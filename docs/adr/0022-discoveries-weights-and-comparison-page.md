# ADR 0022: Latest discoveries, transparent weights and a clause comparison page

Status: **accepted 2026-10-20**. Report: `reports/analysis_workspace/report.v5.md`.

## Decision

- **Latest discoveries (`source-notifications-v1`):**
  - A read-only view of the existing monitoring ledger: the review queue, documents, observations, machine-extracted candidates, source state and the review ledger. It adds no scraper and no new fetching, and leaves the 24-hour gate untouched.
  - One item per official record, newest first discovery first. Status wording is precise and never presents a document as a confirmed change to law; the review ledger has no action that could produce "verified".
  - Listings that were never downloaded are kept apart. Stale, failed and never-succeeded sources are stated.
  - The UI is a toggle in the top bar with an unread count, opening a column on wide screens and a full-width panel on phones. Read marks are kept in this browser only; there is no push and no account.
- **Weights:** the formula and weights are unchanged (reasons in `docs/methodology/tlds.v1.md`). tlds-v1.1 adds per-component contributions and a disagreement flag. `GET /api/methods/tlds` serves each weight's stated rationale and the held-out sensitivity, which the Score Calculation page shows.
- **Clause comparison page:**
  - `#comparison/<id>` shows the stored comparison record full length: provision, amending Act, operation, evidence status, both sides with page-level PDF and official links, verbatim and derived labels, marked changes, and the rule fields that changed.
  - Without a supported pair it explains why and shows no excerpts as versions.
  - It is linked from supported answers and from the Drift explanation page.
- **UI:**
  - a "Recently asked and suggested questions" control that scrolls to and focuses the chip area;
  - a system font stack and readable statutory text;
  - reduced-motion respected in CSS and in scripted scrolling.

## Rejected

- **Re-weighting towards legal effect:** it would remove the "material but Low" cases only by choice of weights, without any labelled evidence.
- **A separate notification feed or scraper:** it would duplicate monitoring and risk bypassing its gate.
