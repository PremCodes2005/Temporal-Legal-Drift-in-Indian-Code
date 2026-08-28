"""Conservative real-corpus temporal candidate extraction for expert review."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes
from temporal_legal_drift.versioning.models import VersionGraph

from .models import TemporalFact, make_fact_id


DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}[-/]\d{1,2}[-/]\d{4}"
    r"|\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r",?\s+\d{4}"
    r")\b",
    re.IGNORECASE,
)
FACT_CUES = (
    ("retrospective_effect", re.compile(r"\bretrospect", re.IGNORECASE)),
    ("transitional_provision", re.compile(r"\btransition", re.IGNORECASE)),
    ("partial_commencement", re.compile(r"different dates|different provisions|in so far as", re.IGNORECASE)),
    ("deferred_commencement", re.compile(r"defer|appointed date", re.IGNORECASE)),
    ("commencement", re.compile(r"come into force|commencement|w\.e\.f\.", re.IGNORECASE)),
    ("publication", re.compile(r"published|publication|Official Gazette|Gazette of India", re.IGNORECASE)),
    ("enactment_or_assent", re.compile(r"assent|enacted", re.IGNORECASE)),
)


def extract_temporal_candidates(graph: VersionGraph) -> tuple[TemporalFact, ...]:
    candidates: dict[str, TemporalFact] = {}
    for version in graph.versions:
        for line_number, line in enumerate(version.exact_text.splitlines(), start=1):
            date_matches = DATE_PATTERN.findall(line)
            if not date_matches:
                continue
            fact_type = next((name for name, cue in FACT_CUES if cue.search(line)), None)
            if fact_type is None:
                continue
            for raw_date in date_matches:
                parsed = _parse_date(raw_date)
                if parsed is None:
                    continue
                locator = f"{version.evidence.locator}:candidate-line:{line_number}"
                fact_id = make_fact_id(version.version_id, fact_type, raw_date, locator)
                candidates[fact_id] = TemporalFact(
                    fact_id=fact_id,
                    fact_type=fact_type,
                    version_id=version.version_id,
                    date_or_condition=raw_date,
                    effective_date=parsed,
                    source_artifact_id=version.evidence.source_artifact_id,
                    evidence_locator=locator,
                    review_status="unreviewed",
                    uncertainty="machine-extracted temporal candidate; legal meaning and scope not validated",
                )
    return tuple(sorted(candidates.values(), key=lambda item: item.fact_id))


def write_candidates_and_lock(
    facts: tuple[TemporalFact, ...], output_path: Path, lock_path: Path
) -> dict[str, object]:
    document = {
        "schema_version": "1.0.0",
        "status": "machine_extracted_candidates_not_legal_gold",
        "facts": [fact.to_dict() for fact in facts],
    }
    atomic_replace(output_path, canonical_json_bytes(document))
    counts = Counter(fact.fact_type for fact in facts)
    lock = {
        "schema_version": "1.0.0",
        "status": "machine_extracted_candidates_not_legal_gold",
        "candidate_count": len(facts),
        "fact_type_counts": dict(sorted(counts.items())),
        "all_candidates_unreviewed": all(fact.review_status == "unreviewed" for fact in facts),
        "all_candidates_have_evidence": all(
            bool(fact.source_artifact_id and fact.evidence_locator) for fact in facts
        ),
        "approved_candidate_count": sum(fact.review_status == "approved" for fact in facts),
    }
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _parse_date(raw: str) -> date | None:
    cleaned = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", raw.strip(), flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "")
    for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %B %Y"):
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    return None
