# Phase B checkpoint — extraction v2.2, layout furniture, OCR candidate

Date: 2026-10-12. Base `58c9868` (release v0.2.1). Engineering results only; **legal/research gate UNVERIFIED**.

## Changes

| Defect / gap | Root cause | Fix (at source) | Regression test |
| --- | --- | --- | --- |
| 340 compound clauses abstained as `UNKNOWN` | One event per numbered clause | Bounded splitter (`_compound_parts`). It splits only when all of these hold: the header has no directive and ends in `,—`; items are in strict `(a)/(i)` sequence at line starts; a quoted payload is closed before the next item; each item has exactly one directive. Each part keeps its own page/line anchor and verbatim lines, plus `compound_part` (header, clause line, clause SHA-256). | split, three ambiguity cases, enumerated lines inside a payload, Wild Life s.50 verbatim |
| `"shall respectively be substituted"` mispaired first/last quotes (8 v2.1 events with a resolved operation; 1 v3 transition) | Directive pattern missed "respectively" | Counted as a directive; any part containing "respectively" is `UNKNOWN` | ambiguity case |
| Plural/sub-clause unit insertions had no operand (e.g. MV s.74(ii)) | Unit pattern knew only `section/sub-section/clause/proviso` | Adds plurals, `sub-clause`, `Explanation` | MV s.74 |
| Gazette headers, `IndiaCode` watermark and margin notes inside operands | Normalized text interleaves them | `parsing/layout.py` classifies pypdf 6.16.2 text runs by coordinates and freezes them in `data/processed/layout/v1/gazette_furniture.json` (37 Acts, 5,971 runs, `c18db9ee…`). The extractor parses the body with matching lines removed and keeps `evidence_text` verbatim. `layout_cleaning` lists each removed line with page, line and zone, and adds the reason `layout_furniture_removed`. | Competition 6A verbatim pages 6–7; mismatched-PDF refusal |

Layout rules (source-specific, recorded in the artifact):
- A top-90-pt line counts as a header only if it reads like one (`GAZETTE OF INDIA` or a lone page number).
- `IndiaCode` is the watermark.
- Left margin: x < body-left − 15 pt. Right margin: x ≥ 0.8 × page width.
- A margin run needs at least two alphanumeric characters, and runs without a position are ignored.
- A line is removed only if its whole text equals a classified run on the same page.

Arbitration 31A and Competition 6A now parse to clean statutory text. For example, 6A loses 9 lines: two "15 of 1992.", the four-line note "Insertion of a / new section / 6A. / Open offers, etc.", the watermark, and the page-7 header. Two operands (CPC 1999 p.3, Patents 2002 p.24) still contain a header that pypdf reports without usable coordinates. They keep `operand_contains_page_furniture`.

## Extraction v1 → v2.1 → v2.2

| | v2.1 (`91a453ad…`) | v2.2 (`5b1a09ab…`) |
| --- | --- | --- |
| Events | 864 | 1,150 (444 split parts from 158 clauses) |
| UNKNOWN | 340 | 232 |
| SUBSTITUTE / INSERT / OMIT | 244 / 219 / 41 | 457 / 370 / 79 |
| MODIFY | 10 | 2 (margin "Amendment of section …" cues no longer drive operation) |
| Operation-resolution coverage | 60.65% | 79.83% |
| Old/new wording coverage | 32.99% | 51.65% |
| Target-identification coverage | 89.81% | 88.43% (split parts whose header names no section) |
| Unresolved records | 1,508 | 1,953 |
| `operand_contains_page_furniture` | 14 | 2 |
| `layout_furniture_removed` (review) | — | 130 |
| `source_text_unreliable` | 35 | 35 |

Coverage rose from source-backed splitting and parsing, not from a target. Every new event has a verbatim `evidence_text` with its own page/line, and is reproducible: a second build was accepted as byte-identical. Graph v3 still rebuilds byte-identically from v2.1 under the modified code.

## 2008 IT Amendment

- The PDF is 20 scanned JPEG pages (~150 dpi) with an "Adobe Acrobat 8.1 Paper Capture" text layer.
- A Tesseract 5.5.3 (`eng`) re-OCR at native resolution is frozen as `data/processed/ocr/v1/it-amendment-act-2008.json` (`dc8f935c…`, deterministic). It records the per-page image SHA-256, dpi, mean confidence (91.51 average; page range 82.1–94.3) and the fraction of low-confidence words.
- Of the 6+-letter words, 93.2% appear in the consolidated IT Act vocabulary, versus 39.9% for the embedded layer. 8-gram overlap with the consolidated Act is 40.0% versus 3.7%.
- **Status: `OCR_CANDIDATE_MANUAL_VERIFICATION_REQUIRED`.** The OCR text is not used for extraction or transitions, and the 35 events stay `source_text_unreliable`.
- **Promotion needs:** a reviewer to check the OCR against the page images clause by clause; then a new normalized-document version with transformation `tesseract_ocr`, and a new extraction version.

## Short-fragment corroboration policy (applied in graph v4)

Nine of the ten v3 short-fragment matches are SUBSTITUTE and one is INSERT. Each fragment occurs exactly once in the consolidated provision.

**Policy:** an after-fragment of less than 15 normalized characters gives strong cross-source corroboration only if one of these holds:
- **INSERT:** the instruction's "after the words …" anchor sits immediately before the fragment in the consolidated text.
- **SUBSTITUTE / REPLACE:** the fragment occurs exactly once, and the old wording no longer appears in that consolidated provision.

Under this policy 6 of the 10 qualify. The other 4 ("section 164", "ten years" ×2, "or culture") fall to a weak status.

## Gates

- Engineering:
  - 126 tests ran; the 1 failure is the Phase 11 checksum check, which is expected until a new release is cut.
  - `validate-contract` exit 0.
  - `check-gates`: Phases 0–10 pass; Phase 11 waits on the release.
- Legal/research: **UNVERIFIED**. No extraction, OCR or layout result is legal validation.

## Limits

- 232 events stay `UNKNOWN`. These include nested `(A)/(i)` numbering, "respectively" pairs, and clauses whose header names no section.
- The layout rules are tuned to Gazette PDFs. Margin notes that pypdf merges into body lines would not be detected; transitions therefore also require cross-source corroboration (Phase C).
- No OCR text has been manually verified.
