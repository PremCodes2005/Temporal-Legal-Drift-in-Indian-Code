"""Executable engineering gates for the Phase 0-4 research foundation.

These checks deliberately do not impersonate research-lead or legal-review approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from .acquisition import SourcePolicy
from .applicability.models import TEMPORAL_FACT_TYPES
from .applicability.selfcheck import run_resolver_self_check
from .corpus import CorpusManifest
from .jsonio import canonical_json_bytes, load_json
from .phase0 import validate_contract_file


@dataclass(frozen=True)
class PhaseGateResult:
    phase: int
    engineering_passed: bool
    checks: dict[str, bool]
    review_status: str
    review_blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "engineering_passed": self.engineering_passed,
            "checks": self.checks,
            "review_status": self.review_status,
            "review_blockers": list(self.review_blockers),
        }


def _phase0(root: Path) -> PhaseGateResult:
    contract = validate_contract_file(root / "configs" / "research_contract.v1.json")
    checks = {
        "research_contract_structurally_valid": contract.structurally_valid,
        "terminology_registry_present": (root / "configs" / "terminology_registry.v1.json").is_file(),
        "temporal_semantics_registry_present": (
            root / "configs" / "temporal_semantics" / "registry.v1.json"
        ).is_file(),
        "novelty_audit_present": (root / "reports" / "phase0" / "novelty_audit.md").is_file(),
    }
    return PhaseGateResult(
        0,
        all(checks.values()),
        checks,
        "pending_qualified_review",
        contract.blockers,
    )


def _load_reconciled_corpus(root: Path) -> tuple[CorpusManifest, dict[str, object]]:
    manifest = CorpusManifest.from_file(root / "configs" / "corpus" / "pilot_v1.json")
    report = load_json(root / "reports" / "corpus" / f"{manifest.manifest_id}.lock.json")
    return manifest, report


def _phase1(root: Path) -> PhaseGateResult:
    manifest, report = _load_reconciled_corpus(root)
    policy = SourcePolicy.from_file(root / "configs" / "source_policy.v1.json")
    report_entries = report.get("entries")
    entries = report_entries if isinstance(report_entries, list) else []
    report_by_id = {
        entry.get("entry_id"): entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("entry_id"), str)
    }
    hosts_approved = all(
        (urlparse(entry.url).hostname or "").lower() in policy.approved_hosts
        for entry in manifest.entries
    )
    provenance_complete = all(
        isinstance(report_by_id.get(entry.entry_id), dict)
        and len(str(report_by_id[entry.entry_id].get("sha256", ""))) == 64
        and bool(report_by_id[entry.entry_id].get("official_identifier"))
        and bool(report_by_id[entry.entry_id].get("parent_reference_url"))
        for entry in manifest.entries
    )
    checks = {
        "bounded_manifest_valid": manifest.status == "bounded_technical_pilot_not_legal_gold",
        "all_manifest_hosts_approved": hosts_approved,
        "lock_report_matches_manifest": (
            report.get("manifest_id") == manifest.manifest_id
            and report.get("entry_count") == len(manifest.entries)
            and set(report_by_id) == {entry.entry_id for entry in manifest.entries}
        ),
        "provenance_fields_complete": provenance_complete,
    }
    return PhaseGateResult(
        1,
        all(checks.values()),
        checks,
        "pending_qualified_review",
        (
            "qualified reviewer has not accepted source sufficiency and temporal evidence",
            "redistribution constraints are not approved",
        ),
    )


def _phase2(root: Path) -> PhaseGateResult:
    manifest, report = _load_reconciled_corpus(root)
    report_entries = report.get("entries")
    entries = report_entries if isinstance(report_entries, list) else []
    parser_provenance = all(
        isinstance(entry, dict)
        and bool(entry.get("normalized_document_id"))
        and bool(entry.get("parser_name"))
        and bool(entry.get("parser_version"))
        and isinstance(entry.get("normalized_block_count"), int)
        and int(entry["normalized_block_count"]) > 0
        for entry in entries
    )
    manifest_risks = {entry.entry_id for entry in manifest.entries if entry.known_extraction_risk}
    reported_risks = {
        str(entry.get("entry_id"))
        for entry in entries
        if isinstance(entry, dict) and entry.get("known_extraction_risk")
    }
    block_counts = [
        int(entry["normalized_block_count"])
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("normalized_block_count"), int)
    ]
    checks = {
        "every_manifest_entry_normalized": len(entries) == len(manifest.entries),
        "parser_provenance_complete": parser_provenance,
        "normalized_block_total_reconciled": (
            len(block_counts) == len(entries)
            and report.get("total_normalized_blocks") == sum(block_counts)
        ),
        "known_extraction_risks_explicit": manifest_risks == reported_risks,
    }
    return PhaseGateResult(
        2,
        all(checks.values()),
        checks,
        "pending_fidelity_and_legal_review",
        (
            "authoritative hand-checked extraction fixtures are not approved",
            "the 2008 IT Amendment extraction requires OCR or manual fidelity review",
            "cross-reference and legal-structure fidelity are not expert validated",
        ),
    )


def _phase3(root: Path) -> PhaseGateResult:
    lock = load_json(root / "reports" / "phase3" / "version_graph.lock.json")
    manifest = CorpusManifest.from_file(root / "configs" / "corpus" / "pilot_v1.json")
    checks = {
        "version_graph_schema_present": (
            root / "schemas" / "temporal" / "version_graph.schema.json"
        ).is_file(),
        "at_least_fourteen_corpus_instruments": len(manifest.entries) >= 14,
        "all_corpus_instruments_reconciled": lock.get("instrument_count") == len(manifest.entries),
        "provision_lineages_and_versions_created": (
            isinstance(lock.get("lineage_count"), int)
            and int(lock["lineage_count"]) > 0
            and lock.get("lineage_count") == lock.get("version_count")
        ),
        "amendment_candidates_linked_or_escalated": (
            isinstance(lock.get("amendment_event_count"), int)
            and int(lock["amendment_event_count"]) > 0
            and isinstance(lock.get("unresolved_count"), int)
        ),
        "all_versions_have_evidence": lock.get("all_versions_have_evidence") is True,
        "graph_invariants_pass": lock.get("graph_validation_errors") == [],
    }
    return PhaseGateResult(
        3,
        all(checks.values()),
        checks,
        "pending_historical_reconstruction_legal_review",
        (
            "real historical before/after provision pairs are not yet legally validated",
            "candidate amendment links and duplicate section candidates require adjudication",
            "the real-corpus graph contains snapshots and unresolved events, not approved transitions",
        ),
    )


def _phase4(root: Path) -> PhaseGateResult:
    registry = load_json(root / "configs" / "temporal_semantics" / "registry.v1.json")
    candidate_lock = load_json(root / "reports" / "phase4" / "temporal_candidates.lock.json")
    cross_lock = load_json(root / "reports" / "phase4" / "cross_version_validation.lock.json")
    graph_lock = load_json(root / "reports" / "phase3" / "version_graph.lock.json")
    validation_config = load_json(root / "configs" / "validation" / "cross_version.v1.json")
    fingerprints = cross_lock.get("input_fingerprints")
    registry_types = registry.get("temporal_fact_types")
    checks = {
        "temporal_fact_schema_present": (
            root / "schemas" / "temporal" / "temporal_fact.schema.json"
        ).is_file(),
        "applicability_schema_present": (
            root / "schemas" / "temporal" / "applicability_determination.schema.json"
        ).is_file(),
        "cross_version_validation_schema_present": (
            root / "schemas" / "temporal" / "cross_version_validation.schema.json"
        ).is_file(),
        "temporal_registry_matches_code": (
            isinstance(registry_types, list) and set(registry_types) == set(TEMPORAL_FACT_TYPES)
        ),
        "resolver_engineering_self_check": run_resolver_self_check(),
        "ambiguity_policy_is_escalation": "unresolved" in str(registry.get("resolution_policy", "")),
        "real_corpus_temporal_candidates_extracted": (
            isinstance(candidate_lock.get("candidate_count"), int)
            and int(candidate_lock["candidate_count"]) > 0
        ),
        "real_candidates_cannot_silently_become_gold": (
            candidate_lock.get("all_candidates_unreviewed") is True
            and candidate_lock.get("approved_candidate_count") == 0
            and candidate_lock.get("all_candidates_have_evidence") is True
        ),
        "cross_source_counts_reconciled": cross_lock.get("counts_reconciled") is True,
        "cross_source_inputs_reconciled": (
            isinstance(fingerprints, dict)
            and fingerprints.get("version_graph_sha256") == graph_lock.get("graph_sha256")
            and fingerprints.get("temporal_facts_sha256")
            == candidate_lock.get("candidate_document_sha256")
            and fingerprints.get("validation_config_sha256")
            == sha256(canonical_json_bytes(validation_config)).hexdigest()
        ),
        "cross_source_evidence_complete": (
            cross_lock.get("all_corroborated_have_complete_evidence") is True
        ),
        "cross_source_technical_threshold_passed": (
            cross_lock.get("all_relations_meet_technical_threshold") is True
            and isinstance(cross_lock.get("corroborated_count"), int)
            and int(cross_lock["corroborated_count"]) > 0
        ),
        "cross_source_validation_does_not_claim_legal_review": (
            cross_lock.get("legal_validation_claimed") is False
            and cross_lock.get("independent_legal_review_status")
            == "not_performed_reviewer_unavailable"
        ),
    }
    return PhaseGateResult(
        4,
        all(checks.values()),
        checks,
        "internal_cross_source_validation_passed_external_legal_review_not_performed",
        (
            "independent legal review could not be performed because no reviewer is available",
            "no real applicability determination is approved as legal gold",
            "temporal hierarchy and scenario-specific conditions require qualified review",
            "compliance scenarios must not use unreviewed applicability results",
        ),
    )


def _phase5(root: Path) -> PhaseGateResult:
    lock = load_json(root / "reports" / "phase5" / "annotation_workload.lock.json")
    taxonomy = load_json(root / "configs" / "annotation" / "materiality_taxonomy.v1.json")
    graph_lock = load_json(root / "reports" / "phase3" / "version_graph.lock.json")
    cross_lock = load_json(root / "reports" / "phase4" / "cross_version_validation.lock.json")
    fingerprints = lock.get("input_fingerprints")
    labels = taxonomy.get("levels")
    checks = {
        "amendment_pair_schema_present": (
            root / "schemas" / "annotation" / "amendment_pair.schema.json"
        ).is_file(),
        "materiality_annotation_schema_present": (
            root / "schemas" / "annotation" / "materiality_annotation.schema.json"
        ).is_file(),
        "canonical_four_levels_defined": (
            isinstance(labels, list)
            and [item.get("label") for item in labels if isinstance(item, dict)]
            == ["High", "Medium", "Low", "None"]
        ),
        "taxonomy_definitions_and_adjudication_present": (
            isinstance(labels, list)
            and all(
                isinstance(item, dict)
                and all(
                    item.get(field)
                    for field in (
                        "definition",
                        "inclusion",
                        "exclusion",
                        "positive_patterns",
                        "negative_patterns",
                    )
                )
                for item in labels
            )
            and bool(taxonomy.get("boundary_rules"))
            and bool(taxonomy.get("adjudication_rules"))
        ),
        "materiality_and_consequence_separated": (
            taxonomy.get("compliance_consequence_is_separate") is True
            and lock.get("compliance_consequence_separate") is True
        ),
        "fifty_unique_annotation_tasks_created": (
            lock.get("task_count") == 50 and lock.get("unique_pair_count") == 50
        ),
        "all_tasks_evidence_linked": lock.get("all_tasks_evidence_linked") is True,
        "phase5_inputs_reconciled": (
            isinstance(fingerprints, dict)
            and fingerprints.get("version_graph_sha256") == graph_lock.get("graph_sha256")
            and fingerprints.get("cross_validation_sha256")
            == cross_lock.get("validation_sha256")
            and fingerprints.get("taxonomy_sha256")
            == sha256(canonical_json_bytes(taxonomy)).hexdigest()
        ),
        "machine_does_not_invent_materiality_gold": (
            lock.get("all_materiality_labels_unassigned") is True
            and lock.get("research_gate_passed") is False
        ),
    }
    return PhaseGateResult(
        5,
        all(checks.values()),
        checks,
        "technical_annotation_workload_passed_research_annotation_not_performed",
        (
            "no historical before/after pair is complete",
            "the 50 tasks have not received two independent annotations",
            "the ten-dimension draft and materiality guideline are not research-frozen",
            "no agreement or adjudication result exists",
        ),
    )


def _phase6(root: Path) -> PhaseGateResult:
    lock = load_json(root / "reports" / "phase6" / "scenario_scaffolds.lock.json")
    coverage = load_json(root / "configs" / "scenarios" / "coverage_requirements.v1.json")
    phase5_lock = load_json(root / "reports" / "phase5" / "annotation_workload.lock.json")
    cross_lock = load_json(root / "reports" / "phase4" / "cross_version_validation.lock.json")
    fingerprints = lock.get("input_fingerprints")
    checks = {
        "scenario_schema_present": (
            root / "schemas" / "scenario" / "compliance_scenario.schema.json"
        ).is_file(),
        "coverage_plan_present": bool(coverage.get("required_categories")),
        "evidence_linked_scaffolds_created": (
            isinstance(lock.get("scenario_count"), int)
            and int(lock["scenario_count"]) > 0
            and lock.get("scenario_count") == lock.get("unique_scenario_count")
            and lock.get("all_scaffolds_evidence_linked") is True
        ),
        "machine_does_not_invent_compliance_gold": (
            lock.get("no_expected_answers_invented") is True
            and lock.get("expert_validated_scenario_count") == 0
            and lock.get("research_gate_passed") is False
        ),
        "incomplete_coverage_reported": lock.get("coverage_complete") is False,
        "phase6_inputs_reconciled": (
            isinstance(fingerprints, dict)
            and fingerprints.get("annotation_workload_sha256")
            == phase5_lock.get("workload_sha256")
            and fingerprints.get("cross_validation_sha256")
            == cross_lock.get("validation_sha256")
            and fingerprints.get("coverage_config_sha256")
            == sha256(canonical_json_bytes(coverage)).hexdigest()
        ),
    }
    return PhaseGateResult(
        6,
        all(checks.values()),
        checks,
        "technical_scenario_scaffolds_passed_expert_scenarios_not_authored",
        (
            "scenario facts and legal questions are not authored",
            "expected answers, consequences and expected-change labels are unset",
            "required scenario-category coverage is not achieved",
            "independent scenario validation and adjudication are unavailable",
        ),
    )


def _phase7(root: Path) -> PhaseGateResult:
    lock = load_json(root / "reports" / "phase7" / "release.lock.json")
    phase5_lock = load_json(root / "reports" / "phase5" / "annotation_workload.lock.json")
    phase6_lock = load_json(root / "reports" / "phase6" / "scenario_scaffolds.lock.json")
    graph_lock = load_json(root / "reports" / "phase3" / "version_graph.lock.json")
    release_config = load_json(root / "configs" / "benchmark" / "release.v1.json")
    fingerprints = lock.get("input_checksums")
    checks = {
        "release_schema_present": (
            root / "schemas" / "evaluation" / "benchmark_release.schema.json"
        ).is_file(),
        "data_card_present": (root / "reports" / "phase7" / "data_card.md").is_file(),
        "release_counts_reconciled": lock.get("counts_reconciled") is True,
        "phase7_inputs_reconciled": (
            isinstance(fingerprints, dict)
            and fingerprints.get("annotation_workload_sha256")
            == phase5_lock.get("workload_sha256")
            and fingerprints.get("scenario_scaffolds_sha256")
            == phase6_lock.get("scenario_document_sha256")
            and fingerprints.get("version_graph_sha256") == graph_lock.get("graph_sha256")
            and fingerprints.get("release_config_sha256")
            == sha256(canonical_json_bytes(release_config)).hexdigest()
        ),
        "all_split_strategies_reported": lock.get("required_strategies_reported") is True,
        "feasible_splits_group_leakage_free": (
            lock.get("feasible_splits_group_leakage_free") is True
        ),
        "infeasible_splits_explicit": lock.get("infeasible_splits_explicit") is True,
        "redistribution_status_documented": bool(
            release_config.get("redistribution_status")
        ),
        "non_gold_release_cannot_freeze": (
            lock.get("freeze_refused_for_non_gold_inputs") is True
            and lock.get("benchmark_frozen") is False
            and lock.get("research_gate_passed") is False
        ),
    }
    return PhaseGateResult(
        7,
        all(checks.values()),
        checks,
        "technical_release_dry_run_passed_benchmark_not_frozen",
        (
            "materiality labels and complete historical pairs are unavailable",
            "expert-authored compliance scenarios are unavailable",
            "Act, temporal and domain holdouts are infeasible in the current pilot",
            "the scientific benchmark cannot be frozen from non-gold inputs",
        ),
    )


def check_engineering_gates(root: Path) -> tuple[PhaseGateResult, ...]:
    """Return all implemented engineering-gate results in order."""
    return (
        _phase0(root),
        _phase1(root),
        _phase2(root),
        _phase3(root),
        _phase4(root),
        _phase5(root),
        _phase6(root),
        _phase7(root),
    )
