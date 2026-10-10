"""Strict data contracts for the deterministic compliance-risk baseline."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


LEVELS = ("High", "Medium", "Low", "None")


def iso_date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Date must use YYYY-MM-DD")
    return date.fromisoformat(value)


@dataclass(frozen=True)
class ComplianceScenario:
    scenario_id: str
    organization_type: str | None
    industry: str | None
    jurisdiction: str | None
    facts: dict[str, Any]
    reference_date: str
    applicable_provision: str | None
    activity: str | None
    exposure: dict[str, Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ComplianceScenario":
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("Scenario must contain exactly the ComplianceScenario fields; drift scores are not inputs")
        for name in ("scenario_id", "reference_date"):
            if not isinstance(value[name], str) or not value[name].strip():
                raise ValueError(f"Missing scenario {name}")
        iso_date(value["reference_date"])
        for name in ("organization_type", "industry", "jurisdiction", "applicable_provision", "activity"):
            if value[name] is not None and (not isinstance(value[name], str) or not value[name].strip()):
                raise ValueError(f"{name} must be nonempty text or null")
        facts = value["facts"]
        if not isinstance(facts, dict) or any(
            not isinstance(key, str) or not key.strip()
            or not isinstance(item, (str, int, float, bool, type(None)))
            or isinstance(item, float) and not math.isfinite(item)
            for key, item in facts.items()
        ):
            raise ValueError("Facts must map names to finite scalar values or null")
        exposure = value["exposure"]
        if not isinstance(exposure, dict) or set(exposure) != {"description", "amount"}:
            raise ValueError("Exposure requires description and amount (both may be null)")
        if exposure["description"] is not None and not isinstance(exposure["description"], str):
            raise ValueError("Exposure description must be text or null")
        amount = exposure["amount"]
        if amount is not None and (type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0):
            raise ValueError("Exposure amount must be a finite non-negative number or null")
        return cls(**{**value, "facts": dict(facts), "exposure": dict(exposure)})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ObligationRule:
    rule_id: str
    provision: str
    provision_version: str
    materiality: str | None
    kind: str
    obligation: str
    consequence: str
    consequence_severity: str
    scope: dict[str, str]
    conditions: dict[str, Any]
    reference_dates: list[str]
    applicability_status: str
    fact_key: str
    required_value: Any
    trigger_fact_key: str | None
    deadline_days: int | None
    counting_convention: str | None
    evidence_ids: list[str]
    rationale: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ObligationRule":
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("Obligation rule fields do not match the versioned contract")
        for key in ("rule_id", "provision", "provision_version", "obligation", "consequence", "fact_key", "rationale"):
            if not isinstance(value[key], str) or not value[key].strip():
                raise ValueError(f"Rule requires {key}")
        if value["kind"] not in {"deadline", "requirement", "prohibition", "eligibility"}:
            raise ValueError("Unsupported deterministic obligation kind")
        if value["materiality"] is not None and value["materiality"] not in LEVELS:
            raise ValueError("Materiality must be a canonical class or null")
        if value["consequence_severity"] not in {"Low", "Medium", "High"}:
            raise ValueError("Consequence severity must be Low, Medium or High")
        if value["applicability_status"] not in {"RESOLVED", "ASSUMED_FOR_DEMONSTRATION", "UNRESOLVED"}:
            raise ValueError("Unknown applicability status")
        if not isinstance(value["reference_dates"], list) or not value["reference_dates"]:
            raise ValueError("Rule requires explicit supported reference dates")
        for day in value["reference_dates"]:
            iso_date(day)
        scope = value["scope"]
        if not isinstance(scope, dict) or set(scope) != {"organization_type", "industry", "jurisdiction", "activity"}:
            raise ValueError("Rule scope must specify organization, industry, jurisdiction and activity")
        if any(not isinstance(item, str) or not item.strip() for item in scope.values()):
            raise ValueError("Scope values must be text (or explicit '*')")
        if not isinstance(value["conditions"], dict) or any(
            not isinstance(k, str) or not k or type(v) not in (bool, str, int, float)
            or isinstance(v, float) and not math.isfinite(v)
            for k, v in value["conditions"].items()
        ):
            raise ValueError("Rule conditions must be named scalar values")
        if not isinstance(value["evidence_ids"], list) or not value["evidence_ids"] or any(
            not isinstance(item, str) or not item for item in value["evidence_ids"]
        ):
            raise ValueError("Rule requires evidence references")
        if len(set(value["evidence_ids"])) != len(value["evidence_ids"]):
            raise ValueError("Evidence IDs must be unique")
        if value["kind"] == "deadline":
            if type(value["deadline_days"]) is not int or value["deadline_days"] < 0:
                raise ValueError("Deadline requires non-negative integer days")
            if not isinstance(value["trigger_fact_key"], str) or not value["trigger_fact_key"]:
                raise ValueError("Deadline requires a trigger fact")
            if value["counting_convention"] != "calendar_days_exclusive_trigger":
                raise ValueError("Only explicit calendar-day counting is supported")
        elif value["required_value"] is None or type(value["required_value"]) not in (bool, str, int, float):
            raise ValueError("Non-deadline rules require a scalar comparison value")
        elif isinstance(value["required_value"], float) and not math.isfinite(value["required_value"]):
            raise ValueError("Rule comparison value must be finite")
        return cls(**value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComplianceRisk:
    risk_id: str
    scenario_id: str
    provision_version: str | None
    materiality: str | None
    obligation: str | None
    consequence: str | None
    severity: str | None
    urgency: str
    uncertainty: list[str]
    risk_level: str | None
    evidence: list[dict[str, Any]]
    escalation_required: bool
    status: str
    risk_flag: bool | None
    reasoning_trace: list[str]
    rule_id: str | None
    baseline_version: str = "compliance-risk-baseline-v1"
    legal_validation: str = "UNVERIFIED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
