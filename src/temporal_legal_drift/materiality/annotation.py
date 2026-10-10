"""Evidence-backed materiality annotation workflow; never synthesizes human labels."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from typing import Any

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes


LABELS = ("High", "Medium", "Low", "None")
REQUIRED_DATE_TYPES = frozenset({"publication", "assent", "commencement", "applicability", "legal_effect"})


def build_materiality_round(
    graph: dict[str, Any],
    taxonomy: dict[str, Any],
    *,
    pilot_size: int = 50,
) -> dict[str, Any]:
    """Create annotation tasks from machine-corroborated transitions, not gold labels."""
    if pilot_size != 50:
        raise ValueError("The initial materiality annotation round is fixed at 50 cases")
    _validate_taxonomy(taxonomy)
    sources = {str(item["source_id"]): item for item in graph.get("legal_sources", [])}
    versions = {str(item["version_id"]): item for item in graph.get("provision_versions", [])}
    provisions = {str(item["provision_id"]): item for item in graph.get("provisions", [])}
    acts = {str(item["act_id"]): item for item in graph.get("acts", [])}
    events = {str(item["amendment_event_id"]): item for item in graph.get("amendment_events", [])}
    transitions = [
        item for item in graph.get("transitions", [])
        if item.get("validation_status") == "MACHINE_CROSS_SOURCE_CORROBORATED"
        and item.get("validation_checks", {}).get("forward_operation_round_trip") is True
        and item.get("validation_checks", {}).get("after_fragment_matches_consolidated_principal_act") is True
    ]
    if len(transitions) < pilot_size:
        raise ValueError(f"Need {pilot_size} machine-corroborated transitions; found {len(transitions)}")

    # Balance INSERT/SUBSTITUTE where possible; within each operation prioritize dated,
    # then stable IDs. Any unresolved operation mixture is represented faithfully.
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in transitions:
        groups.setdefault(str(item["operation"]).upper(), []).append(item)
    for values in groups.values():
        values.sort(key=lambda item: (item.get("effective_date") is None, str(item["transition_id"])))
    selected: list[dict[str, Any]] = []
    operation_order = sorted(groups)
    while len(selected) < pilot_size:
        made_progress = False
        for operation in operation_order:
            if groups[operation]:
                selected.append(groups[operation].pop(0))
                made_progress = True
                if len(selected) == pilot_size:
                    break
        if not made_progress:
            break

    tasks: list[dict[str, Any]] = []
    for transition in selected:
        before = versions[str(transition["before_version_id"])]
        after = versions[str(transition["after_version_id"])]
        provision = provisions[str(transition["target_provision_id"])]
        event = events[str(transition["amendment_event_id"])]
        act = acts[str(provision["act_id"])]
        evidence_source = sources[str(event["evidence"]["source_id"])]
        source_rows: list[dict[str, Any]] = [{
            "source_id": evidence_source["source_id"],
            "sha256": evidence_source["sha256"],
            "source_url": evidence_source["source_url"],
            "role": "amendment_instruction",
            "locator": {
                "page": event["evidence"].get("page"),
                "line": event["evidence"].get("line"),
            },
            "evidence_text": event["evidence"]["exact_text"],
        }]
        for version_id in transition.get("corroborating_consolidated_version_ids", []):
            snapshot = versions[str(version_id)]
            for source_id in snapshot.get("source_ids", []):
                source = sources[str(source_id)]
                source_rows.append({
                    "source_id": source["source_id"],
                    "sha256": source["sha256"],
                    "source_url": source["source_url"],
                    "role": "consolidated_after_text_corroboration",
                    "locator": {"version_id": snapshot["version_id"]},
                    "evidence_text": snapshot["text"],
                })
        # Same source may corroborate multiple snapshots; preserve one deterministic anchor.
        unique_sources = {str(item["source_id"]): item for item in source_rows}
        task_id = _stable_id("mat", transition["transition_id"], taxonomy["guideline_version"])
        tasks.append({
            "pair_id": task_id,
            "transition_id": transition["transition_id"],
            "amendment_event_id": event["amendment_event_id"],
            "act_id": act["act_id"],
            "act_title": act["title"],
            "provision_id": provision["provision_id"],
            "provision_path": provision["canonical_path"],
            "target_path_detail": event.get("target_path_detail"),
            "operation": transition["operation"],
            "unit_of_analysis": "amendment_controlled_fragment_not_full_historical_provision",
            "before_version_id": before["version_id"],
            "after_version_id": after["version_id"],
            "before_text": before["text"],
            "after_text": after["text"],
            "before_fragment_state": "NO_PRIOR_FRAGMENT_FOR_INSERT" if transition["operation"] == "INSERT" else "AMENDMENT_OLD_WORDING",
            "amendment_instruction_text": event["evidence"]["exact_text"],
            "effective_date": transition.get("effective_date"),
            "date_basis": transition.get("date_basis"),
            "source_evidence": sorted(unique_sources.values(), key=lambda item: (item["role"], item["source_id"])),
            "machine_checks": transition["validation_checks"],
            "annotations": [],
            "adjudication": None,
            "materiality": {"label": None, "dimensions": [], "status": "awaiting_independent_annotations"},
            "guideline_version": taxonomy["guideline_version"],
            "gold_status": "NOT_GOLD",
        })
    return {
        "schema_version": "1.0.0",
        "round_id": "materiality-annotation-round-v1",
        "status": "annotation_round_open_not_gold",
        "unit_of_analysis": "amendment_controlled_fragment_not_full_historical_provision",
        "taxonomy_status": taxonomy.get("status"),
        "guideline_version": taxonomy["guideline_version"],
        "canonical_labels": list(LABELS),
        "required_independent_annotators_per_pair": 2,
        "required_adjudication_per_pair": True,
        "selection": {
            "policy": "deterministic round-robin by operation among machine-corroborated transitions",
            "candidate_transition_count": len(transitions),
            "selected_count": len(tasks),
            "operation_distribution": dict(sorted(Counter(task["operation"] for task in tasks).items())),
        },
        "input_sha256": sha256(canonical_json_bytes(graph)).hexdigest(),
        "taxonomy_sha256": sha256(canonical_json_bytes(taxonomy)).hexdigest(),
        "annotation_count": 0,
        "adjudicated_count": 0,
        "gold_labels_created": 0,
        "tasks": tasks,
    }


def compute_annotation_agreement(
    round_document: dict[str, Any], annotations_document: dict[str, Any]
) -> dict[str, Any]:
    """Calculate raw agreement and Cohen's kappa only for complete independent pairs."""
    tasks = round_document.get("tasks")
    rows = annotations_document.get("annotations")
    if not isinstance(tasks, list) or not isinstance(rows, list):
        raise ValueError("Round and annotation submission must contain task/annotation arrays")
    task_ids = {str(item["pair_id"]) for item in tasks}
    tasks_by_id = {str(item["pair_id"]): item for item in tasks}
    by_pair: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str]] = set()
    annotation_ids: set[str] = set()
    errors: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append("annotation_not_object")
            continue
        pair_id = str(row.get("pair_id", ""))
        annotator_id = str(row.get("annotator_id", ""))
        if pair_id not in task_ids:
            errors.append(f"unknown_pair:{pair_id}")
        if not annotator_id:
            errors.append(f"missing_annotator_id:{pair_id}")
        annotation_id = str(row.get("annotation_id", ""))
        if not annotation_id or annotation_id in annotation_ids:
            errors.append(f"invalid_or_duplicate_annotation_id:{annotation_id or pair_id}")
        annotation_ids.add(annotation_id)
        if not _has_timezone_timestamp(row.get("submitted_at")):
            errors.append(f"invalid_submission_timestamp:{pair_id}:{annotator_id}")
        key = (pair_id, annotator_id)
        if key in seen:
            errors.append(f"duplicate_submission:{pair_id}:{annotator_id}")
        seen.add(key)
        if row.get("label") not in LABELS:
            errors.append(f"invalid_label:{pair_id}:{annotator_id}")
        if not str(row.get("rationale", "")).strip():
            errors.append(f"missing_rationale:{pair_id}:{annotator_id}")
        if row.get("guideline_version") != round_document.get("guideline_version"):
            errors.append(f"guideline_version_mismatch:{pair_id}:{annotator_id}")
        if not isinstance(row.get("dimensions"), list):
            errors.append(f"invalid_dimensions:{pair_id}:{annotator_id}")
        confidence = row.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"invalid_confidence:{pair_id}:{annotator_id}")
        if not isinstance(row.get("evidence_spans"), list) or not row.get("evidence_spans"):
            errors.append(f"missing_evidence_spans:{pair_id}:{annotator_id}")
        by_pair.setdefault(pair_id, []).append(row)

    complete: list[tuple[str, str]] = []
    complete_rater_pairs: set[tuple[str, str]] = set()
    complete_ids: set[str] = set()
    for pair_id, pair_rows in by_pair.items():
        if len(pair_rows) != 2 or len({str(row.get("annotator_id")) for row in pair_rows}) != 2:
            errors.append(f"not_two_independent_annotations:{pair_id}")
            continue
        if all(
            row.get("label") in LABELS
            and str(row.get("rationale", "")).strip()
            and row.get("guideline_version") == round_document.get("guideline_version")
            and row.get("annotation_id")
            and _has_timezone_timestamp(row.get("submitted_at"))
            and isinstance(row.get("dimensions"), list)
            and isinstance(row.get("confidence"), (int, float))
            and 0 <= row["confidence"] <= 1
            and isinstance(row.get("evidence_spans"), list)
            and row.get("evidence_spans")
            for row in pair_rows
        ):
            pair_rows.sort(key=lambda row: str(row["annotator_id"]))
            try:
                _validate_annotation_evidence(tasks_by_id[pair_id], pair_rows)
            except ValueError:
                errors.append(f"unsupported_evidence_quote:{pair_id}")
                continue
            complete.append((str(pair_rows[0]["label"]), str(pair_rows[1]["label"])))
            complete_rater_pairs.add(tuple(str(row["annotator_id"]) for row in pair_rows))
            complete_ids.add(pair_id)
    inconsistent_raters = len(complete_rater_pairs) > 1
    if inconsistent_raters:
        errors.append("inconsistent_annotator_pair_for_cohens_kappa")
        complete = []
        complete_ids.clear()
    count = len(complete)
    observed = sum(left == right for left, right in complete)
    raw_agreement = observed / count if count else None
    first_counts = Counter(left for left, _ in complete)
    second_counts = Counter(right for _, right in complete)
    expected = (
        sum(first_counts[label] * second_counts[label] for label in LABELS) / (count * count)
        if count else None
    )
    kappa = (
        (raw_agreement - expected) / (1 - expected)
        if raw_agreement is not None and expected is not None and expected != 1
        else None
    )
    matrix = {
        left: {right: sum(a == left and b == right for a, b in complete) for right in LABELS}
        for left in LABELS
    }
    return {
        "schema_version": "1.0.0",
        "status": "agreement_computed" if count else "awaiting_independent_annotations",
        "round_id": round_document.get("round_id"),
        "task_count": len(tasks),
        "submitted_annotation_count": len(rows),
        "complete_double_annotated_pair_count": count,
        "missing_double_annotation_pair_count": max(0, len(tasks) - count),
        "incomplete_pair_ids": sorted(task_id for task_id in task_ids if task_id not in complete_ids),
        "raw_agreement": raw_agreement,
        "raw_agreement_percent": round(raw_agreement * 100, 2) if raw_agreement is not None else None,
        "annotator_pair": list(next(iter(complete_rater_pairs))) if len(complete_rater_pairs) == 1 else None,
        "cohens_kappa": kappa,
        "cohens_kappa_undefined_reason": (
            "expected_agreement_equals_one" if count and expected == 1 else "no_complete_double_annotated_pairs" if not count else None
        ),
        "expected_agreement": expected,
        "class_distribution_annotator_1": dict(sorted(first_counts.items())),
        "class_distribution_annotator_2": dict(sorted(second_counts.items())),
        "confusion_matrix_annotator_1_rows_annotator_2_columns": matrix,
        "submission_errors": sorted(set(errors)),
        "gold_labels_created": 0,
        "legal_validity_claimed": False,
    }


