"""Phase 4 temporal facts, queries, and determinations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from hashlib import sha256
from typing import Mapping


TEMPORAL_FACT_TYPES = frozenset(
    {
        "publication",
        "enactment_or_assent",
        "commencement",
        "applicability",
        "legal_effect",
        "retrospective_effect",
        "transitional_provision",
        "deferred_commencement",
        "partial_commencement",
    }
)
REVIEW_STATUSES = frozenset({"unreviewed", "approved", "rejected", "contested"})


@dataclass(frozen=True)
class TemporalFact:
    fact_id: str
    fact_type: str
    version_id: str
    date_or_condition: str
    effective_date: date | None
    source_artifact_id: str
    evidence_locator: str
    review_status: str
    uncertainty: str | None = None
    conditions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fact_type not in TEMPORAL_FACT_TYPES:
            raise ValueError(f"Unsupported temporal fact type: {self.fact_type}")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError(f"Unsupported temporal fact review status: {self.review_status}")
        if not self.source_artifact_id or not self.evidence_locator:
            raise ValueError("Temporal facts require authoritative evidence references")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["effective_date"] = self.effective_date.isoformat() if self.effective_date else None
        value["conditions"] = dict(sorted(self.conditions.items()))
        return value

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "TemporalFact":
        raw_date = value.get("effective_date")
        return cls(
            fact_id=str(value["fact_id"]),
            fact_type=str(value["fact_type"]),
            version_id=str(value["version_id"]),
            date_or_condition=str(value["date_or_condition"]),
            effective_date=date.fromisoformat(str(raw_date)) if raw_date else None,
            source_artifact_id=str(value["source_artifact_id"]),
            evidence_locator=str(value["evidence_locator"]),
            review_status=str(value["review_status"]),
            uncertainty=str(value["uncertainty"]) if value.get("uncertainty") else None,
            conditions=dict(value.get("conditions", {})),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class ApplicabilityQuery:
    scenario_id: str
    lineage_id: str
    reference_date: date
    attributes: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicabilityDetermination:
    determination_id: str
    scenario_id: str
    reference_date: str
    lineage_id: str
    status: str
    governing_version_id: str | None
    supporting_fact_ids: tuple[str, ...]
    reasoning_trace: tuple[str, ...]
    escalation_reasons: tuple[str, ...]
    review_requirement: str = "qualified_legal_review_required"
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "determination_id": self.determination_id,
            "scenario_id": self.scenario_id,
            "reference_date": self.reference_date,
            "lineage_id": self.lineage_id,
            "status": self.status,
            "governing_version_id": self.governing_version_id,
            "supporting_fact_ids": list(self.supporting_fact_ids),
            "reasoning_trace": list(self.reasoning_trace),
            "escalation_reasons": list(self.escalation_reasons),
            "review_requirement": self.review_requirement,
        }


def make_fact_id(version_id: str, fact_type: str, date_or_condition: str, locator: str) -> str:
    payload = "\n".join([version_id, fact_type, date_or_condition, locator]).encode("utf-8")
    return f"tmp_{sha256(payload).hexdigest()[:24]}"


def make_determination_id(query: ApplicabilityQuery) -> str:
    attributes = "\n".join(f"{key}={value}" for key, value in sorted(query.attributes.items()))
    payload = "\n".join(
        [query.scenario_id, query.lineage_id, query.reference_date.isoformat(), attributes]
    ).encode("utf-8")
    return f"app_{sha256(payload).hexdigest()[:24]}"
