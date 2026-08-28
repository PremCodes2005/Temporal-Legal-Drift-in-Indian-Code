"""Create evidence-linked scenario scaffolds without inventing legal outcomes."""

from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes


def build_scenario_scaffolds(
    workload: dict[str, object],
    cross_validation: dict[str, object],
    coverage: dict[str, object],
) -> dict[str, object]:
    tasks = workload.get("tasks")
    results = cross_validation.get("results")
    required_categories = coverage.get("required_categories")
    if not isinstance(tasks, list) or not isinstance(results, list):
        raise ValueError("Scenario scaffolding requires workload tasks and cross-validation results")
    if not isinstance(required_categories, list) or not required_categories:
        raise ValueError("Scenario coverage plan requires categories")
    task_by_event = {
        str(task["amendment_event_id"]): task
        for task in tasks
        if isinstance(task, dict) and task.get("amendment_event_id")
    }

    scaffolds: list[dict[str, object]] = []
    for result in results:
        if not isinstance(result, dict) or result.get("status") != "corroborated":
            continue
        task = task_by_event.get(str(result.get("amendment_event_id")))
        if task is None:
            continue
        evidence = result.get("evidence")
        if not isinstance(evidence, dict):
            raise ValueError("Corroborated cross-validation result requires evidence")
        effective_date_raw = evidence.get("expected_effective_date")
        effective_date = date.fromisoformat(str(effective_date_raw))
        source_pair_id = str(task["pair_id"])
        scaffolds.append(
            {
                "scenario_id": _stable_id("scenario", source_pair_id),
                "scenario_schema_version": "1.0.0",
                "source_pair_id": source_pair_id,
                "facts": [],
                "legal_question": None,
                "pre_reference_date": (effective_date - timedelta(days=1)).isoformat(),
                "post_reference_date": effective_date.isoformat(),
                "pre_applicable_version_id": None,
                "post_applicable_version_id": task.get("after_version_id"),
                "expected_answer": None,
                "expected_compliance_consequence": None,
                "expected_change": None,
                "supporting_legal_evidence": {
                    "amendment_event_id": task.get("amendment_event_id"),
                    "cross_validation_id": result.get("validation_id"),
                    "evidence": evidence,
                },
                "expert_rationale": None,
                "category_labels": [],
                "fact_control_status": "not_authored",
                "review_status": "authoring_and_validation_required",
            }
        )
    return {
        "schema_version": "1.0.0",
        "status": "scenario_scaffolds_not_compliance_gold",
        "input_fingerprints": {
            "annotation_workload_sha256": sha256(
                canonical_json_bytes(workload)
            ).hexdigest(),
            "cross_validation_sha256": sha256(
                canonical_json_bytes(cross_validation)
            ).hexdigest(),
            "coverage_config_sha256": sha256(canonical_json_bytes(coverage)).hexdigest(),
        },
        "coverage_plan": required_categories,
        "scenarios": sorted(scaffolds, key=lambda item: str(item["scenario_id"])),
    }


def write_scenarios_and_lock(
    document: dict[str, object], output_path: Path, lock_path: Path
) -> dict[str, object]:
    payload = canonical_json_bytes(document)
    scenarios = document.get("scenarios")
    coverage = document.get("coverage_plan")
    fingerprints = document.get("input_fingerprints")
    if (
        not isinstance(scenarios, list)
        or not isinstance(coverage, list)
        or not isinstance(fingerprints, dict)
    ):
        raise ValueError("Scenario document requires scenarios and coverage plan")
    assigned_categories = {
        label
        for scenario in scenarios
        if isinstance(scenario, dict)
        for label in scenario.get("category_labels", [])
    }
    lock = {
        "schema_version": "1.0.0",
        "status": "scenario_scaffolds_not_compliance_gold",
        "scenario_document_sha256": sha256(payload).hexdigest(),
        "input_fingerprints": fingerprints,
        "scenario_count": len(scenarios),
        "unique_scenario_count": len(
            {str(item.get("scenario_id")) for item in scenarios if isinstance(item, dict)}
        ),
        "all_scaffolds_evidence_linked": all(
            isinstance(item, dict) and bool(item.get("supporting_legal_evidence"))
            for item in scenarios
        ),
        "no_expected_answers_invented": all(
            isinstance(item, dict)
            and item.get("expected_answer") is None
            and item.get("expected_compliance_consequence") is None
            and item.get("expected_change") is None
            for item in scenarios
        ),
        "coverage_categories_required": coverage,
        "coverage_categories_assigned": sorted(assigned_categories),
        "coverage_complete": set(coverage).issubset(assigned_categories),
        "expert_validated_scenario_count": 0,
        "research_gate_passed": False,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{sha256(value.encode('utf-8')).hexdigest()[:24]}"
