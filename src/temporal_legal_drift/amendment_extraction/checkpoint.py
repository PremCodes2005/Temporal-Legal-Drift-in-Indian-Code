"""Phase 2 artifact writer and acceptance gate."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json

from .models import UNRESOLVED_REASONS
from .pipeline import AmendmentExtractionPipeline


def build_phase2_checkpoint(root: Path) -> dict[str, object]:
    root = root.resolve()
    pipeline = AmendmentExtractionPipeline(root)
    extraction = pipeline.run()
    frozen_baseline = load_json(root / "data/manifests/baseline.v0.1.json")
    output_path = root / "data/processed/amendments/v1/extraction.json"
    payload = canonical_json_bytes(extraction)
    atomic_write_new(output_path, payload)

    events = extraction["events"]
    unresolved = extraction["unresolved"]
    metrics = extraction["metrics"]
    controlled = metrics["controlled_fixture_accuracy"]
    accuracy_names = (
        "target_identification_accuracy",
        "operation_accuracy",
        "old_new_extraction_accuracy",
        "commencement_extraction_accuracy",
    )
    checks = {
        "all_configured_amending_acts_processed": (
            extraction["configured_amending_act_count"] == 37
            and extraction["processed_amending_act_count"] == 37
        ),
        "amendment_events_extracted": extraction["amendment_event_count"] > 0,
        "all_events_traceable_to_evidence": extraction["all_events_traceable"] is True,
        "every_document_accounted_for": extraction["every_document_accounted_for"] is True,
        "all_events_require_human_review": all(
            item.get("review_status") == "HUMAN_REVIEW_PENDING" for item in events
        ),
        "all_unresolved_records_are_classified": all(
            item.get("reason_code") in UNRESOLVED_REASONS
            and bool(item.get("evidence_text"))
            and item.get("review_status") == "HUMAN_REVIEW_REQUIRED"
            for item in unresolved
        ),
        "all_required_unresolved_categories_reported": (
            set(metrics["unresolved_reason_counts"]) == set(UNRESOLVED_REASONS)
        ),
        "controlled_fixture_accuracies_measured": all(
            controlled[name]["percent"] == 100.0 for name in accuracy_names
        ),
        "real_corpus_accuracy_not_fabricated": all(
            metrics["real_corpus_accuracy"][name] is None for name in accuracy_names
        ),
        "coverage_and_unresolved_metrics_measured": all(
            name in metrics
            for name in (
                "target_identification_coverage",
                "operation_resolution_coverage",
                "old_new_extraction_coverage",
                "commencement_extraction_coverage",
                "unresolved_event_rate",
            )
        ),
    }
    provenance = {
        "schema_version": "1.0.0",
        "extractor_version": extraction["extractor_version"],
        "artifact_path": str(output_path.relative_to(root)),
        "artifact_sha256": sha256(payload).hexdigest(),
        "configured_amending_act_count": extraction["configured_amending_act_count"],
        "amendment_event_count": extraction["amendment_event_count"],
        "unresolved_count": extraction["unresolved_count"],
        "frozen_v0_1_unresolved_record_count": frozen_baseline["unresolved_records"],
        "unresolved_count_comparability": (
            "Phase 2 counts reason records and may assign multiple reasons per event; "
            "it is not directly comparable to the frozen graph's 175 unresolved records."
        ),
        "metrics": metrics,
        "human_review_required": True,
        "legal_correctness_claimed": False,
    }
    atomic_write_new(
        root / "data/manifests/amendment_extraction_v1.provenance.json",
        canonical_json_bytes(provenance),
    )
    checkpoint = {
        "schema_version": "1.0.0",
        "phase": 2,
        "status": "passed" if all(checks.values()) else "failed",
        "deliverable": "generalised legal amendment extractor v1",
        "checks": checks,
        "artifact_sha256": provenance["artifact_sha256"],
        "configured_amending_act_count": extraction["configured_amending_act_count"],
        "amendment_event_count": extraction["amendment_event_count"],
        "unresolved_count": extraction["unresolved_count"],
        "frozen_v0_1_unresolved_record_count": frozen_baseline["unresolved_records"],
        "human_review_required": True,
        "legal_correctness_claimed": False,
    }
    atomic_write_new(
        root / "reports/phase2/amendment_extraction_checkpoint.v1.json",
        canonical_json_bytes(checkpoint),
    )
    if checkpoint["status"] != "passed":
        raise ValueError("Phase 2 checkpoint failed")
    return checkpoint