def freeze_materiality_gold(
    round_document: dict[str, Any],
    annotations_document: dict[str, Any],
    adjudications_document: dict[str, Any],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    """Freeze a 50-row adjudicated gold set; fail closed on any missing human work."""
    _validate_taxonomy(taxonomy)
    if taxonomy.get("status") != "frozen" or "draft" in str(taxonomy.get("guideline_version", "")).lower():
        raise ValueError("Cannot freeze materiality gold until the taxonomy and guideline are formally frozen")
    tasks = round_document.get("tasks")
    annotation_rows = annotations_document.get("annotations")
    adjudication_rows = adjudications_document.get("adjudications")
    if not isinstance(tasks, list) or len(tasks) != 50:
        raise ValueError("Materiality gold requires exactly 50 annotation tasks")
    if not isinstance(annotation_rows, list) or not isinstance(adjudication_rows, list):
        raise ValueError("Independent annotations and adjudications must be supplied as arrays")
    agreement = compute_annotation_agreement(round_document, annotations_document)
    if agreement["complete_double_annotated_pair_count"] != 50 or agreement["submission_errors"]:
        raise ValueError("Cannot freeze gold: every pair needs two valid independent annotations")
    annotations_by_pair: dict[str, list[dict[str, Any]]] = {}
    for item in annotation_rows:
        annotations_by_pair.setdefault(str(item["pair_id"]), []).append(item)
    adjudications_by_pair: dict[str, dict[str, Any]] = {}
    for item in adjudication_rows:
        pair_id = str(item.get("pair_id", ""))
        if pair_id in adjudications_by_pair:
            raise ValueError(f"Duplicate adjudication for {pair_id}")
        adjudications_by_pair[pair_id] = item
    if set(adjudications_by_pair) != {str(item["pair_id"]) for item in tasks}:
        raise ValueError("Every task must have exactly one explicit adjudication")

    gold_rows = []
    for task in tasks:
        pair_id = str(task["pair_id"])
        adjudication = adjudications_by_pair[pair_id]
        labels = {str(item["label"]) for item in annotations_by_pair[pair_id]}
        if adjudication.get("label") not in LABELS:
            raise ValueError(f"Adjudicated label invalid for {pair_id}")
        if adjudication.get("adjudicator_id") in {
            str(item["annotator_id"]) for item in annotations_by_pair[pair_id]
        }:
            raise ValueError(f"Adjudicator must be independent for {pair_id}")
        if not str(adjudication.get("rationale", "")).strip():
            raise ValueError(f"Adjudication rationale missing for {pair_id}")
        if adjudication.get("guideline_version") != taxonomy.get("guideline_version"):
            raise ValueError(f"Guideline version mismatch for {pair_id}")
        if not isinstance(adjudication.get("dimensions"), list):
            raise ValueError(f"Adjudicated dimensions missing for {pair_id}")
        _validate_annotation_evidence(task, annotations_by_pair[pair_id])
        _validate_adjudication_evidence(task, adjudication)
        gold_rows.append({
            **task,
            "annotations": sorted(annotations_by_pair[pair_id], key=lambda item: str(item["annotator_id"])),
            "adjudication": adjudication,
            "annotator_labels": sorted(labels),
            "materiality": {
                "label": adjudication["label"],
                "dimensions": adjudication.get("dimensions", []),
                "status": "adjudicated",
            },
            "gold_status": "ADJUDICATED_GOLD",
        })
    return {
        "schema_version": "1.0.0",
        "dataset_id": "materiality-gold-v1",
        "status": "adjudicated_gold",
        "guideline_version": taxonomy["guideline_version"],
        "taxonomy_sha256": sha256(canonical_json_bytes(taxonomy)).hexdigest(),
        "annotation_round_sha256": sha256(canonical_json_bytes(round_document)).hexdigest(),
        "agreement": agreement,
        "pair_count": len(gold_rows),
        "class_distribution": dict(sorted(Counter(row["materiality"]["label"] for row in gold_rows).items())),
        "rows": gold_rows,
        "legal_validation_status": "requires_reviewer_signoff",
        "legal_correctness_claimed": False,
    }


def write_materiality_round(document: dict[str, Any], path: Path, lock_path: Path) -> dict[str, Any]:
    payload = canonical_json_bytes(document)
    tasks = document.get("tasks", [])
    task_ids = [str(item.get("pair_id", "")) for item in tasks if isinstance(item, dict)]
    lock = {
        "schema_version": "1.0.0",
        "status": document.get("status"),
        "round_sha256": sha256(payload).hexdigest(),
        "task_count": len(tasks),
        "unique_pair_count": len(set(task_ids)),
        "all_tasks_have_two_source_anchors": all(
            len(item.get("source_evidence", [])) >= 2 for item in tasks
        ),
        "all_tasks_machine_corroborated": all(
            item.get("machine_checks", {}).get("after_fragment_matches_consolidated_principal_act") is True
            and item.get("machine_checks", {}).get("forward_operation_round_trip") is True
            for item in tasks
        ),
        "all_labels_unassigned": all(item.get("materiality", {}).get("label") is None for item in tasks),
        "gold_labels_created": 0,
        "research_gate_passed": False,
    }
    atomic_replace(path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _validate_annotation_evidence(task: dict[str, Any], annotations: list[dict[str, Any]]) -> None:
    evidence_by_source: dict[str, list[str]] = {}
    for item in task.get("source_evidence", []):
        evidence_by_source.setdefault(str(item["source_id"]), []).append(str(item.get("evidence_text", "")))
    for annotation in annotations:
        spans = annotation.get("evidence_spans")
        if not isinstance(spans, list) or not spans:
            raise ValueError(f"Evidence span required for {task['pair_id']}")
        for span in spans:
            source_id = str(span.get("source_id", ""))
            quoted = " ".join(str(span.get("text", "")).casefold().split())
            candidates = [" ".join(text.casefold().split()) for text in evidence_by_source.get(source_id, [])]
            if not quoted or not any(quoted in text for text in candidates):
                raise ValueError(f"Unsupported evidence quote in {task['pair_id']}")


def _validate_adjudication_evidence(task: dict[str, Any], adjudication: dict[str, Any]) -> None:
    if not str(adjudication.get("rationale", "")).strip():
        raise ValueError(f"Adjudication rationale missing for {task['pair_id']}")
    if not _has_timezone_timestamp(adjudication.get("adjudicated_at")):
        raise ValueError(f"Adjudication timestamp must include a timezone for {task['pair_id']}")
    evidence = adjudication.get("evidence_span")
    if not isinstance(evidence, dict):
        raise ValueError(f"Adjudication evidence span missing for {task['pair_id']}")
    source_id = str(evidence.get("source_id", ""))
    quoted = " ".join(str(evidence.get("text", "")).casefold().split())
    candidates = [
        " ".join(str(item.get("evidence_text", "")).casefold().split())
        for item in task.get("source_evidence", [])
        if str(item.get("source_id")) == source_id
    ]
    if not quoted or not any(quoted in candidate for candidate in candidates):
        raise ValueError(f"Unsupported adjudication evidence in {task['pair_id']}")


def _has_timezone_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _validate_taxonomy(taxonomy: dict[str, Any]) -> None:
    levels = taxonomy.get("levels")
    if not isinstance(levels, list) or tuple(item.get("label") for item in levels) != LABELS:
        raise ValueError("Taxonomy must retain canonical labels High, Medium, Low, None")
    if taxonomy.get("compliance_consequence_is_separate") is not True:
        raise ValueError("Materiality must remain separate from compliance consequence")
    if not taxonomy.get("guideline_version"):
        raise ValueError("A versioned guideline is required")


def _stable_id(prefix: str, *values: object) -> str:
    return f"{prefix}_{sha256(chr(10).join(map(str, values)).encode()).hexdigest()[:24]}"
