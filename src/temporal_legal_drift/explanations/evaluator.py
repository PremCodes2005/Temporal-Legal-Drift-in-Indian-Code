"""Automated explanation-support checks that never assert legal correctness."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes
from temporal_legal_drift.versioning.models import VersionGraph


def evaluate_explanation_support(
    explanation: dict[str, object],
    expected: dict[str, object],
    allowed_evidence_ids: set[str],
    required_fields: tuple[str, ...],
) -> dict[str, object]:
    if set(explanation) != set(required_fields):
        missing = set(required_fields) - set(explanation)
        extra = set(explanation) - set(required_fields)
        if extra:
            raise ValueError(f"Unexpected explanation fields: {sorted(extra)}")
    else:
        missing = set()
    present = sum(
        field in explanation and explanation[field] not in {None, "", ()}
        for field in required_fields
        if field not in {"materiality_dimensions", "citations"}
    )
    list_fields_present = sum(
        isinstance(explanation.get(field), list) and bool(explanation.get(field))
        for field in ("materiality_dimensions", "citations")
    )
    completeness = (present + list_fields_present) / len(required_fields)

    evidence_values = [
        explanation.get("before_evidence_id"),
        explanation.get("after_evidence_id"),
    ]
    non_null_evidence = [str(value) for value in evidence_values if value is not None]
    evidence_resolves = len(non_null_evidence) == 2 and all(
        value in allowed_evidence_ids for value in non_null_evidence
    )
    citations = explanation.get("citations")
    if not isinstance(citations, list) or not all(isinstance(item, str) for item in citations):
        raise ValueError("Explanation citations must be a list of strings")
    citation_precision = (
        sum(citation in allowed_evidence_ids for citation in citations) / len(citations)
        if citations
        else None
    )
    expected_version = expected.get("version_id")
    expected_date = expected.get("applicable_date")
    version_alignment = (
        explanation.get("version_id") == expected_version if expected_version is not None else None
    )
    temporal_alignment = (
        explanation.get("applicable_date") == expected_date if expected_date is not None else None
    )
    expected_consequence = expected.get("compliance_consequence")
    conclusion_correct = (
        explanation.get("compliance_consequence") == expected_consequence
        if expected_consequence is not None
        else None
    )
    support_failures = [
        value is False
        for value in (version_alignment, temporal_alignment)
    ] + [not evidence_resolves, citation_precision is not None and citation_precision < 1]
    explanation_drift = (
        bool(any(support_failures)) if conclusion_correct is True else None
    )
    return {
        "field_completeness": completeness,
        "evidence_reference_resolution": evidence_resolves,
        "version_alignment": version_alignment,
        "temporal_alignment": temporal_alignment,
        "citation_precision": citation_precision,
        "uncertainty_presence": bool(explanation.get("uncertainty_or_escalation")),
        "explanation_drift": explanation_drift,
        "expert_evaluation_required": True,
        "legal_correctness": None,
    }


def build_explanation_evaluation_plan(
    llm_plan: dict[str, object],
    scenarios: dict[str, object],
    workload: dict[str, object],
    graph: VersionGraph,
    rubric: dict[str, object],
) -> dict[str, object]:
    runs = llm_plan.get("runs")
    scenario_items = scenarios.get("scenarios")
    required_fields = rubric.get("required_explanation_fields")
    if not isinstance(runs, list) or not isinstance(scenario_items, list):
        raise ValueError("Explanation planning requires Phase 9 runs and scenarios")
    if not isinstance(required_fields, list) or not required_fields:
        raise ValueError("Explanation rubric requires fields")
    if rubric.get("llm_as_judge_is_sole_legal_evaluator") is not False:
        raise ValueError("LLM-as-judge cannot be the sole legal evaluator")

    scenario_by_id = {
        str(item["scenario_id"]): item
        for item in scenario_items
        if isinstance(item, dict) and item.get("scenario_id")
    }
    version_by_id = {version.version_id: version for version in graph.versions}
    lineage_by_id = {lineage.lineage_id: lineage for lineage in graph.lineages}
    instrument_by_id = {instrument.instrument_id: instrument for instrument in graph.instruments}
    event_by_id = {
        event.amendment_event_id: event for event in graph.amendment_events
    }
    version_ids = set(version_by_id)
    records: list[dict[str, object]] = []
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("Phase 9 runs must be objects")
        scenario = scenario_by_id.get(str(run.get("scenario_id")))
        if scenario is None:
            raise ValueError("Phase 9 run references missing scenario")
        version_id = scenario.get("post_applicable_version_id")
        raw_response = run.get("raw_response")
        base_record = {
            "evaluation_id": _stable_id("explain_eval", str(run["run_id"])),
            "run_id": run["run_id"],
            "scenario_id": run["scenario_id"],
            "condition": run["condition"],
            "known_post_version_exists": version_id in version_ids,
            "explanation": None,
            "automated_support_evaluation": None,
            "expert_evaluation": None,
            "status": "blocked_no_model_explanation_or_gold",
        }
        if isinstance(raw_response, dict):
            version = version_by_id.get(str(version_id))
            lineage = lineage_by_id.get(version.lineage_id) if version is not None else None
            instrument = (
                instrument_by_id.get(lineage.instrument_id) if lineage is not None else None
            )
            evidence = scenario.get("supporting_legal_evidence")
            amendment_id = evidence.get("amendment_event_id") if isinstance(evidence, dict) else None
            event = event_by_id.get(str(amendment_id))
            amendment_evidence_id = (
                event.evidence.block_id if event is not None else None
            )
            after_evidence_id = version.evidence.block_id if version is not None else None
            condition = str(run.get("condition"))
            applicable_date = (
                scenario.get("pre_reference_date")
                if condition == "pre_amendment_legal_context"
                else scenario.get("post_reference_date")
                if condition
                in {
                    "post_amendment_legal_context",
                    "both_versions_plus_reference_date",
                    "reconstructed_temporally_applicable_context",
                }
                else None
            )
            cited_version = raw_response.get("cited_version_id")
            explanation = {
                "legal_instrument": instrument.title if instrument is not None else None,
                "provision_path": lineage.canonical_path if lineage is not None else None,
                "applicable_date": applicable_date,
                "version_id": cited_version,
                "before_evidence_id": amendment_evidence_id,
                "after_evidence_id": after_evidence_id,
                "amendment_operation": event.operation if event is not None else None,
                "materiality_dimensions": [],
                "materiality_level": None,
                "compliance_consequence": raw_response.get("conclusion"),
                "citations": raw_response.get("citations", []),
                "confidence": None,
                "uncertainty_or_escalation": raw_response.get("uncertainty"),
            }
            allowed_evidence_ids = {
                str(value)
                for value in (amendment_evidence_id, after_evidence_id)
                if value is not None
            }
            expected_version = (
                version_id
                if condition
                in {
                    "post_amendment_legal_context",
                    "both_versions_plus_reference_date",
                    "reconstructed_temporally_applicable_context",
                }
                else None
            )
            support = evaluate_explanation_support(
                explanation,
                {"version_id": expected_version, "applicable_date": applicable_date},
                allowed_evidence_ids,
                tuple(str(item) for item in required_fields),
            )
            base_record.update(
                {
                    "explanation": explanation,
                    "model_explanation_text": raw_response.get("explanation"),
                    "automated_support_evaluation": support,
                    "status": "automated_support_evaluated_expert_review_required",
                }
            )
        records.append(base_record)
    automated = [
        item["automated_support_evaluation"]
        for item in records
        if isinstance(item.get("automated_support_evaluation"), dict)
    ]
    aggregate_metrics = _aggregate_support_metrics(automated, records) if automated else None
    return {
        "schema_version": "1.0.0",
        "rubric_version": rubric.get("rubric_version"),
        "status": (
            "automated_support_evaluation_completed_expert_review_pending"
            if automated
            else "evaluation_plan_built_no_explanations_scored"
        ),
        "input_fingerprints": {
            "llm_plan_sha256": sha256(canonical_json_bytes(llm_plan)).hexdigest(),
            "scenario_scaffolds_sha256": sha256(canonical_json_bytes(scenarios)).hexdigest(),
            "annotation_workload_sha256": sha256(canonical_json_bytes(workload)).hexdigest(),
            "version_graph_sha256": sha256(canonical_json_bytes(graph.to_dict())).hexdigest(),
            "rubric_sha256": sha256(canonical_json_bytes(rubric)).hexdigest(),
        },
        "required_explanation_fields": required_fields,
        "automated_support_dimensions": rubric.get("automated_support_dimensions"),
        "expert_required_dimensions": rubric.get("expert_required_dimensions"),
        "records": sorted(records, key=lambda item: str(item["evaluation_id"])),
        "aggregate_metrics": aggregate_metrics,
        "limitations": [
            "No materiality or compliance gold exists for legal correctness scoring.",
            "Automated checks are limited to structure, identifier resolution and alignment.",
            "Aggregate values are pipeline-support diagnostics, not legal-quality metrics.",
            "No legal-correctness result is claimed.",
        ],
    }


def write_explanation_plan_and_lock(
    document: dict[str, object], output_path: Path, lock_path: Path
) -> dict[str, object]:
    payload = canonical_json_bytes(document)
    records = document.get("records")
    if not isinstance(records, list):
        raise ValueError("Explanation evaluation plan requires records")
    lock = {
        "schema_version": "1.0.0",
        "status": document.get("status"),
        "plan_sha256": sha256(payload).hexdigest(),
        "input_fingerprints": document.get("input_fingerprints"),
        "planned_evaluation_count": len(records),
        "automated_evaluation_count": sum(
            isinstance(item, dict) and item.get("automated_support_evaluation") is not None
            for item in records
        ),
        "expert_evaluation_count": sum(
            isinstance(item, dict) and item.get("expert_evaluation") is not None
            for item in records
        ),
        "all_known_post_versions_resolve": all(
            isinstance(item, dict) and item.get("known_post_version_exists") is True
            for item in records
        ),
        "aggregate_support_metrics_reported": document.get("aggregate_metrics") is not None,
        "legal_quality_metrics_reported": False,
        "unsupported_quality_claims_absent": True,
        "research_gate_passed": False,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{sha256(value.encode('utf-8')).hexdigest()[:24]}"


def _aggregate_support_metrics(
    evaluations: list[object], records: list[dict[str, object]]
) -> dict[str, object]:
    values = [item for item in evaluations if isinstance(item, dict)]

    def rate(field: str) -> dict[str, object]:
        eligible = [item[field] for item in values if isinstance(item.get(field), bool)]
        passed = sum(value is True for value in eligible)
        return {"passed": passed, "denominator": len(eligible), "rate": passed / len(eligible) if eligible else None}

    citation_values = [
        float(item["citation_precision"])
        for item in values
        if isinstance(item.get("citation_precision"), (int, float))
    ]
    abstentions = sum(
        isinstance(item.get("explanation"), dict)
        and item["explanation"].get("compliance_consequence") == "indeterminate"
        for item in records
    )
    return {
        "evaluation_count": len(values),
        "field_completeness_mean": (
            sum(float(item["field_completeness"]) for item in values) / len(values)
            if values
            else None
        ),
        "evidence_reference_resolution": rate("evidence_reference_resolution"),
        "version_alignment": rate("version_alignment"),
        "temporal_alignment": rate("temporal_alignment"),
        "uncertainty_presence": rate("uncertainty_presence"),
        "citation_precision_mean": (
            sum(citation_values) / len(citation_values) if citation_values else None
        ),
        "abstention_count": abstentions,
        "legal_correctness": None,
        "interpretation": "automated_pipeline_support_only_not_legal_quality",
    }
