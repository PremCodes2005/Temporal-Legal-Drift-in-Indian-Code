"""Conservative discovery and extraction of commencement notifications (policy: docs/methodology/commencement_policy.v1.md).

Publication, commencement and applicability stay separate facts:

* publication  - the Gazette publication date from the listing; not commencement;
* commencement - each date a notification appoints, with the verbatim provisions span; a
  machine reading, stored as ``unreviewed`` TemporalFacts that the applicability resolver
  ignores until a reviewer approves them;
* applicability - never set here; always ``NOT_DETERMINED``.

Anything that cannot be read exactly is recorded as UNRESOLVED with its verbatim text,
never as a guessed date. Different appointed dates for the same provisions are conflicts.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from temporal_legal_drift.applicability.models import TemporalFact, make_fact_id

COMMENCEMENT_POLICY_VERSION = "commencement-policy-v1"
# Listing subjects: a precise commencement phrase and a named enactment (both required).
SUBJECT = re.compile(r"\bappoint(?:s|ment of|ing)?\s+(?:the\s+)?(?:date|day)\b|\bcom(?:es?|ing)\s+into\s+force\b"
                     r"|\bcommencement\s+of\b", re.I)
ENACTMENT = re.compile(r"\b(?:Act|Code|Sanhita|Adhiniyam)\b")
FORCE = re.compile(r"come\s+into\s+force|appoints?\b", re.I)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
ENABLING = re.compile(
    r"conferred by (?P<provision>sub\s*-\s*section\s*\(\d+\)\s*of\s*section\s*\d+[A-Z]?|section\s*\d+[A-Z]?)\s*of\s*the\s*"
    r"(?P<act>[A-Z][A-Za-z ,()&'-]*?(?:Act|Code|Sanhita)),?\s*(?P<year>\d{4})\s*\((?P<number>\d+)\s*of\s*(?P<number_year>\d{4})\)")
APPOINTMENT = re.compile(
    rf"(?:\((?P<label>[a-z]{{1,3}})\)\s*)?the\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(?P<month>{MONTHS}),?\s+"
    rf"(?P<year>\d{{4}}),?\s+as\s+the\s+date\s+on\s+which\s+(?P<provisions>.+?)\s+shall\s+come\s+into\s+force", re.S)
NOTIFICATION = re.compile(r"\b(S\.O\.\s*\d+\s*\(E\))")


def is_commencement_subject(subject: str) -> bool:
    return bool(SUBJECT.search(subject) and ENACTMENT.search(subject))


def extract_commencement(document: dict[str, Any], *, official_id: str, sha256: str,
                         published: str | None) -> dict[str, Any] | None:
    """Facts from the quarantined (evidence) document; None when it is not a commencement notification."""
    pages = [(block.get("source_anchor"), str(block.get("normalized_text", ""))) for block in document.get("blocks", [])]
    if not any("come into force" in " ".join(text.split()) for _, text in pages):
        return None
    version_id = f"monitored:{official_id}@{sha256[:12]}"
    facts: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    if published:
        facts.append(TemporalFact(make_fact_id(version_id, "publication", published, "listing:PublishDate"), "publication",
                                  version_id, f"Gazette publication {published}", date.fromisoformat(published), sha256,
                                  "listing:PublishDate", "unreviewed",
                                  uncertainty="publication is not commencement").to_dict())
    for anchor, text in pages:
        flat = re.sub(r"\s*-\s*(?=section)", "-", " ".join(text.split()))
        enabling = ENABLING.search(flat)
        notification = NOTIFICATION.search(flat)
        matched = 0
        for match in APPOINTMENT.finditer(flat):
            matched += 1
            day = datetime.strptime(f"{match['day']} {match['month']} {match['year']}", "%d %B %Y").date()
            provisions = match["provisions"].strip()
            whole_act = re.fullmatch(r"(?:all the provisions of )?the said Act|the said Act", provisions) is not None
            locator = f"{anchor}:clause:{match['label'] or matched}"
            conditions = {"provisions": provisions, "policy": COMMENCEMENT_POLICY_VERSION}
            if enabling:
                conditions.update(act=f"{enabling['act']}, {enabling['year']}", act_number=f"{enabling['number']} of {enabling['number_year']}",
                                  enabling_provision=" ".join(enabling["provision"].split()))
            if notification:
                conditions["notification"] = notification.group(1)
            facts.append(TemporalFact(
                make_fact_id(version_id, "commencement", day.isoformat(), locator),
                "commencement" if whole_act else "partial_commencement", version_id, match.group(0), day, sha256, locator,
                "unreviewed", uncertainty=None if enabling else "enabling Act not identified in the text",
                conditions=conditions).to_dict())
        if not matched and FORCE.search(flat) and "come into force" in flat:
            unresolved.append({"source_anchor": anchor, "reason": "COMMENCEMENT_WORDING_NOT_PARSED",
                               "verbatim": flat[max(0, flat.find("come into force") - 300): flat.find("come into force") + 40]})
    return {
        "policy": COMMENCEMENT_POLICY_VERSION, "official_id": official_id, "sha256": sha256,
        "status": "MACHINE_EXTRACTED_PENDING_REVIEW" if any(f["fact_type"] != "publication" for f in facts) else "UNRESOLVED",
        "facts": facts, "unresolved": unresolved,
        "applicability": {"status": "NOT_DETERMINED",
                          "reason": "commencement is not applicability; a reviewer must approve facts before any legal-effect claim"},
        "legal_effect_claimed": False, "review_required_before": ["legal_effect", "applicability", "graph_update"],
    }


def find_conflicts(new: dict[str, Any], existing: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Same Act and provisions appointed for a different date by another notification."""
    def keyed(record: dict[str, Any]) -> dict[tuple[str, str], str]:
        return {(f["conditions"].get("act_number", ""), " ".join(f["conditions"].get("provisions", "").split()).lower()): f["effective_date"]
                for f in record.get("facts", []) if f["fact_type"] != "publication" and f["conditions"].get("act_number")}

    mine = keyed(new)
    conflicts = []
    for other in existing:
        if other.get("sha256") == new.get("sha256"):
            continue
        for key, day in keyed(other).items():
            if key in mine and mine[key] != day:
                conflicts.append({"official_id": other["official_id"], "act_number": key[0], "provisions": key[1],
                                  "this_date": mine[key], "other_date": day})
    return conflicts
