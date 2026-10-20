# ADR 0023: Latest five discoveries, evidence cards, rule-weight rationale, review screen retired

Status: **accepted 2026-10-20**. Report: `reports/analysis_workspace/report.v6.md`. Handoff note: `docs/handoff.md` (2026-10-20).

## Decision

- **source-notifications-v2:**
  - Records are keyed by official id plus content hash. The newest five are shown, with older ones behind a disclosure, and a short list is never padded.
  - There are three categories (newly discovered document; possible amendment awaiting review; verified amendment, which is always empty for now).
  - The browser re-reads the stored ledger every 5 minutes and on focus. It never starts a source check, and the 24-hour source rule is unchanged.
  - A record this browser has not seen raises one quiet in-app message and counts as unread. Read marks and known records persist in this browser.
  - When a refresh fails or the browser is offline, the last list stays visible with a note.
- **Drift explanation evidence:**
  - Each stored evidence item is a source card: instrument, role, provision, page and line, verbatim or derived, a text-quality warning, an expandable excerpt, and Open PDF and Official record links.
  - On the two compared sides, the changed words are marked from the stored comparison spans.
  - Evidence ids in the explanation focus their card. The page says that PDF links open the page only.
- **Score calculation:**
  - The full clause cards are replaced by a compact table of the scored texts (sources, evidence ids, text hashes) and a "View detailed clause comparison" link to the same analysis. The legacy diagnostic no longer repeats the clauses either.
  - The worked rule and combined calculations stay.
- **Rule-field weights:** the stated rationale and a held-out sensitivity check are shown under "Why we chose these rule-field weights", separate from the combined-indicator weights. The weights and the rule-drift contract are unchanged.
- **Case trace & review:** removed from the interface. The backend routes and all records stay (reasons in the handoff note).

## Rejected

- **Deleting the run and review endpoints:** they back tests and the hash-chained review ledger that discoveries read.
- **Changing the rule weights:** with no expert labels, there is no evidence that another weighting is better.
