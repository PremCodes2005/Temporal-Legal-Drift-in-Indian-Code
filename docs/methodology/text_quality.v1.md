# Text-quality gate for monitored PDFs (`text-quality-v1`)

Implementation: `src/temporal_legal_drift/parsing/text_quality.py`. Tests: `tests/unit/test_text_quality.py` (real Gazette PDFs, a correct-Unicode control, and the full frozen corpus).

## Why

- **Wrong code points:** a real e-Gazette notification (CG-DL-E-12102026-277080) extracted its Hindi with glyphs mapped to the wrong characters: `अजधसूचना` for अधिसूचना, `जिकास` for विकास. The previous check, a Latin-script heuristic, rated it `READABLE`.
- **Legacy-font mojibake:** another notification (CG-DL-E-10102026-277026) set its Hindi in a legacy KrutiDev-style font, so it extracted as Latin mojibake (`vf/klwpuk`).
- **Correct PDFs are lossy too:** a PDF that Chrome printed from *correct* Unicode Hindi still lost vowel signs in pypdf 6.16.2 (`अ धसूचना`). Hindi from a PDF text layer therefore cannot be verified, whatever the PDF.

## Rule (per page, per line)

| Reason | Rule |
| --- | --- |
| `DEVANAGARI_TEXT_LAYER_UNVERIFIED` | Any line containing Devanagari. |
| `LEGACY_FONT_MOJIBAKE` | At least 30% of a line's alphabetic tokens carry a KrutiDev marker, or the line is letter-spaced (at least 8 alphabetic tokens, at least half single letters) *and* has a marker. |
| `UNRECOGNISED_ON_MOJIBAKE_PAGE` | Once a page has 3 or more mojibake lines, any other line where under half of its 3+-letter words are in the English vocabulary. |

- **KrutiDev markers:**
  - characters `¼ ½ Ù Å Ø ª ñ ~ } ``;
  - patterns `letter=`/`letter@`, `digit@letter`, lowercase-`Z`, and token-final lowercase-`A`;
  - KrutiDev function words `ds dh dk dks esa ls gS vkSj fd rFkk ij ;g bl`.
- **Vocabulary:** `parsing/data/english_vocabulary.v1.txt` has 18,400 words, SHA-256 `20213bda…cbb0`, checked on load.
  - It is built by `build_english_vocabulary` from the 100 tracked corpus PDFs, using only pages with no flagged line, and words seen at least twice.
  - A rebuild reproduced it byte for byte.

## What happens to withheld lines

- **Blanking:** each withheld line is blanked, not deleted, so line numbers used as provenance stay exact.
- **Record:** the withheld lines, with their text, SHA-256 and reason, go to `data/monitoring/quarantine/<sha>.<parser>.text-quality-v1.json` (write-once).
- **Never used:** they are never extracted, indexed or cited.
- **Search overlay:** chunks carry `quarantined_lines_on_page`. An answer citing such a page carries the warning "source text partly withheld", which raises `SOURCE_TEXT_UNRELIABLE` in comparisons.
- **Fully unreliable documents** (more than 8% odd tokens after quarantine) are extracted for review only. Their index stage is `WITHHELD`, they are never served, and they go to `REVIEW_REQUIRED`.
- **Earlier documents:** the gate is applied whenever the overlay is rebuilt, so documents processed before it existed are cleaned too.

## Calibration (2026-10-13)

| Set | Lines | Withheld | Notes |
| --- | --- | --- | --- |
| Frozen corpus (100 docs) | 245,761 | 278 (140 mojibake, 123 page-rule, 15 Devanagari) | Every withheld line reviewed: KrutiDev mastheads or the known IT 2008 OCR noise. English kept, including `Profit/Loss`, `g/m2` and `“Court” means`. |
| CG-DL-E-12102026-277080 | 40 | 17 (Devanagari) | All the Hindi lines on page 1; the English notification page is intact. |
| CG-DL-E-10102026-277026 | 115 | 61 (21 mojibake, 28 page-rule, 12 Devanagari) | All English notification text kept. |
| Correct-Unicode control | 12 | 9 (Devanagari) | English kept. |

## Limits

- Hindi is never used from the text layer. Using it would need verified OCR or a verified extractor.
- The vocabulary rule can withhold rare English lines on a mojibake page. That is the conservative choice; the lines remain in the quarantine record for review.
- The gate applies to the monitoring pipeline. The frozen base corpus index is unchanged; its KrutiDev mastheads remain in it, as before.
