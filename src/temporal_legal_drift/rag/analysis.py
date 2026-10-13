"""Stable analysis records and the minimum-facts request (analysis-record-v1).

An analysis ID is derived from everything that determines the result: the contract, question, mode, the facts
applied, the index identity, the graph hash and the active release. The response is stored once under that ID, so
every view and every shared link shows the same evidence and calculations; the browser never recomputes them.
"""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json

ANALYSIS_RECORD_VERSION = "analysis-record-v1"
ANALYSIS_DIR = "data/runtime/analyses"
ANALYSIS_ID = re.compile(r"an_[0-9a-f]{24}")


def analysis_id(identity: dict[str, Any]) -> str:
    return "an_" + sha256(canonical_json_bytes(identity)).hexdigest()[:24]


def store(root: Path, response: dict[str, Any]) -> dict[str, Any]:
    """Write-once: the first stored result for an ID is the one every later view reads."""
    path = root / ANALYSIS_DIR / f"{response['analysis_id']}.json"
    if not path.is_file():
        atomic_write_new(path, canonical_json_bytes({"record_version": ANALYSIS_RECORD_VERSION, "response": response}))
    return load_json(path)["response"]


def load(root: Path, identifier: str) -> dict[str, Any]:
    if not ANALYSIS_ID.fullmatch(identifier):
        raise ValueError("invalid analysis identifier")
    path = root / ANALYSIS_DIR / f"{identifier}.json"
    if not path.is_file():
        raise KeyError("analysis not found")
    return load_json(path)["response"]


# ---------------- facts stated in the question ----------------
from .determinations import WORD_NUMBERS, _value  # noqa: E402

_NUMBER = r"(\d[\d,]*|(?:" + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True)) + r")(?:[\s-](?:" + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True)) + r"))?)"


def facts_from_question(query: str) -> dict[str, Any]:
    """Scenario facts the user already stated, e.g. 'filed on day 12', 'after 18 months', 'a fine of Rs 3,000'."""
    facts: dict[str, Any] = {}
    day = re.search(rf"\bon\s+day\s+{_NUMBER}\b|\b{_NUMBER}\s+days?\s+(?:after|later|have passed|elapsed|late)\b|\bafter\s+{_NUMBER}\s+days?\b", query, re.I)
    if day:
        facts["elapsed_days"] = _value(next(g for g in day.groups() if g))
    month = re.search(rf"\b(?:after\s+)?{_NUMBER}\s+months?\s*(?:after|later|have passed|elapsed|since)?\b", query, re.I)
    if month and re.search(r"\bmonths?\b", month.group(0), re.I) and re.search(r"after|later|passed|elapsed|since", month.group(0) + query[month.end():month.end() + 12], re.I):
        facts["elapsed_months"] = _value(month.group(1))
    amount = re.search(r"(?:Rs\.?|₹|INR)\s*(\d[\d,]*)|(\d[\d,]*)\s*rupees", query, re.I)
    if amount:
        facts["amount"] = int((amount.group(1) or amount.group(2)).replace(",", ""))
    return {key: value for key, value in facts.items() if value is not None}


def merge_scenario(stated: dict[str, Any], question_facts: dict[str, Any], question_date: str | None) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Facts from the form override facts read from the question; the source of each fact is recorded."""
    scenario = dict(stated or {})
    facts = dict(question_facts)
    facts.update(scenario.get("facts") or {})
    sources = {f"facts.{key}": ("form" if key in (scenario.get("facts") or {}) else "question") for key in facts}
    if facts:
        scenario["facts"] = facts
    if not scenario.get("reference_date") and question_date:
        scenario["reference_date"] = question_date
        sources["reference_date"] = "question"
    elif scenario.get("reference_date"):
        sources["reference_date"] = "form"
    for key in ("organization_type", "industry", "jurisdiction", "activity"):
        if scenario.get(key):
            sources[key] = "form"
    if not scenario:
        return None, {}
    for key in ("organization_type", "industry", "jurisdiction", "activity", "reference_date"):
        scenario.setdefault(key, None)
    scenario.setdefault("facts", {})
    return scenario, sources


# ---------------- minimum facts ----------------
UNLOCKS = {"applicability": "which wording applies on your date", "outcome_drift": "whether your answer changes",
           "risk": "conditional compliance risk"}


def scenario_request(determinations: dict[str, Any], fingerprint: dict[str, Any], scenario: dict[str, Any] | None,
                     sources: dict[str, str]) -> dict[str, Any]:
    """Only the facts that unlock something blocked by missing facts (never by missing evidence), deduplicated."""
    components = {"applicability": determinations.get("applicability"), "outcome_drift": fingerprint.get("outcome_drift"),
                  "risk": determinations.get("risk")}
    fields: dict[str, dict[str, Any]] = {}
    for name, component in components.items():
        if not component or (component.get("limit") or {}).get("kind") != "facts":
            continue
        for need in component.get("needs") or []:
            if need.get("kind") == "text":
                continue
            row = fields.setdefault(need["key"], {**need, "unlocks": [], "group": "core"})
            row["unlocks"].append(UNLOCKS[name])
            if name == "risk" and len(row["unlocks"]) == 1:
                row["group"] = "risk"
    for row in fields.values():
        if row["group"] == "risk" and any(u != UNLOCKS["risk"] for u in row["unlocks"]):
            row["group"] = "core"
    current = scenario or {}
    for key, row in fields.items():
        value = (current.get("facts") or {}).get(key[6:]) if key.startswith("facts.") else current.get(key)
        row["value"], row["source"] = value, sources.get(key)
    blocked_by_evidence = [UNLOCKS[name] for name, c in components.items() if c and (c.get("limit") or {}).get("kind") == "evidence"]
    ordered = sorted(fields.values(), key=lambda row: (row["group"] != "core", row["key"] != "reference_date", row["key"]))
    return {"fields": ordered, "facts_in_use": sources,
            "blocked_by_evidence": blocked_by_evidence,
            "explanation": ("Only these facts are needed; anything you leave blank is not assumed."
                            if ordered else "No facts are needed for this question.")
                           + (" Facts cannot fill missing legal evidence for: " + ", ".join(blocked_by_evidence) + "." if blocked_by_evidence else "")}
