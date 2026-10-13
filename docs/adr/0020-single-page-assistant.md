# ADR 0020: Single-page Legal drift assistant

Status: **accepted 2026-10-13**. UI reference: v0.13.0 (commit `6db1c49`), `AssistantWorkspace` and `RagResultV2` in `frontend/src/App.jsx`. Report: `reports/analysis_workspace/report.v3.md`.

## Decision

- **No tabs:** the assistant page shows one stored analysis as a single page (`frontend/src/AssistantResult.jsx`), not the four-tab analysis workspace, which is removed.
- **Page order (v0.13.0):**
  1. question box and mode;
  2. answer;
  3. "The change, measured": scored values only, plus buttons to `#drift` and `#calculation`;
  4. clause comparison;
  5. evidence list;
  6. source-quality warnings.
- **Folded sections:** personal-situation inputs and results ("Check your situation"), and materiality, provenance, verification and review ("Sources, quality and review"). A re-run with facts unfolds the situation.
- **Address:** `#assistant/<id>`. Older `#analysis/<id>[/<view>]` links still open the matching page.
- **Clause comparison:** each side's text is in a keyboard-scrollable box, so the page stays short. The full clauses are on the Drift explanation page.
- **Mode switch:** the Specific/Generic buttons expose `aria-pressed`.
- **Question area (as in v0.13.0):** it stays complete above every answer: heading, India Code status, the scheduled-ingestion line, the labelled question box and the three suggested questions. It is not collapsed once an answer appears.

## Not changed

Backend, response contract, scoring and saved analyses. The browser computes no score.
