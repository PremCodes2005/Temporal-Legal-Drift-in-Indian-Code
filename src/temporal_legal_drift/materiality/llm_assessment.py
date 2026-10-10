"""LLM-based materiality opinions with schema/provenance checks and mandatory review."""

from __future__ import annotations

import json
import re
from collections import Counter
from hashlib import sha256
from typing import Any, Callable

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes
from temporal_legal_drift.metrics import classification_metrics

from .annotation import LABELS


LLM_ASSESSMENT_SCHEMA_VERSION = "1.0.0"
WORKFLOW_STATUSES = frozenset({"REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE"})
RequestModel = Callable[[list[dict[str, str]]], str]
ProgressCallback = Callable[[int, int, str, str], None]


class AssessmentValidationError(ValueError):
    """Model result violated the declared structured-output or evidence contract."""


def assess_materiality_with_llm(
    silver: dict[str, Any],
    round_document: dict[str, Any],
    graph: dict[str, Any],
    rubric: dict[str, Any],
    *,
    request_model: RequestModel | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Assess each silver pair independently; outputs stay opinions, never gold labels."""
    _validate_rubric(rubric)
    if silver.get("status") != "automated_silver_labels_not_gold":
        raise ValueError("LLM assessment requires the frozen, non-gold silver dataset")
    if silver.get("source_round_sha256") != sha256(canonical_json_bytes(round_document)).hexdigest():
        raise ValueError("Silver dataset and annotation round fingerprints do not match")
    silver_rows = silver.get("rows")
    tasks = round_document.get("tasks")
    if not isinstance(silver_rows, list) or len(silver_rows) != 50 or not isinstance(tasks, list):
        raise ValueError("Expected a complete 50-pair silver dataset and its annotation round")
    task_by_id = {str(task["pair_id"]): task for task in tasks}
    if len(task_by_id) != 50 or {str(row["pair_id"]) for row in silver_rows} != set(task_by_id):
        raise ValueError("Silver rows and source tasks must contain the same unique pair IDs")
    versions = {str(item["version_id"]): item for item in graph.get("provision_versions", [])}
    legal_sources = {str(item["source_id"]): item for item in graph.get("legal_sources", [])}
    call_model, provider, model = _resolve_model(request_model)
    assessments = []
    for silver_row in silver_rows:
        pair_id = str(silver_row["pair_id"])
        task = task_by_id[pair_id]
        evidence = _build_assessment_evidence(task, versions, legal_sources)
        messages = _make_prompt(task, evidence, rubric)
        raw_output: str | None = None
        raw_attempts: list[str] = []
        try:
            raw_output = call_model(messages)
            raw_attempts.append(raw_output)
            try:
                parsed = json.loads(raw_output)
                validate_llm_assessment(parsed, pair_id, rubric, evidence)
            except (AssessmentValidationError, json.JSONDecodeError, TypeError) as first_error:
                # One bounded repair attempt is useful for format-only errors.
                # Preserve both outputs and rerun every schema and quote check;
                # this never weakens the citation or legal-review requirements.
                repair_messages = _make_repair_prompt(
                    pair_id, rubric, evidence, raw_output, first_error
                )
                raw_output = call_model(repair_messages)
                raw_attempts.append(raw_output)
                parsed = json.loads(raw_output)
                validate_llm_assessment(parsed, pair_id, rubric, evidence)
            insufficient = parsed["insufficient_evidence"]
            assessments.append({
                "pair_id": pair_id,
                "workflow_status": "INSUFFICIENT_EVIDENCE" if insufficient else "REVIEW_REQUIRED",
                "assessment_status": "SCHEMA_AND_CITATION_VALID",
                "materiality_label": parsed["label"],
                "evidence": parsed["evidence"],
                "rationale": parsed["rationale"],
                "uncertainty": parsed["uncertainty"],
                "insufficient_evidence": insufficient,
                "citation_integrity": "ALL_QUOTES_FOUND_IN_SUPPLIED_SOURCE_TEXT",
                "legal_correctness": "UNVERIFIED",
                "raw_response_sha256": sha256(raw_output.encode("utf-8")).hexdigest(),
                "raw_response": raw_output,
                "raw_response_attempts": raw_attempts,
            })
        except AssessmentValidationError as error:
            assessments.append(_failed_assessment(pair_id, "INVALID_SCHEMA_OR_EVIDENCE", str(error), raw_output, raw_attempts))
        except (json.JSONDecodeError, TypeError) as error:
            assessments.append(_failed_assessment(pair_id, "INVALID_JSON", type(error).__name__, raw_output, raw_attempts))
        except Exception as error:  # Preserve per-pair failures; the other pairs can still run.
            assessments.append(_failed_assessment(pair_id, "MODEL_CALL_FAILED", type(error).__name__, raw_output, raw_attempts))
        if progress_callback is not None:
            current = assessments[-1]
            progress_callback(len(assessments), len(silver_rows), pair_id, str(current["assessment_status"]))
    silver_reference = {
        str(row["pair_id"]): row.get("automated_adjudication", {}).get("label")
        for row in silver_rows
    }
    silver_agreements: dict[str, Any] = {}
    for prediction_name, predicted_labels in (
        ("rule_a", [row["annotator_a"]["label"] for row in silver_rows]),
        ("rule_b", [row["annotator_b"]["label"] for row in silver_rows]),
    ):
        eligible_rule_pairs = [
            (silver_reference[str(row["pair_id"])], label)
            for row, label in zip(silver_rows, predicted_labels)
            if silver_reference[str(row["pair_id"])] in LABELS
        ]
        silver_agreements[prediction_name] = {
            "status": "silver_label_agreement_only",
            "eligible_pair_count": len(eligible_rule_pairs),
            "abstention_or_unresolved_count": len(silver_rows) - len(eligible_rule_pairs),
            "metrics": classification_metrics(
                [item[0] for item in eligible_rule_pairs], [item[1] for item in eligible_rule_pairs], LABELS
            ) if eligible_rule_pairs else None,
            "reference_is_derived_from_same_rule_systems": True,
        }
    eligible_llm = [
        item for item in assessments
        if item["assessment_status"] == "SCHEMA_AND_CITATION_VALID"
        and item["materiality_label"] in LABELS
        and not item["insufficient_evidence"]
        and silver_reference[item["pair_id"]] in LABELS
    ]
    llm_references = [silver_reference[item["pair_id"]] for item in eligible_llm]
    llm_predictions = [item["materiality_label"] for item in eligible_llm]
    silver_agreements["llm"] = {
        "status": "silver_label_agreement_only",
        "eligible_pair_count": len(eligible_llm),
        "abstention_or_error_count": len(assessments) - len(eligible_llm),
        "metrics": classification_metrics(llm_references, llm_predictions, LABELS) if eligible_llm else None,
        "reference_is_rule_derived_silver_not_gold": True,
    }
    return {
        "schema_version": "1.0.0",
        "assessment_id": "materiality-llm-assessments-v1",
        "status": "llm_materiality_assessments_complete_with_review_required",
        "source_silver_sha256": sha256(canonical_json_bytes(silver)).hexdigest(),
        "source_round_sha256": silver["source_round_sha256"],
        "rubric_id": rubric["rubric_id"],
        "rubric_version": rubric["version"],
        "provider": provider,
        "model": model,
        "temperature": 0.0,
        "case_count": len(assessments),
        "schema_valid_count": sum(item["assessment_status"] == "SCHEMA_AND_CITATION_VALID" for item in assessments),
        "review_required_count": sum(item["workflow_status"] == "REVIEW_REQUIRED" for item in assessments),
        "insufficient_evidence_count": sum(item["workflow_status"] == "INSUFFICIENT_EVIDENCE" for item in assessments),
        "failed_count": sum(item["assessment_status"] != "SCHEMA_AND_CITATION_VALID" for item in assessments),
        "silver_label_agreement_only": silver_agreements,
        "rows": assessments,
        "legal_validation_status": "unverified",
        "legal_correctness_claimed": False,
        "is_gold": False,
    }


def validate_llm_assessment(
    value: Any,
    pair_id: str,
    rubric: dict[str, Any],
    supplied_evidence: list[dict[str, Any]],
) -> None:
    """Validate the public JSON schema contract and that quotes occur in cited source text."""
    if not isinstance(value, dict):
        raise AssessmentValidationError("Output must be one JSON object")
    required = {"schema_version", "pair_id", "rubric_version", "label", "evidence", "rationale", "uncertainty", "insufficient_evidence"}
    if set(value) != required:
        raise AssessmentValidationError("Output fields do not exactly match the assessment schema")
    if value.get("schema_version") != LLM_ASSESSMENT_SCHEMA_VERSION:
        raise AssessmentValidationError("Unsupported assessment schema version")
    if value.get("pair_id") != pair_id or value.get("rubric_version") != rubric.get("version"):
        raise AssessmentValidationError("Pair ID or rubric version mismatch")
    insufficient = value.get("insufficient_evidence")
    if not isinstance(insufficient, bool):
        raise AssessmentValidationError("insufficient_evidence must be boolean")
    label = value.get("label")
    if insufficient:
        if label is not None:
            raise AssessmentValidationError("Insufficient-evidence assessments must abstain with a null label")
    elif label not in LABELS:
        raise AssessmentValidationError("A supported assessment requires one canonical materiality label")
    if not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        raise AssessmentValidationError("A non-empty rationale is required")
    if not isinstance(value.get("uncertainty"), str):
        raise AssessmentValidationError("uncertainty must be a string, including an empty string if none is stated")
    citations = value.get("evidence")
    if not isinstance(citations, list):
        raise AssessmentValidationError("evidence must be an array")
    source_quotes: dict[str, list[str]] = {}
    for source in supplied_evidence:
        source_quotes.setdefault(str(source["source_id"]), []).append(_normalize_quote(str(source["evidence_text"])))
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {"source_id", "quote"}:
            raise AssessmentValidationError("Each evidence item must contain only source_id and quote")
        source_id, quote = str(citation.get("source_id", "")), _normalize_quote(str(citation.get("quote", "")))
        if not source_id or not quote or not any(quote in candidate for candidate in source_quotes.get(source_id, [])):
            raise AssessmentValidationError("A cited quote was not found in the supplied text for its source_id")
    if not insufficient and not citations:
        raise AssessmentValidationError("A non-abstaining assessment requires at least one verifiable citation")


def build_materiality_ensemble(
    silver: dict[str, Any], assessments: dict[str, Any]
) -> dict[str, Any]:
    """Optional reproducible majority view; retain components and force human review."""
    if assessments.get("source_silver_sha256") != sha256(canonical_json_bytes(silver)).hexdigest():
        raise ValueError("LLM assessments do not reference this silver dataset")
    assessment_rows = assessments.get("rows", [])
    llm_by_pair = {str(row["pair_id"]): row for row in assessment_rows}
    if len(assessment_rows) != 50 or len(llm_by_pair) != 50:
        raise ValueError("Ensembling requires exactly one LLM assessment record for each of the 50 cases")
    outputs = []
    for row in silver.get("rows", []):
        pair_id = str(row["pair_id"])
        llm = llm_by_pair.get(pair_id)
        a, b = row["annotator_a"]["label"], row["annotator_b"]["label"]
        c = llm.get("materiality_label") if llm and llm.get("assessment_status") == "SCHEMA_AND_CITATION_VALID" else None
        votes = [label for label in (a, b, c) if label in LABELS]
        counts = Counter(votes)
        winner_count = max(counts.values(), default=0)
        winner = next((label for label in LABELS if counts[label] == winner_count), None) if winner_count >= 2 else None
        llm_insufficient = bool(llm and llm.get("workflow_status") == "INSUFFICIENT_EVIDENCE")
        outputs.append({
            "pair_id": pair_id,
            "rule_a_prediction": a,
            "rule_b_prediction": b,
            "rule_tiebreak_prediction": row["automated_adjudication"]["label"],
            "llm_prediction": c,
            "llm_workflow_status": llm.get("workflow_status") if llm else "REVIEW_REQUIRED",
            "ensemble_votes": votes,
            "ensemble_label": None if llm_insufficient else winner,
            "ensemble_status": "INSUFFICIENT_EVIDENCE" if llm_insufficient else "REVIEW_REQUIRED",
            "ensemble_disposition": "PROVISIONAL_MAJORITY" if winner and not llm_insufficient else "ABSTAIN_NO_MAJORITY",
            "gold_status": "NOT_GOLD",
        })
    return {
        "schema_version": "1.0.0",
        "ensemble_id": "materiality-optional-ensemble-v1",
        "status": "optional_machine_ensemble_not_gold",
        "source_silver_sha256": sha256(canonical_json_bytes(silver)).hexdigest(),
        "source_assessments_sha256": sha256(canonical_json_bytes(assessments)).hexdigest(),
        "case_count": len(outputs),
        "ensemble_enabled": True,
        "ensemble_method": "unweighted majority over raw rule A, rule B and valid non-abstaining LLM labels; derived rule tie-break is not counted as an extra vote",
        "review_required_count": len(outputs),
        "insufficient_evidence_count": sum(row["ensemble_status"] == "INSUFFICIENT_EVIDENCE" for row in outputs),
        "provisional_majority_count": sum(row["ensemble_disposition"] == "PROVISIONAL_MAJORITY" for row in outputs),
        "rows": outputs,
        "legal_correctness_claimed": False,
        "is_gold": False,
    }


def build_disagreement_report(silver: dict[str, Any], round_document: dict[str, Any]) -> str:
    """Write a case-by-case, non-adjudicative account of every rule disagreement."""
    tasks = {str(task["pair_id"]): task for task in round_document.get("tasks", [])}
    rows = {str(row["pair_id"]): row for row in silver.get("rows", [])}
    disagreement_ids = silver.get("agreement", {}).get("disagreement_pair_ids", [])
    parts = [
        "# Materiality Rule Disagreements — Review Required",
        "",
        f"This report lists all {len(disagreement_ids)} cases where the two rule systems disagree. It does not resolve any case or claim legal correctness.",
        "",
    ]
    for number, pair_id in enumerate(disagreement_ids, 1):
        prediction = rows[str(pair_id)]
        task = tasks[str(pair_id)]
        amendment = next((source for source in task["source_evidence"] if source.get("role") == "amendment_instruction"), None)
        evidence = amendment.get("evidence_text", "") if amendment else ""
        parts.extend([
            f"## {number}. {pair_id}",
            "",
            f"- Act / provision: {task.get('act_title', task.get('act_id'))} / {task.get('provision_path')}",
            f"- Operation: {task.get('operation')}",
            f"- Rule A ({prediction['annotator_a']['method_id']}): **{prediction['annotator_a']['label']}** — {prediction['annotator_a']['rationale']}",
            f"- Rule B ({prediction['annotator_b']['method_id']}): **{prediction['annotator_b']['label']}** — {prediction['annotator_b']['rationale']}",
            f"- Existing tie-break: **{prediction['automated_adjudication']['label']}** (provisional only; not independent adjudication)",
            f"- Evidence source IDs: {', '.join(prediction['source_evidence_ids'])}",
            f"- Amendment instruction excerpt: “{_excerpt(evidence)}”",
            f"- Before excerpt: “{_excerpt(task.get('before_text', ''))}”",
            f"- After excerpt: “{_excerpt(task.get('after_text', ''))}”",
            "- Disposition: **REVIEW_REQUIRED**; no prediction is treated as truth.",
            "",
        ])
    return "\n".join(parts)


def render_none_coverage_report(search: dict[str, Any]) -> str:
    parts = [
        "# Search for Potential Materiality-None Cases",
        "",
        f"Status: **{search['status']}**",
        "",
        f"- Real graph transitions scanned: {search['transition_count_scanned']}",
        f"- Normalized-text-equal candidates: {search['normalized_text_match_count']}",
        f"- Cross-source review candidates: {search['reviewable_candidate_count']}",
        f"- Rejected candidates: {search['rejected_candidate_count']}",
        "- `None` gold labels created: 0",
        "",
        search["interpretation"],
        "",
    ]
    for item in search.get("results", []):
        parts.extend([
            f"## {item['transition_id']}",
            "",
            f"- Candidate status: `{item['candidate_status']}`",
            f"- Operation: `{item['operation']}`",
            f"- Versions: `{item['before_version_id']}` → `{item['after_version_id']}`",
            f"- Source IDs: {', '.join(item['source_ids']) or 'none'}",
            f"- Finding: {item['reason']}",
            "",
        ])
    return "\n".join(parts)


def write_llm_assessments(document: dict[str, Any], output_path: Any, lock_path: Any) -> dict[str, Any]:
    payload = canonical_json_bytes(document)
    _refuse_immutable_overwrite(output_path, payload, "LLM assessment run")
    lock = {
        "schema_version": "1.0.0",
        "assessment_id": document.get("assessment_id"),
        "status": document.get("status"),
        "artifact_sha256": sha256(payload).hexdigest(),
        "case_count": document.get("case_count"),
        "schema_valid_count": document.get("schema_valid_count"),
        "insufficient_evidence_count": document.get("insufficient_evidence_count"),
        "failed_count": document.get("failed_count"),
        "legal_correctness_claimed": False,
        "is_gold": False,
    }
    _refuse_immutable_overwrite(lock_path, canonical_json_bytes(lock), "LLM assessment lock")
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def write_ensemble(document: dict[str, Any], output_path: Any, lock_path: Any) -> dict[str, Any]:
    payload = canonical_json_bytes(document)
    _refuse_immutable_overwrite(output_path, payload, "materiality ensemble")
    lock = {
        "schema_version": "1.0.0",
        "ensemble_id": document.get("ensemble_id"),
        "status": document.get("status"),
        "artifact_sha256": sha256(payload).hexdigest(),
        "case_count": document.get("case_count"),
        "review_required_count": document.get("review_required_count"),
        "legal_correctness_claimed": False,
        "is_gold": False,
    }
    _refuse_immutable_overwrite(lock_path, canonical_json_bytes(lock), "materiality ensemble lock")
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _refuse_immutable_overwrite(path: Any, payload: bytes, description: str) -> None:
    from pathlib import Path

    target = Path(path)
    if not target.exists():
        return
    current = target.read_bytes()
    if sha256(current).digest() != sha256(payload).digest():
        raise ValueError(f"Refusing to overwrite existing {description}; choose a new output path/version")


def _build_assessment_evidence(
    task: dict[str, Any], versions: dict[str, dict[str, Any]], legal_sources: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    amendment = next((item for item in task.get("source_evidence", []) if item.get("role") == "amendment_instruction"), None)
    if amendment:
        evidence.append({
            "source_id": str(amendment["source_id"]),
            "source_url": amendment.get("source_url"),
            "sha256": amendment.get("sha256"),
            "role": "amendment_instruction",
            "locator": amendment.get("locator"),
            "evidence_text": str(amendment.get("evidence_text") or ""),
        })
    for role, version_key in (("before_version_text", "before_version_id"), ("after_version_text", "after_version_id")):
        version = versions.get(str(task.get(version_key)))
        if not version:
            continue
        # The source-anchored fragments are the exact before/after text submitted
        # for annotation. Avoid duplicating an entire consolidated document into
        # every prompt; the underlying source ID, URL and document hash are kept.
        for source_id in version.get("source_ids", []):
            source = legal_sources.get(str(source_id), {})
            text = str(task.get("before_text" if role == "before_version_text" else "after_text") or "")
            if text:
                evidence.append({
                    "source_id": str(source_id),
                    "source_url": source.get("source_url"),
                    "source_sha256": source.get("sha256"),
                    "role": role,
                    "locator": {"version_id": version.get("version_id")},
                    "evidence_text": text,
                })
    return evidence


def _make_prompt(task: dict[str, Any], evidence: list[dict[str, Any]], rubric: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You are performing a constrained research annotation, not giving legal advice. "
        "Use only the supplied before/after text, amendment operation, source evidence, and rubric. "
        "A source quote may support what words appear, but does not prove your legal interpretation. "
        "If evidence is incomplete or legal effect cannot be distinguished, set insufficient_evidence=true and label=null. "
        "Keep the rationale concise and quote only the shortest spans needed to support the textual comparison. "
        "Always return a single JSON object matching the exact requested schema. Do not repeat or echo the input. "
        "Do not add keys. Do not use markdown. Keep rationale to at most two short sentences."
    )
    payload = {
        "pair_id": task["pair_id"],
        "rubric_version": rubric["version"],
        "proposed_rubric_not_legally_validated": rubric,
        "amendment_operation": task.get("operation"),
        "before_text": task.get("before_text"),
        "after_text": task.get("after_text"),
        "amendment_instruction_text": task.get("amendment_instruction_text"),
        "sources": [
            {"source_id": item["source_id"], "source_sha256": item.get("sha256", item.get("source_sha256")),
             "source_url": item.get("source_url"), "role": item.get("role"),
             "locator": item.get("locator"), "text": item.get("evidence_text")}
            for item in evidence
        ],
        "output_schema": {
            "schema_version": "1.0.0",
            "pair_id": "same pair_id",
            "rubric_version": "same rubric version",
            "label": "High | Medium | Low | None; null only when insufficient_evidence=true",
            "evidence": [{"source_id": "exact supplied source id", "quote": "verbatim substring of that source text"}],
            "rationale": "string explaining how the rubric applies",
            "uncertainty": "string, empty only if no uncertainty",
            "insufficient_evidence": "boolean",
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
    ]


def _make_repair_prompt(
    pair_id: str,
    rubric: dict[str, Any],
    evidence: list[dict[str, Any]],
    invalid_output: str,
    error: Exception,
) -> list[dict[str, str]]:
    """Ask for one schema-only correction; the returned value is revalidated."""
    context = {
        "pair_id": pair_id,
        "rubric_version": rubric["version"],
        "allowed_labels": list(LABELS),
        "source_evidence": [
            {"source_id": item["source_id"], "text": item["evidence_text"]}
            for item in evidence
        ],
        "sources": [
            {"source_id": item["source_id"], "text": item["evidence_text"]}
            for item in evidence
        ],
        "invalid_output": invalid_output[:12000],
        "validation_error": str(error),
    }
    schema = {
        "schema_version": "1.0.0",
        "pair_id": pair_id,
        "rubric_version": rubric["version"],
        "label": "High | Medium | Low | None, or null only if insufficient_evidence is true",
        "evidence": [{"source_id": "exact supplied source id", "quote": "exact substring from that source text"}],
        "rationale": "brief string",
        "uncertainty": "string",
        "insufficient_evidence": "boolean",
    }
    return [
        {
            "role": "system",
            "content": (
                "Correct the previous response to the required JSON schema. Return ONLY the JSON object. "
                "Do not echo the input, add keys, invent evidence, or change evidence quotes. "
                "If unable to produce a valid supported answer, abstain with label null, empty evidence, "
                "and insufficient_evidence true. This remains a provisional machine assessment."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {**context, "required_schema": schema},
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
    ]


def _resolve_model(request_model: RequestModel | None) -> tuple[RequestModel, str, str]:
    if request_model is not None:
        return request_model, "injected_test_or_caller", "injected"
    from temporal_legal_drift.rag.rag_pipeline import _chat_completion, _llm_configured, _llm_model, _rag_provider

    if not _llm_configured():
        raise RuntimeError("No configured LLM is available; set up Ollama or the configured OpenAI-compatible provider")
    return _chat_completion, _rag_provider(), _llm_model()


def _failed_assessment(
    pair_id: str, status: str, reason: str, raw_output: str | None, raw_attempts: list[str]
) -> dict[str, Any]:
    return {
        "pair_id": pair_id,
        "workflow_status": "REVIEW_REQUIRED",
        "assessment_status": status,
        "materiality_label": None,
        "evidence": [],
        "rationale": "No schema-valid, source-verified LLM assessment was produced.",
        "uncertainty": reason,
        "insufficient_evidence": None,
        "citation_integrity": "NOT_ESTABLISHED",
        "legal_correctness": "UNVERIFIED",
        "raw_response_sha256": sha256(raw_output.encode("utf-8")).hexdigest() if raw_output is not None else None,
        "raw_response": raw_output,
        "raw_response_attempts": raw_attempts,
    }


def _validate_rubric(rubric: dict[str, Any]) -> None:
    if rubric.get("status") != "proposed_operational_research_rubric_not_legally_validated":
        raise ValueError("LLM assessment only accepts the proposed, non-legal rubric")
    if rubric.get("legal_validation_status") != "unverified_no_qualified_legal_reviewer":
        raise ValueError("Rubric must preserve the explicit unverified legal-review status")
    if rubric.get("canonical_labels") != list(LABELS) or rubric.get("version") != "1.0.0":
        raise ValueError("Unsupported materiality rubric version or label order")
    if len(rubric.get("levels", [])) != 4 or {item.get("label") for item in rubric["levels"]} != set(LABELS):
        raise ValueError("Rubric must define all four canonical levels exactly once")


def _normalize_quote(value: str) -> str:
    return " ".join(re.sub(r"\s+", " ", value).casefold().split())


def _excerpt(value: Any, limit: int = 360) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[:limit].rstrip() + " …"
