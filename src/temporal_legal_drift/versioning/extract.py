"""Conservative section extraction that preserves ambiguity for review."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256


SECTION_START = re.compile(
    r"^\s*(?P<number>\d{1,3}[A-Z]{0,3})\.\s+"
    r"(?P<title>.{1,200}?)\s*\.\s*[—–]{1,2}\s*(?P<body>.*)$"
)
AMENDING_CLAUSE_START = re.compile(
    r"^\s*(?P<number>\d{1,3})\.\s*(?P<body>.*(?:principal\s*A\w+|Information\s*Technology\s*Act).*)$",
    re.IGNORECASE,
)
TARGET_SECTION = re.compile(r"\bsection(?:s)?\s*(\d{1,3}[A-Z]{0,3})\b", re.IGNORECASE)
OPERATION_CUES = (
    ("substitution", re.compile(r"\bsubstitut(?:e|ed|ion|ing)\b", re.IGNORECASE)),
    ("insertion", re.compile(r"\bins(?:ert|en)(?:ed|ion|ing)?\b", re.IGNORECASE)),
    ("omission", re.compile(r"\bomi(?:tt|n)(?:ed|ing|ion)?\b", re.IGNORECASE)),
    ("repeal", re.compile(r"\brepeal(?:ed|ing)?\b", re.IGNORECASE)),
    ("renumbering", re.compile(r"\brenumber(?:ed|ing)?\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class ExtractedProvision:
    number: str
    title: str
    exact_text: str
    block_id: str
    locator: str

    @property
    def text_hash(self) -> str:
        return sha256(self.exact_text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExtractedAmendment:
    target_number: str
    operation: str
    provision: ExtractedProvision


def extract_provisions(document: dict[str, object]) -> tuple[tuple[ExtractedProvision, ...], tuple[dict[str, object], ...]]:
    candidates: list[ExtractedProvision] = []
    current: dict[str, object] | None = None
    for raw_block in document.get("blocks", []):  # type: ignore[assignment]
        block = dict(raw_block)
        block_id = str(block.get("block_id", ""))
        anchor = str(block.get("source_anchor", ""))
        for line_number, line in enumerate(str(block.get("normalized_text", "")).splitlines(), start=1):
            match = SECTION_START.match(line)
            if match:
                if current is not None:
                    candidates.append(_finish(current))
                current = {
                    "number": match.group("number"),
                    "title": match.group("title").strip(),
                    "lines": [line.strip()],
                    "block_id": block_id,
                    "locator": f"{anchor}:line:{line_number}",
                }
            elif current is not None:
                current["lines"].append(line.strip())  # type: ignore[union-attr]
    if current is not None:
        candidates.append(_finish(current))

    grouped: dict[str, list[ExtractedProvision]] = {}
    for item in candidates:
        grouped.setdefault(item.number, []).append(item)
    selected: list[ExtractedProvision] = []
    unresolved: list[dict[str, object]] = []
    for number, items in sorted(grouped.items(), key=lambda item: _section_sort_key(item[0])):
        chosen = max(items, key=lambda item: len(item.exact_text))
        selected.append(chosen)
        if len(items) > 1:
            unresolved.append(
                {
                    "reason_code": "duplicate_section_candidates",
                    "provision_number": number,
                    "selected_locator": chosen.locator,
                    "candidate_locators": [item.locator for item in items],
                    "requires_review": True,
                }
            )
    return tuple(selected), tuple(unresolved)


def extract_amendments(provisions: tuple[ExtractedProvision, ...]) -> tuple[ExtractedAmendment, ...]:
    results: list[ExtractedAmendment] = []
    for provision in provisions:
        targets = TARGET_SECTION.findall(provision.exact_text)
        operations = [name for name, pattern in OPERATION_CUES if pattern.search(provision.exact_text)]
        operation = operations[0] if len(operations) == 1 else "complex_or_unresolved"
        for target in dict.fromkeys(targets):
            results.append(ExtractedAmendment(target, operation, provision))
    return tuple(results)


def extract_amending_clauses(document: dict[str, object]) -> tuple[ExtractedProvision, ...]:
    """Extract numbered amending clauses even when a legacy PDF lacks em-dash headings."""
    results: list[ExtractedProvision] = []
    current: dict[str, object] | None = None
    for raw_block in document.get("blocks", []):  # type: ignore[assignment]
        block = dict(raw_block)
        block_id = str(block.get("block_id", ""))
        anchor = str(block.get("source_anchor", ""))
        for line_number, line in enumerate(str(block.get("normalized_text", "")).splitlines(), start=1):
            match = AMENDING_CLAUSE_START.match(line)
            if match:
                if current is not None:
                    results.append(_finish(current))
                current = {
                    "number": match.group("number"),
                    "title": f"Amending clause {match.group('number')}",
                    "lines": [line.strip()],
                    "block_id": block_id,
                    "locator": f"{anchor}:line:{line_number}",
                }
            elif current is not None:
                current["lines"].append(line.strip())  # type: ignore[union-attr]
    if current is not None:
        results.append(_finish(current))
    return tuple(results)


def _finish(value: dict[str, object]) -> ExtractedProvision:
    return ExtractedProvision(
        number=str(value["number"]),
        title=str(value["title"]),
        exact_text="\n".join(line for line in value["lines"] if line).strip(),  # type: ignore[union-attr]
        block_id=str(value["block_id"]),
        locator=str(value["locator"]),
    )


def _section_sort_key(number: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d+)([A-Z]*)", number)
    return (int(match.group(1)), match.group(2)) if match else (10**9, number)
