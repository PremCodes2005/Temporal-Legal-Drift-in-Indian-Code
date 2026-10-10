"""Deterministic obligations and consequences; no drift or similarity dependency."""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from typing import Any

from temporal_legal_drift.jsonio import canonical_json_bytes
from .models import ComplianceRisk, ComplianceScenario, ObligationRule, iso_date


def evaluate_risk(
    scenario: ComplianceScenario,
    rules: list[ObligationRule],
    evidence_registry: dict[str, dict[str, Any]],
) -> ComplianceRisk:
    """Evaluate a single provision at a supplied date; preserve uncertainty as data.

    Evidence and rules are supplied by the server registry, not the HTTP caller.
    Outcomes are conditional on the declared operational interpretation. Even a
    resolved applicability input does not establish expert legal validation.
    """
    scenario = ComplianceScenario.from_dict(scenario.to_dict())
    rules = [ObligationRule.from_dict(rule.to_dict()) for rule in rules]
    trace: list[str] = []
    uncertainty: list[str] = []
    used_evidence: list[dict[str, Any]] = []
    rule: ObligationRule | None = None
    risk_id = "risk_" + sha256(canonical_json_bytes({
        "scenario": scenario.to_dict(), "rules": [r.to_dict() for r in rules],
        "evidence": evidence_registry, "baseline": "compliance-risk-baseline-v1",
    })).hexdigest()[:24]

    def result(status: str, flag: bool | None = None, level: str | None = None,
               urgency: str = "UNKNOWN", consequence: str | None = None) -> ComplianceRisk:
        return ComplianceRisk(
            risk_id, scenario.scenario_id, rule.provision_version if rule else None,
            rule.materiality if rule else None, rule.obligation if rule else None,
            consequence, rule.consequence_severity if flag and rule else ("None" if flag is False else None),
            urgency, list(dict.fromkeys(uncertainty)), level, used_evidence,
            flag is None or flag is True or bool(uncertainty), status, flag, list(trace),
            rule.rule_id if rule else None,
        )

    candidates = [r for r in rules if r.provision == scenario.applicable_provision]
    if not candidates:
        uncertainty.append("no_supported_obligation_model_for_provision")
        return result("INSUFFICIENT_EVIDENCE")
    dated = [r for r in candidates if scenario.reference_date in r.reference_dates]
    if len(dated) != 1:
        uncertainty.append("applicability_conflict" if len(dated) > 1 else "no_applicability_evidence_for_reference_date")
        return result("REVIEW_REQUIRED" if dated else "INSUFFICIENT_EVIDENCE")
    rule = dated[0]
    if rule.applicability_status == "UNRESOLVED":
        uncertainty.append("temporal_applicability_unresolved")
        return result("INSUFFICIENT_EVIDENCE")

    for evidence_id in rule.evidence_ids:
        evidence = evidence_registry.get(evidence_id)
        if not _valid_evidence(evidence) or evidence["evidence_id"] != evidence_id:
            uncertainty.append(f"missing_or_invalid_evidence:{evidence_id}")
            return result("INSUFFICIENT_EVIDENCE")
        used_evidence.append({key: value for key, value in evidence.items() if key != "source_text"})
    if not {"obligation", "temporal"}.issubset({e["role"] for e in used_evidence}):
        uncertainty.append("obligation_and_temporal_evidence_required")
        return result("INSUFFICIENT_EVIDENCE")
    trace.append(f"Selected {rule.provision_version} for {scenario.reference_date}: {rule.applicability_status}.")
    uncertainty.append("operational_rule_interpretation_not_expert_validated")
    if rule.applicability_status == "ASSUMED_FOR_DEMONSTRATION":
        uncertainty.append("historical_applicability_stipulated_for_demonstration")
    if rule.materiality is None:
        uncertainty.append("materiality_unassessed_risk_uses_obligation_and_consequence")

    missing_scope = [key for key in rule.scope if getattr(scenario, key) is None]
    if missing_scope:
        uncertainty.extend(f"missing_scenario_scope:{key}" for key in missing_scope)
        return result("INSUFFICIENT_EVIDENCE")
    for key, expected in rule.scope.items():
        if expected != "*" and getattr(scenario, key) != expected:
            trace.append(f"Scenario {key} falls outside this rule's stated scope.")
            return result("NOT_APPLICABLE", False, "None", "NONE", "No consequence assessed under this selected rule.")
    for key, expected in rule.conditions.items():
        actual = scenario.facts.get(key)
        if actual is None:
            uncertainty.append(f"missing_applicability_fact:{key}")
            return result("INSUFFICIENT_EVIDENCE")
        if type(actual) is not type(expected):
            uncertainty.append(f"wrong_fact_type:{key}")
            return result("INSUFFICIENT_EVIDENCE")
        if actual != expected:
            uncertainty.append(f"applicability_condition_not_established:{key}")
            return result("REVIEW_REQUIRED")
    trace.append("Scenario scope and explicit applicability conditions match.")
    if rule.fact_key not in scenario.facts:
        uncertainty.append(f"missing_obligation_fact:{rule.fact_key}")
        return result("INSUFFICIENT_EVIDENCE")
    actual = scenario.facts[rule.fact_key]
    if rule.kind == "deadline":
        try:
            trigger = iso_date(scenario.facts.get(str(rule.trigger_fact_key)))
            reference = iso_date(scenario.reference_date)
            due = trigger + timedelta(days=rule.deadline_days)
            completed = iso_date(actual) if actual is not None else None
        except (ValueError, OverflowError):
            uncertainty.append("missing_or_invalid_deadline_dates")
            return result("INSUFFICIENT_EVIDENCE")
        if trigger > reference or completed is not None and (completed > reference or completed < trigger):
            uncertainty.append("inconsistent_scenario_dates")
            return result("REVIEW_REQUIRED")
        trace.append(f"Due {due.isoformat()}; calendar days excluding trigger; boundary is inclusive.")
        # A null completion date explicitly means not completed; an absent key is unknown.
        breach = completed > due if completed else reference > due
        if not breach and completed is None:
            soon = (due - reference).days <= 7
            trace.append("Deadline has not passed; no current breach detected.")
            return result("PROVISIONAL_ASSESSMENT", False, "Low" if soon else "None", "SOON" if soon else "ROUTINE", "Obligation remains pending before its deadline.")
    else:
        if actual is None or type(actual) is not type(rule.required_value):
            uncertainty.append(f"missing_or_invalid_fact_type:{rule.fact_key}")
            return result("INSUFFICIENT_EVIDENCE")
        breach = actual == rule.required_value if rule.kind == "prohibition" else actual != rule.required_value
    if breach:
        trace.append("Scenario does not satisfy the modelled obligation; consequence severity determines risk.")
        return result("PROVISIONAL_ASSESSMENT", True, rule.consequence_severity, "IMMEDIATE", rule.consequence)
    trace.append("Scenario satisfies the selected obligation under the supplied facts.")
    return result("PROVISIONAL_ASSESSMENT", False, "None", "NONE", "No adverse consequence detected under the selected obligation.")


def _valid_evidence(value: dict[str, Any]) -> bool:
    if not isinstance(value, dict):
        return False
    required = ("evidence_id", "source_id", "source_sha256", "locator", "quote", "source_text", "text_sha256", "role")
    if any(not isinstance(value.get(k), str) or not value[k].strip() for k in required):
        return False
    if value["role"] not in {"obligation", "temporal", "consequence"}:
        return False
    return (value["quote"] in value["source_text"]
            and sha256(value["source_text"].encode()).hexdigest() == value["text_sha256"]
            and len(value["source_sha256"]) == 64
            and all(c in "0123456789abcdef" for c in value["source_sha256"]))
