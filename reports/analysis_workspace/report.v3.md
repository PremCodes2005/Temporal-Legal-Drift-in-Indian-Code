# Restored v0.13.0 assistant and explanation pages

Reference UI: v0.13.0 (commit `6db1c49`). Decisions: ADR 0019 (Drift explanation and Score calculation pages) and ADR 0020 (assistant page). The backend, scoring and saved analyses are unchanged.

## What a reader sees

| Address | Page |
|---|---|
| `#assistant`, `#assistant/<id>` | A question box with Specific/Generic mode, then the answer and "The change, measured" (scored values only, with buttons to the two pages). Then the clause comparison (scrollable before/after boxes with source, page and verbatim/derived labels) and the evidence list. "Check your situation" and "Sources, quality and review" are folded. |
| `#drift`, `#drift/<id>` | Drift explanation: level guide, component breakdown, whole clauses side by side with their sources, and the detected changes and why they matter |
| `#calculation`, `#calculation/<id>` | Score calculation: the compared clauses with hashes, why these clauses were compared, the values and formulas, the rule-field contributions, the worked combined calculation and the separate situation outcome |

Older links (`#analysis/<id>[/<view>]`) open the matching page. A link ending in `/scenario` opens the assistant with "Check your situation" unfolded.

## Real-Chrome run (2026-10-13, running app on port 8799)

| Check | Result |
|---|---|
| Fresh `#assistant`: type the IBC s.99 question, choose Specific, press Analyse | Answer at `#assistant/an_23dd…`; no tab list; order: answer → the change, measured → clause comparison → evidence → folded situation → folded review → official source |
| "Explain the change…" button, then the sidebar Score calculation, then the sidebar assistant | `#drift/<id>` → `#calculation/<id>` → `#assistant/<id>`, with the same answer and the question kept |
| Back ×3, forward | calculation → drift → assistant → drift |
| Refresh on `#drift/<id>` and `#assistant/<id>` | Same page and analysis |
| Facts re-run (15 days) from "Check your situation" | New analysis ID; "Does your answer change: Changed" |
| 390px: assistant, drift, calculation | No horizontal overflow; the assistant page is 4,766px tall (6,729px before the clause boxes were capped) |
| `frontend/scripts/browser-a11y-check.mjs` | Passed: "Check your situation" reachable and opened by keyboard; no unnamed controls; no overflow at 320–480px |

## Screenshots (`screenshots/v3/`)

- `assistant-empty-desktop.jpg`: the question page before asking.
- `assistant-question-area-with-answer.jpg`: the full question area (status, scheduled ingestion, suggestions) kept above an answer, on the user's server at port 8765.
- `assistant-ibc99-desktop.jpg` and `assistant-ibc99-390.jpg`: the answer page.
- `assistant-ibc99-day15-situation.jpg`: the unfolded situation after a facts re-run.
- `drift-ibc99-desktop.jpg` and `drift-ibc99-390-top.jpg`: the Drift explanation page.
- `calculation-ibc99-desktop.jpg` and `calculation-ibc99-390-top.jpg`: the Score calculation page.

Legal validation: UNVERIFIED.
