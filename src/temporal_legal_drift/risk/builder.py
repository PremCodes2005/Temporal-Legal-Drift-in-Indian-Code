"""Versioned conversion of existing scenarios and evidence into risk artifacts."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json
from .engine import evaluate_risk
from .models import ComplianceScenario, ObligationRule


def phase4_preflight(root: Path) -> dict[str, Any]:
    """Check frozen Phase 4 evidence before constructing dependent risk artifacts."""
    silver_path = root / "data/silver/materiality_silver_labels.v1.json"
    silver = load_json(silver_path)
    frozen = load_json(root / "reports/materiality/materiality_silver_frozen.lock.json")
    audit = load_json(root / "data/silver/materiality_disagreement_audit.v2.3.json")
    checks = {
        "frozen_silver_bytes_unchanged": sha256(silver_path.read_bytes()).hexdigest() == frozen["source_file_sha256"],
        "fifty_unique_cases": len(silver["rows"]) == len({r["pair_id"] for r in silver["rows"]}) == 50,
        "audit_reconciles_to_frozen_silver": audit["source_silver_sha256"] == sha256(canonical_json_bytes(silver)).hexdigest(),
        "all_original_disagreements_audited": set(silver["agreement"]["disagreement_pair_ids"]) == {r["pair_id"] for r in audit["rows"]},
        "legal_uncertainty_retained": all(r["gold_status"] == "NOT_GOLD" for r in audit["rows"]),
    }
    if not all(checks.values()):
        raise ValueError(f"Phase 4 preflight failed: {[k for k, v in checks.items() if not v]}")
    return {"checks": checks, "engineering_preflight_passed": True,
            "legal_validation": "UNVERIFIED", "confirmed_extraction_defects": audit["confirmed_alignment_defect_count"],
            "additional_review_required_cases": audit["review_required_count"],
            "cross_source_revalidation_cases": audit["cross_source_revalidation_required_count"]}


def build_risk_artifacts(root: Path) -> dict[str, dict[str, Any]]:
    preflight = phase4_preflight(root)
    input_paths = ["data/scenarios/phase6_scaffolds.v1.json", "data/scenarios/temporal_drift_demo.v1.json",
                   "data/interim/version_graph.v1.json", "data/silver/materiality_silver_labels.v1.json",
                   "data/silver/materiality_disagreement_audit.v2.3.json"]
    scaffolds, demo, graph, _, _ = [load_json(root / path) for path in input_paths]
    if len(scaffolds["scenarios"]) != 13:
        raise ValueError("The v1 risk migration must account for the original 13 scenario scaffolds")
    versions = {v["version_id"]: v for v in graph["versions"]}
    lineages = {v["lineage_id"]: v for v in graph["lineages"]}
    instruments = {v["instrument_id"]: v for v in graph["instruments"]}
    evidence: dict[str, dict[str, Any]] = {}
    benchmark_rows = []
    for old in scaffolds["scenarios"]:
        version = versions[old["post_applicable_version_id"]]
        lineage = lineages[version["lineage_id"]]
        provision = f"{instruments[lineage['instrument_id']]['corpus_entry_id']}:{lineage['canonical_path']}"
        item = _source_evidence(version, "obligation")
        evidence[item["evidence_id"]] = item
        # Empty facts in the source remain empty: expectations concern abstention,
        # not invented legal duties or adverse consequences.
        scenario = ComplianceScenario.from_dict({
            "scenario_id": old["scenario_id"], "organization_type": None, "industry": None,
            "jurisdiction": None, "facts": {}, "reference_date": old["post_reference_date"],
            "applicable_provision": provision, "activity": None,
            "exposure": {"description": None, "amount": None},
        })
        benchmark_rows.append({
            "scenario": scenario.to_dict(), "source_scenario_id": old["scenario_id"],
            "source_pair_id": old["source_pair_id"], "candidate_provision_version": version["version_id"],
            "evidence_ids": [item["evidence_id"]],
            "expected": {"status": "INSUFFICIENT_EVIDENCE", "applicable_law": None,
                         "obligation": None, "consequence": None, "risk_level": None,
                         "risk_flag": None, "urgency": "UNKNOWN"},
            "expectation_basis": "engineering_abstention_contract_not_legal_gold",
            "engineering_rationale": "Source template has no organization, activity, scenario facts or expert outcomes; a legal risk cannot be established.",
            "expert_rationale": None, "expert_validation": "NOT_PERFORMED",
        })
    if len({r["scenario"]["scenario_id"] for r in benchmark_rows}) != 13:
        raise ValueError("Duplicate scenario IDs in migration")

    # A narrow, explicitly conditional execution example from the existing demo.
    # It is separate from the 13 migrated cases and cannot masquerade as gold.
    original = demo["scenarios"][0]
    version = versions[original["post_applicable_version_id"]]
    obligation_evidence = _source_evidence(version, "obligation")
    temporal_evidence = _source_evidence(version, "temporal")
    evidence[obligation_evidence["evidence_id"]] = obligation_evidence
    evidence[temporal_evidence["evidence_id"]] = temporal_evidence
    lineage = lineages[version["lineage_id"]]
    provision = f"{instruments[lineage['instrument_id']]['corpus_entry_id']}:{lineage['canonical_path']}"
    rules, demonstration = [], []
    for when in ("pre", "post"):
        rule = ObligationRule.from_dict({
            "rule_id": f"it19-{when}-conditional-v1", "provision": provision,
            "provision_version": original[f"{when}_applicable_version_id"], "materiality": None,
            "kind": "eligibility", "obligation": "Certificate falls within the signature scope of the supplied section 19(2) wording, with section 19(1) recognition stipulated.",
            "consequence": "Certificate validity is not established by this selected wording; seek recognition or an alternative supported basis. No penalty is inferred.",
            "consequence_severity": "Medium",
            "scope": {"organization_type": "foreign_certifying_authority", "industry": "trust_services", "jurisdiction": "IN", "activity": "certificate_recognition"},
            "conditions": {"recognition_in_force": True, "government_approval": True, "gazette_notification": True, "regulatory_conditions_met": True},
            "reference_dates": [original[f"{when}_reference_date"]],
            "applicability_status": "ASSUMED_FOR_DEMONSTRATION",
            "fact_key": "is_digital_signature" if when == "pre" else "is_notified_electronic_signature",
            "required_value": True, "trigger_fact_key": None, "deadline_days": None, "counting_convention": None,
            "evidence_ids": [obligation_evidence["evidence_id"], temporal_evidence["evidence_id"]],
            "rationale": "Engineer-authored conditional model of the existing Section 19 demo. Pre wording is inferred from the quoted substitution footnote; Medium is operational review priority, not statutory penalty severity. Full historical applicability is unverified.",
        })
        rules.append(rule.to_dict())
        scenario = ComplianceScenario.from_dict({
            "scenario_id": f"{original['scenario_id']}_{when}_risk", **rule.scope,
            "reference_date": original[f"{when}_reference_date"], "applicable_provision": provision,
            "facts": {**rule.conditions, "is_digital_signature": False, "is_notified_electronic_signature": True},
            "exposure": {"description": "Stipulated reliance on one certificate", "amount": None},
        })
        demonstration.append({"scenario": scenario.to_dict(), "expected": {
            "risk_flag": when == "pre", "risk_level": "Medium" if when == "pre" else "None",
            "urgency": "IMMEDIATE" if when == "pre" else "NONE", "status": "PROVISIONAL_ASSESSMENT",
        }, "expectation_basis": "existing_non_gold_demo_plus_proposed_operational_priority",
            "original_facts": original["facts"], "expert_rationale": None})

    # Bind every derived quote to the input graph and immutable PDF bytes.
    for item in evidence.values():
        digest = item["source_sha256"]
        raw = f"data/raw/sha256/{digest[:2]}/{digest}.pdf"
        if not (root / raw).is_file() or sha256((root / raw).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Risk evidence PDF missing or changed: {raw}")
        input_paths.append(raw)
    fingerprints = {path: sha256((root / path).read_bytes()).hexdigest() for path in sorted(set(input_paths))}
    registry = {"schema_version": "1.0.0", "status": "PROPOSED_OPERATIONAL_MODELS_NOT_LEGAL_GOLD",
                "input_sha256": fingerprints, "rules": rules, "evidence": evidence}
    benchmark = {"schema_version": "1.0.0", "dataset_id": "risk-scenarios-v1",
                 "benchmark_kind": "engineering_abstention_benchmark_not_substantive_risk_gold",
                 "scenarios": benchmark_rows, "conditional_demonstrations": demonstration,
                 "input_sha256": fingerprints, "expert_validated_count": 0}
    evaluated = evaluate_benchmark(benchmark, registry)
    return {"preflight": preflight, "registry": registry, "benchmark": benchmark, "evaluation": evaluated}


def _source_evidence(version: dict[str, Any], role: str) -> dict[str, Any]:
    text, anchor = version["exact_text"], version["evidence"]
    if sha256(text.encode()).hexdigest() != anchor["exact_text_sha256"]:
        raise ValueError("Graph evidence text hash does not reconcile")
    return {"evidence_id": f"{version['version_id']}:{role}", "source_id": anchor["source_artifact_id"],
            "source_sha256": anchor["source_sha256"], "locator": anchor["locator"],
            "quote": text, "source_text": text, "text_sha256": anchor["exact_text_sha256"], "role": role}


def evaluate_benchmark(benchmark: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    rules = [ObligationRule.from_dict(r) for r in registry["rules"]]
    rows = []
    for group in ("scenarios", "conditional_demonstrations"):
        for row in benchmark[group]:
            result = evaluate_risk(ComplianceScenario.from_dict(row["scenario"]), rules, registry["evidence"]).to_dict()
            keys = ("status", "risk_level", "risk_flag", "urgency")
            matches = {key: result[key] == row["expected"][key] for key in keys}
            rows.append({"scenario_id": row["scenario"]["scenario_id"], "group": group,
                         "result": result, "expectation_checks": matches})
    return {"schema_version": "1.0.0", "metric_basis": "engineering_expected_behavior_only",
            "registry_sha256": sha256(canonical_json_bytes(registry)).hexdigest(),
            "benchmark_sha256": sha256(canonical_json_bytes(benchmark)).hexdigest(),
            "migrated_scenario_count": len(benchmark["scenarios"]), "conditional_demo_count": len(benchmark["conditional_demonstrations"]),
            "all_expected_behavior_checks_passed": all(all(r["expectation_checks"].values()) for r in rows),
            "legal_accuracy": None, "legal_false_positive_rate": None, "legal_false_negative_rate": None,
            "expert_validated_scenario_count": 0, "research_checkpoint_passed": False, "results": rows}


def write_risk_checkpoint(root: Path) -> dict[str, Any]:
    artifacts = build_risk_artifacts(root)
    outputs = {"reports/risk/phase4_preflight.v1.json": artifacts["preflight"],
               "data/risk/obligation_registry.v1.json": artifacts["registry"],
               "data/risk/compliance_scenarios.v1.json": artifacts["benchmark"],
               "experiments/risk/baseline_results.v1.json": artifacts["evaluation"]}
    payloads = {p: canonical_json_bytes(value) for p, value in outputs.items()}
    checkpoint = {"engineering_checks_passed": artifacts["evaluation"]["all_expected_behavior_checks_passed"],
                  "migrated_scenarios": 13, "conditional_demonstrations": 2,
                  "expert_validation": "NOT_PERFORMED", "research_checkpoint_passed": False,
                  "artifacts": {p: sha256(b).hexdigest() for p, b in payloads.items()}}
    payloads["reports/risk/checkpoint.v1.json"] = canonical_json_bytes(checkpoint)
    # Preflight all collisions before publishing any member of this version.
    for path, payload in payloads.items():
        if (root / path).exists() and (root / path).read_bytes() != payload:
            raise ValueError(f"Versioned risk output already differs: {path}; create a new release")
    for path, payload in payloads.items():
        atomic_write_new(root / path, payload)
    return checkpoint
