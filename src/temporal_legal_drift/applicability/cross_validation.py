"""Automated cross-source amendment propagation checks for the technical pilot.

These checks corroborate internal consistency across authoritative artifacts. They
do not approve temporal facts, determine legal applicability, or replace review.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import date
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes
from temporal_legal_drift.versioning.models import VersionGraph

from .models import TemporalFact


STATUS = "automated_cross_source_consistency_not_legal_validation"


def validate_cross_source_consistency(
    graph: VersionGraph,
    facts: tuple[TemporalFact, ...],
    config: dict[str, object],
) -> dict[str, object]:
    """Corroborate amendment events against consolidated text and date evidence."""
    raw_relations = config.get("relations")
    if not isinstance(raw_relations, list) or not raw_relations:
        raise ValueError("Cross-version validation config requires relations")

    instruments_by_entry = {item.corpus_entry_id: item for item in graph.instruments}
    lineages = {item.lineage_id: item for item in graph.lineages}
    versions_by_lineage: dict[str, list[object]] = {}
    for version in graph.versions:
        versions_by_lineage.setdefault(version.lineage_id, []).append(version)
    facts_by_version: dict[str, list[TemporalFact]] = {}
    for fact in facts:
        facts_by_version.setdefault(fact.version_id, []).append(fact)

    results: list[dict[str, object]] = []
    relation_summaries: list[dict[str, object]] = []
    for raw_relation in raw_relations:
        if not isinstance(raw_relation, dict):
            raise ValueError("Cross-version relations must be objects")
        relation = raw_relation
        relation_id = _required_string(relation, "relation_id")
        amending_entry = _required_string(relation, "amending_entry_id")
        target_entry = _required_string(relation, "target_entry_id")
        citation_pattern = re.compile(
            _required_string(relation, "amending_act_citation_regex"), re.IGNORECASE
        )
        date_pattern = re.compile(
            _required_string(relation, "effective_date_text_regex"), re.IGNORECASE
        )
        expected_date = date.fromisoformat(_required_string(relation, "effective_date"))
        operation_cues = relation.get("operation_cues")
        if not isinstance(operation_cues, dict):
            raise ValueError(f"Relation {relation_id} requires operation_cues")
        minimum = relation.get("minimum_corroborated_events_for_technical_gate")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            raise ValueError(f"Relation {relation_id} requires a positive technical minimum")

        amending_instrument = instruments_by_entry.get(amending_entry)
        target_instrument = instruments_by_entry.get(target_entry)
        if amending_instrument is None or target_instrument is None:
            raise ValueError(f"Relation {relation_id} references a missing corpus instrument")

        relation_results: list[dict[str, object]] = []
        for event in graph.amendment_events:
            if event.amending_instrument_id != amending_instrument.instrument_id:
                continue
            target_versions = versions_by_lineage.get(event.target_lineage_id or "", [])
            target_version = target_versions[0] if len(target_versions) == 1 else None
            target_lineage = lineages.get(event.target_lineage_id or "")
            target_belongs_to_instrument = bool(
                target_lineage and target_lineage.instrument_id == target_instrument.instrument_id
            )
            target_text = target_version.exact_text if target_version is not None else ""
            operation_pattern = operation_cues.get(event.operation)
            operation_supported = bool(
                isinstance(operation_pattern, str)
                and re.search(operation_pattern, target_text, re.IGNORECASE)
            )
            matching_facts = tuple(
                fact
                for fact in facts_by_version.get(
                    target_version.version_id if target_version is not None else "", []
                )
                if fact.effective_date == expected_date
                and fact.fact_type in {"commencement", "legal_effect", "partial_commencement"}
            )
            checks = {
                "target_lineage_linked": event.target_lineage_id is not None,
                "target_belongs_to_configured_instrument": target_belongs_to_instrument,
                "exactly_one_target_snapshot": target_version is not None,
                "amending_act_citation_present": bool(citation_pattern.search(target_text)),
                "operation_cue_present": operation_supported,
                "effective_date_text_present": bool(date_pattern.search(target_text)),
                "effective_date_candidate_present": bool(matching_facts),
                "two_distinct_source_artifacts": bool(
                    target_version is not None
                    and event.evidence.source_artifact_id
                    != target_version.evidence.source_artifact_id
                ),
            }
            corroborated = all(checks.values())
            failure_reasons = [name for name, passed in checks.items() if not passed]
            target_version_id = target_version.version_id if target_version is not None else None
            validation_id = _validation_id(relation_id, event.amendment_event_id, target_version_id)
            result = {
                "validation_id": validation_id,
                "relation_id": relation_id,
                "amendment_event_id": event.amendment_event_id,
                "status": "corroborated" if corroborated else "unresolved",
                "checks": checks,
                "evidence": {
                    "amendment_event": asdict(event.evidence),
                    "target_version": asdict(target_version.evidence)
                    if target_version is not None
                    else None,
                    "target_version_id": target_version_id,
                    "temporal_fact_ids": [fact.fact_id for fact in matching_facts],
                    "expected_effective_date": expected_date.isoformat(),
                },
                "failure_reasons": failure_reasons,
            }
            results.append(result)
            relation_results.append(result)

        corroborated_count = sum(item["status"] == "corroborated" for item in relation_results)
        relation_summaries.append(
            {
                "relation_id": relation_id,
                "event_count": len(relation_results),
                "corroborated_count": corroborated_count,
                "unresolved_count": len(relation_results) - corroborated_count,
                "minimum_corroborated_events_for_technical_gate": minimum,
                "technical_threshold_passed": corroborated_count >= minimum,
            }
        )

    return {
        "schema_version": "1.0.0",
        "status": STATUS,
        "input_fingerprints": {
            "version_graph_sha256": sha256(canonical_json_bytes(graph.to_dict())).hexdigest(),
            "temporal_facts_sha256": sha256(
                canonical_json_bytes(
                    {
                        "schema_version": "1.0.0",
                        "status": "machine_extracted_candidates_not_legal_gold",
                        "facts": [fact.to_dict() for fact in facts],
                    }
                )
            ).hexdigest(),
            "validation_config_sha256": sha256(canonical_json_bytes(config)).hexdigest(),
        },
        "results": sorted(results, key=lambda item: str(item["validation_id"])),
        "relation_summaries": relation_summaries,
    }


def write_cross_validation_and_lock(
    validation: dict[str, object],
    output_path: Path,
    lock_path: Path,
) -> dict[str, object]:
    payload = canonical_json_bytes(validation)
    results = validation.get("results")
    summaries = validation.get("relation_summaries")
    fingerprints = validation.get("input_fingerprints")
    if (
        not isinstance(results, list)
        or not isinstance(summaries, list)
        or not isinstance(fingerprints, dict)
    ):
        raise ValueError("Invalid cross-version validation document")
    corroborated = [item for item in results if item.get("status") == "corroborated"]
    unresolved = [item for item in results if item.get("status") == "unresolved"]
    lock = {
        "schema_version": "1.0.0",
        "status": STATUS,
        "validation_sha256": sha256(payload).hexdigest(),
        "input_fingerprints": fingerprints,
        "event_count": len(results),
        "corroborated_count": len(corroborated),
        "unresolved_count": len(unresolved),
        "counts_reconciled": len(results) == len(corroborated) + len(unresolved),
        "all_corroborated_have_complete_evidence": all(
            bool(item.get("evidence")) and all(item.get("checks", {}).values())
            for item in corroborated
        ),
        "all_relations_meet_technical_threshold": bool(summaries)
        and all(item.get("technical_threshold_passed") is True for item in summaries),
        "legal_validation_claimed": False,
        "independent_legal_review_status": "not_performed_reviewer_unavailable",
        "relation_summaries": summaries,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _required_string(value: dict[str, object], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"Required non-empty string missing: {key}")
    return raw


def _validation_id(relation_id: str, event_id: str, version_id: str | None) -> str:
    payload = "\n".join([relation_id, event_id, version_id or "unresolved"]).encode("utf-8")
    return f"xval_{sha256(payload).hexdigest()[:24]}"
