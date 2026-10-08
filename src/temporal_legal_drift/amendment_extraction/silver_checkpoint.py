"""Build an immutable silver-label release without altering Phase 2 v1 extraction."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json

from .silver import build_silver_label, silver_metrics


def build_silver_label_checkpoint(root: Path) -> dict[str, object]:
    root = root.resolve()
    extraction_path = root / "data/processed/amendments/v1/extraction.json"
    extraction = load_json(extraction_path)
    report = load_json(root / "reports/corpus/india-code-temporal-pilot-v1.lock.json")
    text_by_source = _document_text_by_source(root, report)
    raw_events = extraction.get("events", [])
    if not isinstance(raw_events, list) or not all(isinstance(item, dict) for item in raw_events):
        raise ValueError("Phase 2 extraction artifact does not contain event objects")

    labels = [
        build_silver_label(event, text_by_source.get(str(event.get("source_document")), "")).to_dict()
        for event in raw_events
    ]
    metrics = silver_metrics(labels)
    artifact = {
        "schema_version": "1.0.0",
        "labelling_version": "amendment-silver-labeller-v1",
        "source_extraction_path": str(extraction_path.relative_to(root)),
        "source_extraction_sha256": sha256(extraction_path.read_bytes()).hexdigest(),
        "label_semantics": "machine_generated_silver_labels_not_legal_gold",
        "ground_truth_status": "UNVALIDATED",
        "accuracy_claimed": False,
        "policy": (
            "accept only evidence-supported fields with independent rule agreement; "
            "otherwise abstain"
        ),
        "metrics": metrics,
        "labels": labels,
    }
    output = root / "data/processed/amendments/v1/silver_labels.v1.json"
    payload = canonical_json_bytes(artifact)
    atomic_write_new(output, payload)

    checks = {
        "one_label_decision_per_extracted_event": len(labels) == len(raw_events),
        "all_labels_reference_known_events": (
            {str(item["amendment_id"]) for item in labels}
            == {str(item["amendment_id"]) for item in raw_events}
        ),
        "all_accepted_labels_are_evidence_constrained": all(
            item.get("validator_checks", {}).get("source_evidence_present") is True
            and item.get("validator_checks", {}).get("principal_act_document_supported") is True
            and item.get("validator_checks", {}).get("target_rule_agreement") is True
            and item.get("validator_checks", {}).get("operation_rule_agreement") is True
            and item.get("validator_checks", {}).get("required_wording_complete") is True
            for item in labels if item.get("label_status") == "AUTO_ACCEPTED"
        ),
        "all_disagreements_abstain": all(
            item.get("label_status") == "ABSTAIN"
            for item in labels
            if not (
                item.get("validator_checks", {}).get("principal_act_document_supported")
                and item.get("validator_checks", {}).get("target_rule_agreement")
                and item.get("validator_checks", {}).get("operation_rule_agreement")
                and item.get("validator_checks", {}).get("required_wording_complete")
            )
        ),
        "coverage_and_abstention_reported": (
            metrics.get("auto_label_coverage", {}).get("denominator") == len(labels)
            and metrics.get("abstention_rate", {}).get("denominator") == len(labels)
        ),
        "accuracy_not_mislabeled": artifact["accuracy_claimed"] is False,
        "source_extraction_unchanged": (
            artifact["source_extraction_sha256"] == sha256(extraction_path.read_bytes()).hexdigest()
        ),
    }
    checkpoint = {
        "schema_version": "1.0.0",
        "phase": 2,
        "deliverable": "evidence-constrained amendment silver labels v1",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "artifact_path": str(output.relative_to(root)),
        "artifact_sha256": sha256(payload).hexdigest(),
        "metrics": metrics,
        "legal_gold_created": False,
        "human_validation_still_required_for_accuracy": True,
    }
    atomic_write_new(
        root / "reports/phase2/silver_label_checkpoint.v1.json",
        canonical_json_bytes(checkpoint),
    )
    if checkpoint["status"] != "passed":
        raise ValueError("Phase 2 silver-label checkpoint failed")
    return checkpoint


def _document_text_by_source(root: Path, report: dict[str, object]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in report.get("entries", []):
        if not isinstance(item, dict):
            continue
        entry_id = item.get("entry_id")
        normalized_id = item.get("normalized_document_id")
        if not entry_id or not normalized_id:
            continue
        document = load_json(root / "data/normalized" / f"{normalized_id}.json")
        values[str(entry_id)] = "\n".join(
            str(block.get("normalized_text", ""))
            for block in document.get("blocks", []) if isinstance(block, dict)
        )
    return values
