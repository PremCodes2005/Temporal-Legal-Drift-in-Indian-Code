# ADR 0012: Withhold untrustworthy PDF text lines before any evidence use

Status: **accepted 2026-10-13**. See `docs/methodology/text_quality.v1.md`.

## Decision

- **Devanagari:** every line from a PDF text layer that contains Devanagari is withheld. Even a correctly encoded PDF loses vowel signs in pypdf, so "detect only the bad Hindi" cannot be done reliably.
- **Legacy-font mojibake** is withheld by marker rules plus a page-level vocabulary rule.
- **Blanking:** withheld lines are blanked, preserving line provenance, and recorded write-once.
- **Whole documents:** a document that is unreliable as a whole is never indexed.

## Rejected

- Orthographic validity checks on Devanagari: mis-mapped words such as `अजधसूचना` are orthographically valid.
- Page-level quarantine: it would discard the authoritative English text on mixed pages.
- An unversioned keyword list for the page rule: it removed real statutory lines such as `“Court” means`.

## Consequences

- Hindi Gazette text is not used until there is a verified OCR or extraction path.
- English evidence from bilingual pages survives.
- The calibration counts are pinned in tests, so any change in behaviour forces a line-by-line re-review.
