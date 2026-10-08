"""Conservative generalised extraction from normalized Indian amending Acts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from hashlib import sha256

from .models import AmendmentEvent, UnresolvedAmendment


CLAUSE_START = re.compile(r"^\s*(?P<number>\d{1,3}[A-Z]?)\.\s+(?P<body>.+)$")
ACT_REFERENCE = re.compile(
    r"(?:the\s+)?(?P<name>[A-Z][A-Za-z()'’\-\s]{2,100}?(?:Act|Code))\s*,\s*(?P<year>(?:18|19|20)\d{2})",
)
IN_SECTION = re.compile(r"\b(?:in|of)\s+section\s+(?P<number>\d{1,3}[A-Z]{0,3})\b", re.I)
SECTION_REFERENCE = re.compile(r"\bsection\s+(?P<number>\d{1,3}[A-Z]{0,3})\b", re.I)
QUOTED = re.compile(r'"(?P<straight>[^"\n]{1,4000})"|“(?P<curly>[^”]{1,4000})”', re.S)
DATE_TEXT = re.compile(
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:\s+day\s+of)?\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s*,?\s*(?P<year>\d{4})",
    re.I,
)
ASSENT_DATE = re.compile(r"\[(?P<value>[^\]]{6,40}\d{4})\.?\]")
PUBLICATION_DATE = re.compile(r"New\s+Delhi\s*,?\s+the\s+(?P<value>.{6,40}?\d{4})", re.I)
DEEMED_EFFECTIVE = re.compile(
    r"(?:deemed\s+to\s+have\s+come|shall\s+be\s+deemed\s+to\s+have\s+come)\s+into\s+force\s+on\s+the\s+"
    r"(?P<value>[^.]{4,60}?\d{4})",
    re.I,
)
EXPLICIT_EFFECTIVE = re.compile(r"shall\s+come\s+into\s+force\s+on\s+the\s+(?P<value>[^.]{4,60}?\d{4})", re.I)
COMMENCEMENT_CUE = re.compile(r"come\s+into\s+force|commencement", re.I)
AMENDMENT_CUE = re.compile(
    r"\b(insert(?:ed|ion)?|substitut(?:e|ed|ion)|omit(?:ted|ission)?|repeal(?:ed)?|"
    r"renumber(?:ed)?|replac(?:e|ed)|amendment\s+of)\b",
    re.I,
)
OPERATION_PATTERNS = (
    ("RENUMBER", re.compile(r"\brenumber(?:ed|ing)?\b", re.I)),
    ("REPLACE", re.compile(r"\breplac(?:e|ed|ing|ement)\b", re.I)),
    ("SUBSTITUTE", re.compile(r"\bsubstitut(?:e|ed|ing|ion)\b", re.I)),
    ("INSERT", re.compile(r"\binsert(?:ed|ing|ion)?\b", re.I)),
    ("OMIT", re.compile(r"\bomit(?:ted|ting|ission)?\b", re.I)),
    ("REPEAL", re.compile(r"\brepeal(?:ed|ing)?\b", re.I)),
)


@dataclass(frozen=True)
class Clause:
    number: str
    text: str
    block_id: str
    page: int | None
    line: int | None


class GeneralisedAmendmentExtractor:
    def extract(
        self,
        document: dict[str, object],
        *,
        source_document: str,
        source_sha256: str,
        amending_act: str,
    ) -> tuple[tuple[AmendmentEvent, ...], tuple[UnresolvedAmendment, ...]]:
        clauses = _segment_clauses(document)
        all_text = "\n".join(
            str(block.get("normalized_text", ""))
            for block in document.get("blocks", []) if isinstance(block, dict)
        )
        defaults = _preamble_targets(all_text[:5000])
        assent_date = _extract_named_date(ASSENT_DATE, all_text[:3000])
        publication_date = _extract_named_date(PUBLICATION_DATE, all_text[:4000])
        effective_date = _effective_date(all_text[:6000])
        commencement_unclear = bool(COMMENCEMENT_CUE.search(all_text[:6000])) and effective_date is None

        events: list[AmendmentEvent] = []
        unresolved: list[UnresolvedAmendment] = []
        current_principal = defaults[0] if len(defaults) == 1 else None
        candidate_clauses = [clause for clause in clauses if AMENDMENT_CUE.search(clause.text)]
        for clause in candidate_clauses:
            explicit_targets = _act_references(clause.text[:800])
            principal_act = explicit_targets[0] if explicit_targets else current_principal
            if explicit_targets:
                current_principal = explicit_targets[0]
            elif "principal act" not in clause.text.lower() and len(defaults) == 1:
                principal_act = defaults[0]

            target, target_ambiguous = _target_provision(clause.text)
            operation, operation_ambiguous = _operation(clause.text)
            old_text, new_text = _wording(clause.text, operation)
            amendment_id = _event_id(
                source_document, clause.page, clause.line, target, operation, clause.text
            )
            confidence = _confidence(
                principal_act, target, operation, old_text, new_text, effective_date
            )
            event = AmendmentEvent(
                amendment_id=amendment_id,
                amending_act=amending_act,
                principal_act=principal_act,
                target_provision=target,
                operation=operation,
                old_text=old_text,
                new_text=new_text,
                effective_date=effective_date,
                assent_date=assent_date,
                publication_date=publication_date,
                source_document=source_document,
                source_page=clause.page,
                source_line=clause.line,
                source_sha256=source_sha256,
                evidence_text=clause.text,
                confidence=confidence,
            )
            events.append(event)
            reasons: list[tuple[str, str]] = []
            if principal_act is None or target is None:
                reasons.append(("target_not_found", "principal Act or affected provision was not resolved"))
            if target_ambiguous:
                reasons.append(("ambiguous_section", "multiple candidate target sections were found"))
            if operation == "UNKNOWN" or operation_ambiguous:
                reasons.append(("unclear_operation", "operation cues were absent or conflicting"))
            if operation in {"SUBSTITUTE", "REPLACE", "MODIFY", "REPEAL", "RENUMBER"} and old_text is None:
                reasons.append(("missing_old_text", "old wording was not explicit in the amendment clause"))
            if operation in {"INSERT", "SUBSTITUTE", "REPLACE", "MODIFY", "RENUMBER"} and new_text is None:
                reasons.append(("missing_new_text", "new wording was not explicit in the amendment clause"))
            if commencement_unclear:
                reasons.append(("commencement_unclear", "commencement depends on notification or could not be dated"))
            unresolved.extend(
                _unresolved(source_document, event, clause, code, detail)
                for code, detail in dict.fromkeys(reasons)
            )

        if not candidate_clauses:
            evidence = all_text[:1500].strip() or "No normalized text was available."
            unresolved.append(UnresolvedAmendment(
                unresolved_id=_unresolved_id(source_document, None, "parsing_failure", evidence),
                source_document=source_document,
                reason_code="parsing_failure",
                evidence_text=evidence,
                source_page=1 if all_text else None,
                source_line=1 if all_text else None,
                amendment_id=None,
                detail="no amendment clause with a supported cue was segmented",
            ))
        return tuple(events), tuple(unresolved)


def _segment_clauses(document: dict[str, object]) -> list[Clause]:
    results: list[Clause] = []
    current: dict[str, object] | None = None
    for raw_block in document.get("blocks", []):
        if not isinstance(raw_block, dict):
            continue
        anchor = str(raw_block.get("source_anchor", ""))
        page_match = re.search(r"page:(\d+)", anchor)
        page = int(page_match.group(1)) if page_match else None
        block_id = str(raw_block.get("block_id", ""))
        for line_number, raw_line in enumerate(str(raw_block.get("normalized_text", "")).splitlines(), 1):
            line = raw_line.strip()
            match = CLAUSE_START.match(line)
            if match and not re.search(r"GAZETTE|PART\s+II|SEC\.", match.group("body"), re.I):
                if current:
                    results.append(_finish_clause(current))
                current = {
                    "number": match.group("number"),
                    "lines": [line],
                    "block_id": block_id,
                    "page": page,
                    "line": line_number,
                }
            elif current and line:
                current["lines"].append(line)  # type: ignore[union-attr]
    if current:
        results.append(_finish_clause(current))
    return results


def _finish_clause(value: dict[str, object]) -> Clause:
    return Clause(
        str(value["number"]),
        "\n".join(value["lines"]).strip(),  # type: ignore[arg-type]
        str(value["block_id"]),
        value["page"] if isinstance(value["page"], int) else None,
        value["line"] if isinstance(value["line"], int) else None,
    )


def _preamble_targets(text: str) -> list[str]:
    preamble = re.split(r"BE\s+it\s+enacted", text, maxsplit=1, flags=re.I)[0]
    return _act_references(preamble)


def _act_references(text: str) -> list[str]:
    values = []
    for match in ACT_REFERENCE.finditer(text):
        name = " ".join(match.group("name").split())
        name = re.sub(r"^(?:An\s+Act\s+(?:further\s+)?to\s+amend\s+the\s+)", "", name, flags=re.I)
        name = re.sub(r"^(?:In|of)\s+(?:the\s+)?", "", name, flags=re.I)
        value = f"{name}, {match.group('year')}"
        if value not in values:
            values.append(value)
    return values


def _target_provision(text: str) -> tuple[str | None, bool]:
    renumbered = re.search(
        r"\bsection\s+(?P<number>\d{1,3}[A-Z]{0,3})\s+shall\s+be\s+re-?numbered\b",
        text[:1200],
        re.I,
    )
    if renumbered:
        return f"section:{renumbered.group('number').upper()}", False
    direct = IN_SECTION.search(text[:1200])
    if direct:
        return f"section:{direct.group('number').upper()}", False
    targets = list(dict.fromkeys(match.group("number").upper() for match in SECTION_REFERENCE.finditer(text[:1200])))
    if len(targets) == 1:
        return f"section:{targets[0]}", False
    return (None, len(targets) > 1)


def _operation(text: str) -> tuple[str, bool]:
    matches = [name for name, pattern in OPERATION_PATTERNS if pattern.search(text)]
    unique = list(dict.fromkeys(matches))
    if len(unique) == 1:
        return unique[0], False
    if not unique and re.search(r"\bamendment\s+of\b", text, re.I):
        return "MODIFY", False
    return "UNKNOWN", len(unique) > 1


def _wording(text: str, operation: str) -> tuple[str | None, str | None]:
    quotes = [
        " ".join((match.group("straight") or match.group("curly") or "").split())
        for match in QUOTED.finditer(text)
    ]
    quotes = [value for value in quotes if value]
    if operation in {"SUBSTITUTE", "REPLACE"} and len(quotes) >= 2:
        return quotes[0], quotes[-1]
    if operation == "INSERT" and quotes:
        return None, quotes[-1]
    if operation == "OMIT" and quotes:
        return quotes[0], ""
    if operation == "RENUMBER":
        match = re.search(
            r"(?:section|sub-section)\s*\(?([0-9A-Za-z]+)\)?\s+shall\s+be\s+re-?numbered\s+as\s+"
            r"(?:section|sub-section)\s*\(?([0-9A-Za-z]+)\)?",
            text,
            re.I,
        )
        if match:
            return match.group(1), match.group(2)
    if operation == "REPEAL":
        return quotes[0] if quotes else None, ""
    return None, None


def _effective_date(text: str) -> str | None:
    for pattern in (DEEMED_EFFECTIVE, EXPLICIT_EFFECTIVE):
        match = pattern.search(text)
        if match:
            return _parse_date(match.group("value"))
    return None


def _extract_named_date(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return _parse_date(match.group("value")) if match else None


def _parse_date(value: str) -> str | None:
    match = DATE_TEXT.search(value)
    if not match:
        return None
    months = {
        name.lower(): number for number, name in enumerate(
            ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1
        )
    }
    try:
        return date(int(match.group("year")), months[match.group("month").lower()], int(match.group("day"))).isoformat()
    except ValueError:
        return None


def _confidence(
    principal: str | None,
    target: str | None,
    operation: str,
    old_text: str | None,
    new_text: str | None,
    effective_date: str | None,
) -> float:
    value = 0.15
    value += 0.20 if principal else 0
    value += 0.20 if target else 0
    value += 0.20 if operation != "UNKNOWN" else 0
    value += 0.15 if old_text is not None or new_text is not None else 0
    value += 0.10 if effective_date else 0
    return round(min(value, 1.0), 2)


def _event_id(source: str, page: int | None, line: int | None, target: str | None, operation: str, text: str) -> str:
    payload = f"{source}\n{page}\n{line}\n{target}\n{operation}\n{text}"
    return f"amendment_{sha256(payload.encode()).hexdigest()[:24]}"


def _unresolved(
    source: str,
    event: AmendmentEvent,
    clause: Clause,
    code: str,
    detail: str,
) -> UnresolvedAmendment:
    return UnresolvedAmendment(
        _unresolved_id(source, event.amendment_id, code, clause.text),
        source,
        code,
        clause.text,
        clause.page,
        clause.line,
        event.amendment_id,
        detail,
    )


def _unresolved_id(source: str, amendment_id: str | None, code: str, evidence: str) -> str:
    payload = f"{source}\n{amendment_id}\n{code}\n{evidence}"
    return f"unresolved_{sha256(payload.encode()).hexdigest()[:24]}"
