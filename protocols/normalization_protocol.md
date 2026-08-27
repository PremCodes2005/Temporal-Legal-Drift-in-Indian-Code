# Phase 2 Parsing and Normalization Protocol

**Status:** Implemented software foundation; legal/data gate not passed.

## Principles

- Preserve immutable raw bytes and their SHA-256 hash.
- Record parser name and version for every normalized document.
- Preserve extracted raw block text alongside normalized text.
- Restrict normalization to documented, deterministic transformations.
- Never infer provision lineage, temporal applicability, materiality, or compliance consequence.
- Quarantine unsupported or malformed inputs rather than silently dropping them.

## Implemented transformations

- UTF-8 decoding with explicit failure on invalid data.
- Unicode NFC normalization.
- CRLF/CR line-ending normalization to LF.
- Space/tab collapsing within normalized block text.
- Structural block classification for headings and paragraphs.

## Formats

- Plain text: deterministic line/block parser.
- HTML: standard-library HTML parser; script/style content excluded and recorded by parser semantics.
- XML: safe subset using `xml.etree.ElementTree`; document types and entity declarations are rejected.
- PDF: optional `pypdf` text extraction; image-only/scanned PDFs fail explicitly and require a later OCR workflow.

## Gate

The Phase 2 gate requires an approved pilot corpus, hand-checked fixtures derived from it, fidelity thresholds, and reconciliation against authoritative evidence. Current tests use synthetic fixtures and establish software behaviour only.

