"""Controlled Phase 9 planning, execution, normalization, and drift scoring."""

from __future__ import annotations

import json
import shutil
import subprocess
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

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
    execution_enabled = config.get("execution_enabled")
    model = config.get("model")
    model_version = config.get("model_version")
    if not isinstance(execution_enabled, bool):
        raise ValueError("execution_enabled must be a boolean")
    if execution_enabled and (not isinstance(model, str) or not model):
        raise ValueError("Execution-enabled plans require a selected model")
    if model_version is not None and not isinstance(model_version, str):
        raise ValueError("model_version must be a string or null")
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
                    "model": model,
                    "model_version": model_version,
                    "prompt_version": prompt.get("prompt_version"),
                    "temperature": config.get("temperature"),
                    "retrieval_configuration": config.get("retrieval_configuration"),
                    "raw_prompt": None,
                    "raw_response": None,
                    "execution_status": (
                        "ready_for_controlled_execution"
                        if execution_enabled
                        else "blocked_missing_scenario_gold_and_model"
                    ),
                }
            )
    return {
        "schema_version": "1.0.0",
        "experiment_id": config.get("experiment_id"),
        "status": (
            "controlled_plan_built_ready_for_execution"
            if execution_enabled
            else "controlled_plan_built_execution_blocked"
        ),
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
            "Scenario facts, questions and expected-change labels are not gold.",
            "A model execution does not convert machine-generated scenarios into legal gold.",
            "Temporal-drift performance metrics remain unavailable until independent gold exists.",
        ],
    }


