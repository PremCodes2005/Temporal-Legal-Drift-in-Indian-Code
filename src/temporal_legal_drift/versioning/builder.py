"""Build an evidence-linked technical version graph from normalized corpus snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.corpus import CorpusManifest
from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes, load_json

from .extract import (
    ExtractedProvision,
    extract_amendments,
    extract_amending_clauses,
    extract_provisions,
)
from .models import (
    AmendmentEvent,
    EvidenceReference,
    LegalInstrument,
    ProvisionLineage,
    ProvisionVersion,
    VersionGraph,
    make_amendment_event_id,
    make_instrument_id,
    make_lineage_id,
    make_version_id,
)


@dataclass(frozen=True)
class BuildSummary:
    graph_path: Path
    lock_path: Path
    instrument_count: int
    lineage_count: int
    version_count: int
    amendment_event_count: int
    transition_count: int
    unresolved_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "graph_path": str(self.graph_path),
            "lock_path": str(self.lock_path),
            "instrument_count": self.instrument_count,
            "lineage_count": self.lineage_count,
            "version_count": self.version_count,
            "amendment_event_count": self.amendment_event_count,
            "transition_count": self.transition_count,
            "unresolved_count": self.unresolved_count,
        }


class VersionGraphBuilder:
    def build(
        self,
        manifest: CorpusManifest,
        corpus_report: dict[str, object],
        normalized_root: Path,
        relation_config: dict[str, object] | None = None,
    ) -> VersionGraph:
        report_entries = corpus_report.get("entries")
        if not isinstance(report_entries, list):
            raise ValueError("Corpus report entries must be a list")
        report_by_entry = {str(item["entry_id"]): item for item in report_entries}
        relations = (relation_config or {}).get("amending_instrument_targets", {})
        if not isinstance(relations, dict):
            raise ValueError("amending_instrument_targets must be an object")

        instruments: list[LegalInstrument] = []
        lineages: list[ProvisionLineage] = []
        versions: list[ProvisionVersion] = []
        events: list[AmendmentEvent] = []
        unresolved: list[dict[str, object]] = []
        lineage_by_entry_number: dict[tuple[str, str], str] = {}
        extracted_by_entry: dict[str, tuple[object, ...]] = {}

        for entry in manifest.entries:
            report = report_by_entry.get(entry.entry_id)
            if not isinstance(report, dict):
                raise ValueError(f"Missing corpus report entry for {entry.entry_id}")
            document_path = normalized_root / f"{report['normalized_document_id']}.json"
            document = load_json(document_path)
            instrument_id = make_instrument_id(entry.official_identifier)
            instruments.append(
                LegalInstrument(
                    instrument_id,
                    entry.entry_id,
                    entry.official_identifier,
                    entry.instrument_type,
                    entry.entry_id.replace("-", " ").title(),
                    str(report["source_artifact_id"]),
                )
            )
            provisions, collisions = extract_provisions(document)
            if entry.instrument_type == "amending_act":
                amending_clauses = extract_amending_clauses(document)
                if amending_clauses:
                    provisions = amending_clauses
            # ``extract_provisions`` already collapses repeated section numbers, but the
            # amending-clause fallback does not. Two provisions with the same number would
            # produce an identical lineage id and fail the graph's uniqueness invariant, so
            # keep the longest-text candidate and escalate the rest instead of crashing.
            provisions, number_collisions = _dedupe_by_number(provisions)
            extracted_by_entry[entry.entry_id] = provisions
            for collision in (*collisions, *number_collisions):
                unresolved.append({"corpus_entry_id": entry.entry_id, **collision})
            if not provisions:
                unresolved.append(
                    {
                        "corpus_entry_id": entry.entry_id,
                        "reason_code": "no_section_boundaries_extracted",
                        "requires_review": True,
                    }
                )
            for provision in provisions:
                canonical_path = f"section:{provision.number}"
                lineage_id = make_lineage_id(instrument_id, canonical_path)
                lineage_by_entry_number[(entry.entry_id, provision.number)] = lineage_id
                lineages.append(
                    ProvisionLineage(
                        lineage_id,
                        instrument_id,
                        canonical_path,
                        provision.number,
                        provision.title,
                    )
                )
                evidence = EvidenceReference(
                    str(report["source_artifact_id"]),
                    str(report["sha256"]),
                    str(report["normalized_document_id"]),
                    provision.block_id,
                    provision.locator,
                    provision.text_hash,
                )
                versions.append(
                    ProvisionVersion(
                        make_version_id(lineage_id, str(report["sha256"]), provision.text_hash),
                        lineage_id,
                        "consolidated_source_snapshot",
                        provision.exact_text,
                        provision.text_hash,
                        evidence,
                    )
                )

        instrument_by_entry = {item.corpus_entry_id: item.instrument_id for item in instruments}
        for amending_entry, target_entry in relations.items():
            if amending_entry not in extracted_by_entry or target_entry not in instrument_by_entry:
                unresolved.append(
                    {
                        "corpus_entry_id": str(amending_entry),
                        "reason_code": "invalid_instrument_relation",
                        "target_entry_id": str(target_entry),
                        "requires_review": True,
                    }
                )
                continue
            report = report_by_entry[str(amending_entry)]
            amendments = extract_amendments(extracted_by_entry[str(amending_entry)])  # type: ignore[arg-type]
            for amendment in amendments:
                target_lineage = lineage_by_entry_number.get((str(target_entry), amendment.target_number))
                evidence = EvidenceReference(
                    str(report["source_artifact_id"]),
                    str(report["sha256"]),
                    str(report["normalized_document_id"]),
                    amendment.provision.block_id,
                    amendment.provision.locator,
                    amendment.provision.text_hash,
                )
                status = (
                    "candidate_target_linked_transition_unresolved"
                    if target_lineage
                    else "candidate_target_unresolved"
                )
                event_id = make_amendment_event_id(
                    instrument_by_entry[str(amending_entry)],
                    amendment.provision.locator,
                    amendment.target_number,
                    amendment.operation,
                )
                events.append(
                    AmendmentEvent(
                        event_id,
                        instrument_by_entry[str(amending_entry)],
                        target_lineage,
                        f"section:{amendment.target_number}",
                        amendment.operation,
                        evidence,
                        status,
                    )
                )
                unresolved.append(
                    {
                        "amendment_event_id": event_id,
                        "reason_code": "historical_before_after_pair_not_reconstructed",
                        "requires_review": True,
                    }
                )

        graph = VersionGraph(
            tuple(sorted(instruments, key=lambda item: item.instrument_id)),
            tuple(sorted(lineages, key=lambda item: item.lineage_id)),
            tuple(sorted(versions, key=lambda item: item.version_id)),
            tuple(sorted(events, key=lambda item: item.amendment_event_id)),
            (),
            tuple(unresolved),
        )
        errors = graph.validate()
        if errors:
            raise ValueError("Invalid version graph: " + "; ".join(errors))
        return graph


def _dedupe_by_number(
    provisions: tuple[ExtractedProvision, ...],
) -> tuple[tuple[ExtractedProvision, ...], list[dict[str, object]]]:
    """Keep one provision per section number; escalate the discarded candidates."""
    grouped: dict[str, list[ExtractedProvision]] = {}
    for provision in provisions:
        grouped.setdefault(provision.number, []).append(provision)
    # ``grouped`` keeps first-appearance order, which preserves downstream
    # extraction stability for the common no-collision case.
    selected: list[ExtractedProvision] = []
    collisions: list[dict[str, object]] = []
    for number, items in grouped.items():
        chosen = max(items, key=lambda item: len(item.exact_text))
        selected.append(chosen)
        if len(items) > 1:
            collisions.append(
                {
                    "reason_code": "duplicate_section_candidates",
                    "provision_number": number,
                    "selected_locator": chosen.locator,
                    "candidate_locators": [item.locator for item in items],
                    "requires_review": True,
                }
            )
    return tuple(selected), collisions


def write_graph_and_lock(graph: VersionGraph, graph_path: Path, lock_path: Path) -> BuildSummary:
    graph_payload = canonical_json_bytes(graph.to_dict())
    atomic_replace(graph_path, graph_payload)
    lock = {
        "schema_version": "1.0.0",
        "graph_status": graph.graph_status,
        "legal_validation_status": "not_reviewed",
        "graph_sha256": sha256(graph_payload).hexdigest(),
        "instrument_count": len(graph.instruments),
        "lineage_count": len(graph.lineages),
        "version_count": len(graph.versions),
        "amendment_event_count": len(graph.amendment_events),
        "transition_count": len(graph.transitions),
        "unresolved_count": len(graph.unresolved),
        "all_versions_have_evidence": all(
            bool(item.evidence.source_artifact_id and item.evidence.locator) for item in graph.versions
        ),
        "graph_validation_errors": list(graph.validate()),
    }
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return BuildSummary(
        graph_path,
        lock_path,
        len(graph.instruments),
        len(graph.lineages),
        len(graph.versions),
        len(graph.amendment_events),
        len(graph.transitions),
        len(graph.unresolved),
    )
