# Latest discoveries, transparent weights and clause comparison

Decision: ADR 0022. Running app on port 8799 (new backend), real Chrome, 2026-10-20. Screenshots in `screenshots/v5/`.

## Baseline before the change (v0.20.0, clean tree)

- **Tests:** Python 308 OK; vitest 51 passed; 12 phase gates passed.
- **Discoveries:** the assistant showed only the one-line "Scheduled ingestion" summary. Individual discovered documents were visible only through the case-review API.
- **Weights:** Score Calculation showed each component's value and weight, but neither each component's points nor why the weights are what they are, and not the held-out sensitivity.
- **Comparison:** the clause comparison existed only as a capped panel on the answer, with no address of its own.

## Walkthrough

| Feature | What was checked | Result |
|---|---|---|
| Latest discoveries | Toggle in the top bar | "Latest discoveries, 4 unread"; the panel opens as a column, focus goes to its heading, and the page makes room |
| | Sources | e-Gazette: "Not checked recently; no successful check for 158 hours". India Code: "Last check failed; the last check ended with source unavailable". Both with last success and attempt times |
| | Items | 4 documents, newest first: 1 "New document awaiting review" (the MSMED commencement notice) and 3 "Possible amendment text found by machine extraction; not verified", each with source, published date, discovery time and official link. 21 listings that were not downloaded are folded separately |
| | Read marks and keyboard | "Mark as read" moves the count to 3 unread; Escape closes the panel and returns focus to the toggle; at 390px it is a full-width panel with no overflow |
| Weights | IBC s.99, Score calculation | Points 0.1 + 0.0 + 20.0 + 0.6 for the 20.7 total, with the worked formula; inputs (clauses E1–E3, the deadline field, rule elements); "Read legal effect on its own" warning |
| | Rationale and sensitivity | Each weight's stated rationale; "not learned from data, not optimised and not legally validated"; 42 / 53 / 0 / 58 material-but-Low changes under the four weightings |
| Clause comparison | Opened from "View detailed clause comparison" on the answer | `#comparison/<id>`: provision, Act 6 of 2026 (from the footnote), evidence status, both sides full length with page-98 PDF and official links, derived side labelled, changes marked, rule fields listed |
| | Navigation | Refresh keeps the page; Back returns to the answer; Forward returns to the comparison; at 390px the sides stack with no overflow |
| | Unsupported pair | Explains the reason and shows no excerpts as versions |
| Question area | "Recently asked and suggested questions ↓" | Scrolls to and focuses the chip region; scrolling is instant when reduced motion is set |
| Accessibility | `browser-a11y-check.mjs` | Passed at 320–480px. It first found that the top bar overflowed at 320px; the toggle now shows "Discoveries" there and keeps its full accessible name |

## Not established

- Whether the monitored sources list every amendment.
- Whether any discovered item changes the law; none is reviewed.
- Whether any weighting is more correct; there are no expert labels.
- Legal accuracy.
