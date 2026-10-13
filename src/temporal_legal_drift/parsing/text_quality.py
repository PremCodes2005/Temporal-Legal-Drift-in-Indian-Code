"""Line-level quarantine of PDF text that cannot be trusted as legal evidence.

Two failure modes seen in real Gazette PDFs (docs/methodology/text_quality.v1.md):

* Devanagari from a PDF text layer. pypdf drops or misplaces vowel signs even for a
  correctly encoded PDF, and some Gazette fonts map glyphs to wrong code points. No
  available extractor reproduces Hindi faithfully, so every Devanagari line is withheld.
* Legacy (KrutiDev-style) font mojibake, where Hindi comes out as Latin letters
  ("vf/klwpuk" for अधिसूचना). It is detected from marker characters and patterns; once a
  page shows three such lines, any further line without mostly English vocabulary words
  is withheld as well.

Quarantined lines are blanked, not deleted, so line numbers used as provenance stay exact.
"""

from __future__ import annotations

import re
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

TEXT_QUALITY_VERSION = "text-quality-v1"
VOCABULARY_PATH = Path(__file__).with_name("data") / "english_vocabulary.v1.txt"
VOCABULARY_SHA256 = "20213bdae485da66b0f6cb722dd3f0c920353acb8a7719c8762714e14aa6cbb0"

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# KrutiDev renders matras/conjuncts as these characters and letter shapes; English legal prose does not use them.
LEGACY_MARK = re.compile(
    r"[¼½ÙÅØªñ~}`]|[A-Za-z][=@][A-Za-z0-9]|[0-9]@[A-Za-z]|[a-z]Z(?:[a-z.]|$)|[a-z]A$"
    r"|^(?:ds|dh|dk|dks|esa|ls|gS|vkSj|fd|rFkk|ij|;g|bl)$")
WORD = re.compile(r"[A-Za-z]{3,}")
MOJIBAKE_PAGE_LINES = 3


def is_legacy_mojibake(line: str) -> bool:
    tokens = [token for token in line.split() if re.search(r"[A-Za-z]", token)]
    legacy = [token for token in tokens if LEGACY_MARK.search(token)]
    if not legacy:
        return False
    letter_spaced = len(tokens) >= 8 and sum(bool(re.fullmatch(r"[A-Za-z][.,;:]?", t)) for t in tokens) / len(tokens) >= 0.5
    return letter_spaced or len(legacy) / len(tokens) >= 0.3


def line_reason(line: str) -> str | None:
    """Reason a line is untrustworthy on its own, without page context."""
    if DEVANAGARI.search(line):
        return "DEVANAGARI_TEXT_LAYER_UNVERIFIED"
    if is_legacy_mojibake(line):
        return "LEGACY_FONT_MOJIBAKE"
    return None


@lru_cache(maxsize=1)
def english_vocabulary() -> frozenset[str]:
    payload = VOCABULARY_PATH.read_bytes()
    if sha256(payload).hexdigest() != VOCABULARY_SHA256:
        raise ValueError(f"{VOCABULARY_PATH.name} does not match its recorded SHA-256")
    return frozenset(payload.decode("utf-8").split())


def page_quarantine(text: str, vocabulary: frozenset[str] | None = None) -> dict[int, str]:
    """Map line index -> reason for every line of one page that must be withheld."""
    vocabulary = english_vocabulary() if vocabulary is None else vocabulary
    lines = text.split("\n")
    reasons = {index: reason for index, line in enumerate(lines) if (reason := line_reason(line))}
    if sum(reason == "LEGACY_FONT_MOJIBAKE" for reason in reasons.values()) >= MOJIBAKE_PAGE_LINES:
        for index, line in enumerate(lines):
            words = [word.lower() for word in WORD.findall(line)]
            if index not in reasons and words and sum(word in vocabulary for word in words) / len(words) < 0.5:
                reasons[index] = "UNRECOGNISED_ON_MOJIBAKE_PAGE"
    return reasons


def quarantine_document(document: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (evidence document with withheld lines blanked, quarantine report)."""
    blocks, withheld = [], []
    for block in document.get("blocks", []):
        text = str(block.get("normalized_text", ""))
        reasons = page_quarantine(text)
        lines = text.split("\n")
        for index, reason in sorted(reasons.items()):
            withheld.append({"block_id": block.get("block_id"), "source_anchor": block.get("source_anchor"),
                             "line": index + 1, "reason": reason, "text": lines[index],
                             "text_sha256": sha256(lines[index].encode("utf-8")).hexdigest()})
        kept = "\n".join("" if index in reasons else line for index, line in enumerate(lines))
        blocks.append({**block, "normalized_text": kept, "quarantined_lines": len(reasons)})
    evidence = {**document, "blocks": blocks, "text_quality_version": TEXT_QUALITY_VERSION}
    counts: dict[str, int] = {}
    for item in withheld:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    report = {"version": TEXT_QUALITY_VERSION, "status": "PARTIALLY_QUARANTINED" if withheld else "NOTHING_WITHHELD",
              "withheld_lines": len(withheld), "by_reason": counts, "lines": withheld,
              "legal_evidence_use": "withheld lines are never indexed, extracted or cited; review against the official PDF"}
    return evidence, report


def build_english_vocabulary(page_texts: list[str]) -> list[str]:
    """Words (3+ letters, seen at least twice) from pages that contain no flagged line.

    Rebuild: parse every tracked data/corpus/pdfs/*.pdf with PdfParser (pypdf 6.16.2) and pass each
    block's normalized_text; the result must reproduce english_vocabulary.v1.txt byte for byte.
    """
    counts: dict[str, int] = {}
    for text in page_texts:
        if any(line_reason(line) for line in text.split("\n")):
            continue
        for word in WORD.findall(text):
            counts[word.lower()] = counts.get(word.lower(), 0) + 1
    return sorted(word for word, count in counts.items() if count >= 2)
