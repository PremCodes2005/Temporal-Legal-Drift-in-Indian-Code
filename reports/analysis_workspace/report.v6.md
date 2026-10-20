# Latest five discoveries, evidence cards, rule weights, review screen retired

Decision: ADR 0023. Running app on port 8799 (new backend), real Chrome, 2026-10-20. Screenshots in `screenshots/v6/`.

| Feature | Checked | Result |
|---|---|---|
| Latest discoveries | Panel on the real ledger | "The latest 4 records (all that exist)"; legend: newly discovered document 1, possible amendment awaiting review 3, verified amendment 0; each source with its last successful check |
| | New-record alert | With one record unknown to the browser, a focus refresh showed "New in the monitored sources: Appointment of the date 15th October 2026 for MSMED Amendment Act 2026. Not yet reviewed." No message on a first visit |
| | Read marks | "Mark all as read" then reload: the toggle reads "Latest discoveries" with no count |
| Evidence cards | Drift explanation, IBC s.99 | 3 cards; clicking E1 in the clause sources focuses card E1; marked "ten" in E3 and "twenty-one" in E1 from the stored spans; "Derived, not a verbatim quote" on E3; Open PDF (page 98) and Official record links |
| Score calculation | IBC s.99 | No full-clause cards; a "Scored texts" table with sources and hashes; "View detailed clause comparison" opens `#comparison/<same id>`; "Why we chose these rule-field weights" lists the four tiers (25; 15 each; 10 each; 5 each) |
| Review screen | `#review` | "Case trace & review is no longer part of this app", with a link to the assistant; no sidebar entry |
| Phones | 390px | No horizontal overflow on Drift explanation or the discoveries panel; `browser-a11y-check.mjs` passed at 320–480px |

## Not established

- Whether the monitored sources cover every India Code record (they do not claim to).
- Whether any discovered document changes the law; none is reviewed, and no review can yet verify an amendment.
- Whether any rule or combined weighting is more correct; there are no expert labels.
- Legal accuracy.
- The PDF links open the cited page; exact regions are not available.
