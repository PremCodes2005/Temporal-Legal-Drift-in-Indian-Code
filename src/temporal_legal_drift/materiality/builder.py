"""Build evidence-linked Phase 5 annotation tasks without inventing labels."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes
from temporal_legal_drift.versioning.models import VersionGraph


def build_annotation_workload(
    graph: VersionGraph,
    cross_validation: dict[str, object],
    taxonomy: dict[str, object],
    *,
    pilot_size: int = 50,
) -> dict[str, object]:
    if pilot_size < 1:
        raise ValueError("pilot_size must be positive")
    if taxonomy.get("role") != "intermediate_component":
        raise ValueError("Materiality taxonomy must remain an intermediate component")
    if taxonomy.get("compliance_consequence_is_separate") is not True:
        raise ValueError("Compliance consequence must remain separate from materiality")
    levels = taxonomy.get("levels")
    if not isinstance(levels, list) or [item.get("label") for item in levels] != [
        "High",
        "Medium",
        "Low",
        "None",
    ]:
        raise ValueError("Taxonomy must define High, Medium, Low, and None in canonical order")

    cross_results = cross_validation.get("results")
    if not isinstance(cross_results, list):
        raise ValueError("Cross-validation document requires results")
    cross_by_event = {
        str(item["amendment_event_id"]): item
        for item in cross_results
        if isinstance(item, dict) and item.get("amendment_event_id")
    }
    versions_by_lineage: dict[str, list[object]] = {}
    versions_by_text_hash = {item.exact_text_sha256: item for item in graph.versions}
    for version in graph.versions:
        versions_by_lineage.setdefault(version.lineage_id, []).append(version)

    ranked_events = sorted(
        graph.amendment_events,
        key=lambda item: (
            cross_by_event.get(item.amendment_event_id, {}).get("status") != "corroborated",
            item.amendment_event_id,
        ),
    )
    tasks: list[dict[str, object]] = []
    for event in ranked_events[:pilot_size]:
        instruction_version = versions_by_text_hash.get(event.evidence.exact_text_sha256)
        target_versions = versions_by_lineage.get(event.target_lineage_id or "", [])
        after_version = target_versions[0] if len(target_versions) == 1 else None
        reconstruction_status = (
            "missing_historical_before_version"
            if event.target_lineage_id and after_version is not None
            else "unresolved_target"
        )
        pair_id = _stable_id("pair", event.amendment_event_id)
        task = {
            "pair_id": pair_id,
            "amendment_event_id": event.amendment_event_id,
            "target_lineage_id": event.target_lineage_id,
            "operation": event.operation,
            "before_version_id": None,
            "after_version_id": after_version.version_id if after_version is not None else None,
            "before_text": None,
            "after_text": after_version.exact_text if after_version is not None else None,
            "amendment_instruction_text": (
                instruction_version.exact_text if instruction_version is not None else ""
            ),
            "reconstruction_status": reconstruction_status,
            "evidence": {
                "amendment": asdict(event.evidence),
                "after": asdict(after_version.evidence) if after_version is not None else None,
                "cross_validation_status": cross_by_event.get(event.amendment_event_id, {}).get(
                    "status", "not_evaluated"
                ),
            },
            "materiality": {"label": None, "dimensions": [], "status": "unannotated"},
            "compliance_consequence": None,
            "annotations": [],
            "required_independent_annotations": 2,
            "guideline_version": str(taxonomy.get("guideline_version", "")),
        }
        tasks.append(task)

    if len(tasks) != min(pilot_size, len(graph.amendment_events)):
        raise ValueError("Annotation workload count failed to reconcile")
    return {
        "schema_version": "1.0.0",
        "status": "annotation_workload_not_gold",
        "input_fingerprints": {
            "version_graph_sha256": sha256(canonical_json_bytes(graph.to_dict())).hexdigest(),
            "cross_validation_sha256": sha256(
                canonical_json_bytes(cross_validation)
            ).hexdigest(),
            "taxonomy_sha256": sha256(canonical_json_bytes(taxonomy)).hexdigest(),
        },
        "pilot_target": pilot_size,
        "guideline_version": taxonomy.get("guideline_version"),
        "taxonomy_status": taxonomy.get("status"),
        "tasks": tasks,
    }


def write_annotation_workload_and_lock(
    workload: dict[str, object], output_path: Path, lock_path: Path
) -> dict[str, object]:
    payload = canonical_json_bytes(workload)
    tasks = workload.get("tasks")
    fingerprints = workload.get("input_fingerprints")
    if not isinstance(tasks, list) or not isinstance(fingerprints, dict):
        raise ValueError("Annotation workload requires tasks")
    unique_ids = {str(task.get("pair_id")) for task in tasks if isinstance(task, dict)}
    lock = {
        "schema_version": "1.0.0",
        "status": "annotation_workload_not_gold",
        "workload_sha256": sha256(payload).hexdigest(),
        "input_fingerprints": fingerprints,
        "task_count": len(tasks),
        "unique_pair_count": len(unique_ids),
        "all_tasks_evidence_linked": all(
            isinstance(task, dict)
            and bool(task.get("evidence"))
            and bool(task.get("amendment_instruction_text"))
            for task in tasks
        ),
        "all_materiality_labels_unassigned": all(
            isinstance(task, dict)
            and isinstance(task.get("materiality"), dict)
            and task["materiality"].get("label") is None
            for task in tasks
        ),
        "compliance_consequence_separate": all(
            isinstance(task, dict) and task.get("compliance_consequence") is None
            for task in tasks
        ),
        "complete_before_after_pair_count": sum(
            isinstance(task, dict) and task.get("reconstruction_status") == "complete"
            for task in tasks
        ),
        "double_annotated_pair_count": sum(
            isinstance(task, dict) and len(task.get("annotations", [])) >= 2 for task in tasks
        ),
        "taxonomy_frozen": workload.get("taxonomy_status") == "frozen",
        "research_gate_passed": False,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{sha256(value.encode('utf-8')).hexdigest()[:24]}"