def execute_controlled_plan_with_codex_cli(
    plan: dict[str, object],
    scenarios: dict[str, object],
    graph: object,
    prompt: dict[str, object],
    *,
    model: str,
    codex_command: str = "codex",
    timeout_seconds: int = 1800,
) -> dict[str, object]:
    """Execute every planned condition in one schema-constrained Codex CLI batch.

    The batch is an operational pipeline run, not a legal benchmark result.  It is
    intentionally allowed to execute incomplete scenarios so the correct model
    behaviour (abstention) and artifact plumbing can be tested end to end.
    """
    runs = plan.get("runs")
    scenario_items = scenarios.get("scenarios")
    if not isinstance(runs, list) or not runs:
        raise ValueError("Controlled execution requires planned runs")
    if not isinstance(scenario_items, list):
        raise ValueError("Controlled execution requires scenarios")
    executable = shutil.which(codex_command)
    if executable is None:
        candidate = Path(codex_command)
        if not candidate.is_file():
            raise ValueError(f"Codex CLI not found: {codex_command}")
        executable = str(candidate)

    scenario_by_id = {
        str(item["scenario_id"]): item
        for item in scenario_items
        if isinstance(item, dict) and item.get("scenario_id")
    }
    versions = {str(item.version_id): item for item in getattr(graph, "versions", ())}
    requests: list[dict[str, str]] = []
    prompt_by_run: dict[str, str] = {}
    for item in runs:
        if not isinstance(item, dict):
            raise ValueError("Planned runs must be objects")
        scenario = scenario_by_id.get(str(item.get("scenario_id")))
        if scenario is None:
            raise ValueError("Planned run references a missing scenario")
        rendered = _render_prompt(item, scenario, versions, prompt)
        run_id = str(item["run_id"])
        requests.append({"run_id": run_id, "prompt": rendered})
        prompt_by_run[run_id] = rendered

    batch_prompt = (
        "You are executing a controlled temporal-legal reasoning pipeline smoke test. "
        "Return exactly one result for every request. Follow each embedded prompt. "
        "Do not infer missing scenario facts, questions, legal versions, or legal conclusions. "
        "The current records are non-gold research scaffolds; abstain with conclusion "
        "'indeterminate' whenever information is insufficient. Keep explanations concise.\n\n"
        + json.dumps({"requests": requests}, ensure_ascii=False, sort_keys=True)
    )
    output_schema = _batch_output_schema()
    started = datetime.now(timezone.utc).isoformat()
    with TemporaryDirectory(prefix="tldrift-phase9-") as temporary_directory:
        temporary = Path(temporary_directory)
        schema_path = temporary / "batch-output.schema.json"
        output_path = temporary / "batch-output.json"
        schema_path.write_text(json.dumps(output_schema), encoding="utf-8")
        completed = subprocess.run(
            [
                executable,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "-C",
                str(temporary),
                "--sandbox",
                "read-only",
                "--model",
                model,
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                batch_prompt,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0 or not output_path.is_file():
            detail = (completed.stderr or completed.stdout)[-2000:]
            raise ValueError(f"Codex CLI execution failed ({completed.returncode}): {detail}")
        response_document = json.loads(output_path.read_text(encoding="utf-8"))
        client_log = completed.stderr
    finished = datetime.now(timezone.utc).isoformat()

    response_items = response_document.get("results")
    if not isinstance(response_items, list):
        raise ValueError("Model batch response has no results array")
    response_by_id: dict[str, dict[str, object]] = {}
    for item in response_items:
        if not isinstance(item, dict) or not isinstance(item.get("run_id"), str):
            raise ValueError("Model batch result is malformed")
        run_id = str(item["run_id"])
        if run_id in response_by_id:
            raise ValueError(f"Duplicate model response for {run_id}")
        assertion = item.get("assertion")
        if not isinstance(assertion, dict):
            raise ValueError(f"Missing structured assertion for {run_id}")
        response_by_id[run_id] = normalize_structured_assertion(assertion)
    expected_ids = set(prompt_by_run)
    if set(response_by_id) != expected_ids:
        raise ValueError("Model response run IDs do not exactly match the execution plan")

    executed_runs: list[dict[str, object]] = []
    normalized_assertions: list[dict[str, object]] = []
    for original in runs:
        run = dict(original)  # type: ignore[arg-type]
        run_id = str(run["run_id"])
        assertion = response_by_id[run_id]
        run.update(
            {
                "model": model,
                "model_version": model,
                "raw_prompt": prompt_by_run[run_id],
                "raw_response": assertion,
                "execution_status": "completed",
            }
        )
        executed_runs.append(run)
        normalized_assertions.append({"run_id": run_id, **assertion})

    result = dict(plan)
    result.update(
        {
            "status": "controlled_execution_completed_unscored_without_legal_gold",
            "runs": sorted(executed_runs, key=lambda item: str(item["run_id"])),
            "normalized_assertions": sorted(
                normalized_assertions, key=lambda item: str(item["run_id"])
            ),
            "metrics": None,
            "execution": {
                "provider": "openai_codex_cli",
                "model": model,
                "client": _codex_client_identity(client_log),
                "batch_invocation_count": 1,
                "started_at": started,
                "finished_at": finished,
                "planned_run_count": len(runs),
                "completed_run_count": len(executed_runs),
                "response_sha256": sha256(canonical_json_bytes(response_document)).hexdigest(),
                "scoring_status": "not_scored_missing_independent_legal_gold",
            },
            "limitations": [
                "The controlled LLM pipeline was executed on non-gold scenario scaffolds.",
                "Scenario facts and legal questions are absent, so abstention is expected.",
                "One schema-constrained batch invocation produced the per-condition assertions.",
                "No accuracy, drift, citation, explanation-quality, or legal-correctness claim is made.",
            ],
        }
    )
    return result


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
            isinstance(run, dict)
            and run.get("execution_status") == "completed"
            and run.get("raw_response") is not None
            for run in runs
        ),
        "all_planned_runs_completed": bool(runs)
        and all(
            isinstance(run, dict)
            and run.get("execution_status") == "completed"
            and run.get("raw_prompt") is not None
            and run.get("raw_response") is not None
            for run in runs
        ),
        "normalized_assertion_count": len(document.get("normalized_assertions", [])),
        "operational_execution_gate_passed": bool(runs)
        and all(
            isinstance(run, dict) and run.get("execution_status") == "completed"
            for run in runs
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


def _render_prompt(
    run: dict[str, object],
    scenario: dict[str, object],
    versions: dict[str, object],
    prompt: dict[str, object],
) -> str:
    condition = str(run["condition"])
    pre_version_id = scenario.get("pre_applicable_version_id")
    post_version_id = scenario.get("post_applicable_version_id")
    context: list[dict[str, object]] = []

    def add_version(label: str, version_id: object) -> None:
        if not isinstance(version_id, str) or version_id not in versions:
            context.append({"label": label, "status": "version_unavailable"})
            return
        version = versions[version_id]
        evidence = getattr(version, "evidence")
        context.append(
            {
                "label": label,
                "version_id": version_id,
                "provision_text_excerpt": str(getattr(version, "exact_text"))[:1600],
                "evidence_id": str(getattr(evidence, "block_id")),
                "evidence_locator": str(getattr(evidence, "locator")),
                "extraction_status": str(getattr(version, "extraction_status")),
            }
        )

    if condition in {"pre_amendment_legal_context", "both_versions", "both_versions_plus_reference_date"}:
        add_version("pre_amendment", pre_version_id)
    if condition in {
        "post_amendment_legal_context",
        "both_versions",
        "both_versions_plus_reference_date",
        "reconstructed_temporally_applicable_context",
    }:
        add_version("post_amendment", post_version_id)
    reference_date = None
    if condition == "pre_amendment_legal_context":
        reference_date = scenario.get("pre_reference_date")
    elif condition in {
        "post_amendment_legal_context",
        "both_versions_plus_reference_date",
        "reconstructed_temporally_applicable_context",
    }:
        reference_date = scenario.get("post_reference_date")
    payload = {
        "instruction": prompt.get("instruction"),
        "scenario_id": scenario.get("scenario_id"),
        "condition": condition,
        "facts": scenario.get("facts"),
        "legal_question": scenario.get("legal_question"),
        "reference_date": reference_date,
        "legal_context": context,
        "source_review_status": scenario.get("review_status"),
        "output_contract": {
            "conclusion": "compliant | non_compliant | indeterminate",
            "cited_version_id": "string or null; cite only a supplied version ID",
            "citations": "array; use only supplied evidence IDs or locators",
            "explanation": "concise reasoning",
            "uncertainty": "string or null",
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _batch_output_schema() -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["run_id", "assertion"],
                    "properties": {
                        "run_id": {"type": "string"},
                        "assertion": {
                            "type": "object",
                            "required": [
                                "conclusion",
                                "cited_version_id",
                                "citations",
                                "explanation",
                                "uncertainty",
                            ],
                            "properties": {
                                "conclusion": {
                                    "enum": ["compliant", "non_compliant", "indeterminate"]
                                },
                                "cited_version_id": {"type": ["string", "null"]},
                                "citations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "explanation": {"type": "string"},
                                "uncertainty": {"type": ["string", "null"]},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "additionalProperties": False,
                },
            }
        },
        "additionalProperties": False,
    }


def _codex_client_identity(log: str) -> str:
    for line in log.splitlines():
        if line.startswith("OpenAI Codex v"):
            return line.removeprefix("OpenAI Codex ")
    return "codex-cli-version-unreported"
