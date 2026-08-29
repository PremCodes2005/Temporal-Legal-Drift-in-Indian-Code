"""Controlled Phase 9 planning, normalization, and drift scoring."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes
from temporal_legal_drift.metrics import temporal_drift_metrics


REQUIRED_CONDITIONS = (
    "no_legal_context",
    "pre_amendment_legal_context",
    "post_amendment_legal_context",
    "both_versions",
    "both_versions_plus_reference_date",
    "reconstructed_temporally_applicable_context",
)
CONCLUSIONS = frozenset({"compliant", "non_compliant", "indeterminate"})


def build_llm_evaluation_plan(
    scenarios: dict[str, object],
    release: dict[str, object],
    baseline_run: dict[str, object],
    config: dict[str, object],
    prompt: dict[str, object],
) -> dict[str, object]:
    items = scenarios.get("scenarios")
    conditions = config.get("conditions")
    if not isinstance(items, list) or conditions != list(REQUIRED_CONDITIONS):
        raise ValueError("Phase 9 requires the six canonical controlled conditions")
    if config.get("execution_enabled") is not False or config.get("model") is not None:
        raise ValueError("Dry-run planning requires execution disabled and no selected model")
    if release.get("benchmark_frozen") is not False:
        raise ValueError("Current Phase 9 plan expects the non-frozen technical release")
    if baseline_run.get("metrics") is not None:
        raise ValueError("Current Phase 9 dry run expects no unsupported baseline metrics")

    runs: list[dict[str, object]] = []
    for scenario in items:
        if not isinstance(scenario, dict):
            raise ValueError("Scenarios must be objects")
        facts_hash = sha256(canonical_json_bytes(scenario.get("facts", []))).hexdigest()
        for condition in REQUIRED_CONDITIONS:
            run_id = _run_id(str(scenario["scenario_id"]), condition, str(config["experiment_id"]))
            runs.append(
                {
                    "run_id": run_id,
                    "scenario_id": scenario["scenario_id"],
                    "condition": condition,
                    "facts_sha256": facts_hash,
                    "model": None,
                    "model_version": None,
                    "prompt_version": prompt.get("prompt_version"),
                    "temperature": config.get("temperature"),
                    "retrieval_configuration": config.get("retrieval_configuration"),
                    "raw_prompt": None,
                    "raw_response": None,
                    "execution_status": "blocked_missing_scenario_gold_and_model",
                }
            )
    return {
        "schema_version": "1.0.0",
        "experiment_id": config.get("experiment_id"),
        "status": "controlled_plan_built_execution_blocked",
        "input_fingerprints": {
            "scenario_scaffolds_sha256": sha256(canonical_json_bytes(scenarios)).hexdigest(),
            "release_sha256": sha256(canonical_json_bytes(release)).hexdigest(),
            "baseline_run_sha256": sha256(canonical_json_bytes(baseline_run)).hexdigest(),
            "experiment_config_sha256": sha256(canonical_json_bytes(config)).hexdigest(),
            "prompt_config_sha256": sha256(canonical_json_bytes(prompt)).hexdigest(),
        },
        "conditions": list(REQUIRED_CONDITIONS),
        "runs": sorted(runs, key=lambda item: str(item["run_id"])),
        "normalized_assertions": [],
        "metrics": None,
        "failure_attributions": [],
        "limitations": [
            "No model or model version is selected.",
            "Scenario facts, questions and expected-change labels are not gold.",
            "No prompt was rendered and no provider was called.",
            "No LLM response, normalized assertion, drift metric or performance result exists.",
        ],
    }


def normalize_structured_assertion(value: dict[str, object]) -> dict[str, object]:
    conclusion = value.get("conclusion")
    if conclusion not in CONCLUSIONS:
        raise ValueError("Structured conclusion is invalid")
    citations = value.get("citations")
    if not isinstance(citations, list) or not all(isinstance(item, str) for item in citations):
        raise ValueError("Citations must be a list of strings")
    explanation = value.get("explanation")
    if not isinstance(explanation, str):
        raise ValueError("Explanation must be a string")
    cited_version = value.get("cited_version_id")
    uncertainty = value.get("uncertainty")
    if cited_version is not None and not isinstance(cited_version, str):
        raise ValueError("cited_version_id must be a string or null")
    if uncertainty is not None and not isinstance(uncertainty, str):
        raise ValueError("uncertainty must be a string or null")
    if set(value) != {
        "conclusion",
        "cited_version_id",
        "citations",
        "explanation",
        "uncertainty",
    }:
        raise ValueError("Structured assertion contains missing or unexpected fields")
    return {
        "conclusion": conclusion,
        "cited_version_id": cited_version,
        "citations": citations,
        "explanation": explanation,
        "uncertainty": uncertainty,
    }


def score_paired_assertions(records: list[dict[str, object]]) -> dict[str, object]:
    normalized: list[dict[str, object]] = []
    outcome_correct = 0
    outcome_denominator = 0
    version_correct = 0
    version_denominator = 0
    citation_true_positive = 0
    citation_predicted = 0
    citation_expected = 0
    for record in records:
        expected = record.get("expected_change")
        pre = record.get("pre_assertion")
        post = record.get("post_assertion")
        if expected not in {0, 1} or not isinstance(pre, dict) or not isinstance(post, dict):
            raise ValueError("Paired records require binary gold and two assertions")
        pre_value = normalize_structured_assertion(pre)
        post_value = normalize_structured_assertion(post)
        normalized.append(
            {
                "expected_change": expected,
                "model_change": int(pre_value["conclusion"] != post_value["conclusion"]),
            }
        )
        for prefix, assertion in (("pre", pre_value), ("post", post_value)):
            expected_conclusion = record.get(f"expected_{prefix}_conclusion")
            if expected_conclusion is not None:
                if expected_conclusion not in CONCLUSIONS:
                    raise ValueError("Expected conclusions must use the structured vocabulary")
                outcome_denominator += 1
                outcome_correct += assertion["conclusion"] == expected_conclusion
            expected_version = record.get(f"expected_{prefix}_version_id")
            if expected_version is not None:
                if not isinstance(expected_version, str):
                    raise ValueError("Expected version IDs must be strings")
                version_denominator += 1
                version_correct += assertion["cited_version_id"] == expected_version
            expected_citations = record.get(f"expected_{prefix}_citations")
            if expected_citations is not None:
                if not isinstance(expected_citations, list) or not all(
                    isinstance(item, str) for item in expected_citations
                ):
                    raise ValueError("Expected citations must be lists of strings")
                predicted_set = set(assertion["citations"])
                expected_set = set(expected_citations)
                citation_true_positive += len(predicted_set & expected_set)
                citation_predicted += len(predicted_set)
                citation_expected += len(expected_set)
    metrics = temporal_drift_metrics(normalized)
    metrics.update(
        {
            "compliance_outcome_correct_count": outcome_correct,
            "compliance_outcome_denominator": outcome_denominator,
            "compliance_outcome_accuracy": _ratio(outcome_correct, outcome_denominator),
            "version_correct_count": version_correct,
            "version_denominator": version_denominator,
            "version_accuracy": _ratio(version_correct, version_denominator),
            "citation_true_positive_count": citation_true_positive,
            "citation_predicted_denominator": citation_predicted,
            "citation_expected_denominator": citation_expected,
            "citation_precision": _ratio(citation_true_positive, citation_predicted),
            "citation_recall": _ratio(citation_true_positive, citation_expected),
        }
    )
    return metrics


def write_llm_plan_and_lock(
    document: dict[str, object], output_path: Path, lock_path: Path
) -> dict[str, object]:
    payload = canonical_json_bytes(document)
    runs = document.get("runs")
    conditions = document.get("conditions")
    if not isinstance(runs, list) or not isinstance(conditions, list):
        raise ValueError("LLM evaluation plan requires runs and conditions")
    scenario_ids = {str(item.get("scenario_id")) for item in runs if isinstance(item, dict)}
    facts_by_scenario: dict[str, set[str]] = {}
    for run in runs:
        if isinstance(run, dict):
            facts_by_scenario.setdefault(str(run.get("scenario_id")), set()).add(
                str(run.get("facts_sha256"))
            )
    lock = {
        "schema_version": "1.0.0",
        "status": document.get("status"),
        "plan_sha256": sha256(payload).hexdigest(),
        "input_fingerprints": document.get("input_fingerprints"),
        "scenario_count": len(scenario_ids),
        "condition_count": len(conditions),
        "planned_run_count": len(runs),
        "all_scenarios_have_six_conditions": all(
            sum(run.get("scenario_id") == scenario_id for run in runs if isinstance(run, dict))
            == 6
            for scenario_id in scenario_ids
        ),
        "facts_held_constant_across_conditions": all(
            len(hashes) == 1 for hashes in facts_by_scenario.values()
        ),
        "executed_run_count": sum(
            isinstance(run, dict) and run.get("raw_response") is not None for run in runs
        ),
        "metrics_reported": document.get("metrics") is not None,
        "unsupported_results_absent": document.get("metrics") is None,
        "research_gate_passed": False,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _run_id(scenario_id: str, condition: str, experiment_id: str) -> str:
    value = "\n".join([scenario_id, condition, experiment_id]).encode("utf-8")
    return f"run_{sha256(value).hexdigest()[:24]}"


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
