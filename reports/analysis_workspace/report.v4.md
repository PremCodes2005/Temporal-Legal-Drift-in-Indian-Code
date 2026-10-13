# Act-only questions, section choice and FAQ

Decision: ADR 0021. Running app on port 8799, real Chrome, 2026-10-13.

| Check | Result |
|---|---|
| "What changed in the Motor Vehicles Act?" | 27 sections with a supported comparison; the 8 most relevant listed, each with status, reason, amendment and source PDF page; no whole-Act score |
| Keyboard: focus "Compare section 194", press Enter | `#assistant/<id>`; "Section chosen from the list: section 194 of the Motor Vehicles Act 1988"; question unchanged; scores wording 2.4%, rule 30/100 |
| Drift explanation page, then Back twice | Same chosen analysis, then the Act-level list again |
| FAQ page, with an old answer showing: "Ask this question" on the Disaster Management 2025 card | The box shows that question immediately; exactly 1 request; 13 sections of the 2025 amendment listed |
| Recently asked / follow-ups | Two distinct questions plus "Clear history"; follow-ups "Compare section 20 / 31 of the Disaster Management Act 2005 before and after the 2025 amendment." |
| Every generated follow-up for the 6 Act-only FAQ questions (12) | All reach a supported comparison; some are honestly "Not scored" for rule drift |
| "section 99 of the IBC … after the 2025 amendment" and "… 2019 amendment" | Rejected: "made by Act 6 of 2026, not by …"; no score |
| 390px | No horizontal overflow; one card per section; full-width buttons |
| `browser-a11y-check.mjs` | Passed |

Screenshots in `screenshots/v4/`:
- `act-only-chooser-desktop.jpg` and `act-only-chooser-390.jpg`: the section list.
- `act-only-section-chosen-desktop.jpg`: the comparison after choosing section 194.
- `assistant-recent-followups-desktop.jpg`: recently asked questions and follow-ups.
- `faq-desktop.jpg`: the FAQ page.

Legal validation: UNVERIFIED.
