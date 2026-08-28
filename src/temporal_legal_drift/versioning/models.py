"""Evidence-linked Phase 3 graph contracts and invariants."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Iterable


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\n".join(parts).encode("utf-8")
    return f"{prefix}_{sha256(payload).hexdigest()[:24]}"


@dataclass(frozen=True)
class EvidenceReference:
    source_artifact_id: str
    source_sha256: str
    normalized_document_id: str
    block_id: str
    locator: str
    exact_text_sha256: str


@dataclass(frozen=True)
class LegalInstrument:
    instrument_id: str
    corpus_entry_id: str
    official_identifier: str
    instrument_type: str
    title: str
    source_artifact_id: str


@dataclass(frozen=True)
class ProvisionLineage:
    lineage_id: str
    instrument_id: str
    canonical_path: str
    provision_number: str
    title: str


@dataclass(frozen=True)
class ProvisionVersion:
    version_id: str
    lineage_id: str
    version_label: str
    exact_text: str
    exact_text_sha256: str
    evidence: EvidenceReference
    extraction_status: str = "machine_extracted_unreviewed"


@dataclass(frozen=True)
class AmendmentEvent:
    amendment_event_id: str
    amending_instrument_id: str
    target_lineage_id: str | None
    target_path_text: str
    operation: str
    evidence: EvidenceReference
    resolution_status: str


@dataclass(frozen=True)
class VersionTransition:
    transition_id: str
    before_version_id: str
    after_version_id: str
    amendment_event_id: str
    operation: str
    evidence: EvidenceReference


@dataclass(frozen=True)
class VersionGraph:
    instruments: tuple[LegalInstrument, ...]
    lineages: tuple[ProvisionLineage, ...]
    versions: tuple[ProvisionVersion, ...]
    amendment_events: tuple[AmendmentEvent, ...] = field(default_factory=tuple)
    transitions: tuple[VersionTransition, ...] = field(default_factory=tuple)
    unresolved: tuple[dict[str, object], ...] = field(default_factory=tuple)
    graph_status: str = "technical_reconstruction_not_legal_gold"
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "graph_status": self.graph_status,
            "instruments": [asdict(item) for item in self.instruments],
            "lineages": [asdict(item) for item in self.lineages],
            "versions": [asdict(item) for item in self.versions],
            "amendment_events": [asdict(item) for item in self.amendment_events],
            "transitions": [asdict(item) for item in self.transitions],
            "unresolved": list(self.unresolved),
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "VersionGraph":
        def evidence(raw: dict[str, object]) -> EvidenceReference:
            return EvidenceReference(**raw)  # type: ignore[arg-type]

        versions = []
        for raw in value.get("versions", []):  # type: ignore[assignment]
            item = dict(raw)
            item["evidence"] = evidence(item["evidence"])
            versions.append(ProvisionVersion(**item))
        events = []
        for raw in value.get("amendment_events", []):  # type: ignore[assignment]
            item = dict(raw)
            item["evidence"] = evidence(item["evidence"])
            events.append(AmendmentEvent(**item))
        transitions = []
        for raw in value.get("transitions", []):  # type: ignore[assignment]
            item = dict(raw)
            item["evidence"] = evidence(item["evidence"])
            transitions.append(VersionTransition(**item))
        return cls(
            instruments=tuple(LegalInstrument(**item) for item in value.get("instruments", [])),  # type: ignore[arg-type]
            lineages=tuple(ProvisionLineage(**item) for item in value.get("lineages", [])),  # type: ignore[arg-type]
            versions=tuple(versions),
            amendment_events=tuple(events),
            transitions=tuple(transitions),
            unresolved=tuple(value.get("unresolved", [])),  # type: ignore[arg-type]
            graph_status=str(value.get("graph_status", "")),
            schema_version=str(value.get("schema_version", "")),
        )

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        errors.extend(_duplicate_errors("instrument", (x.instrument_id for x in self.instruments)))
        errors.extend(_duplicate_errors("lineage", (x.lineage_id for x in self.lineages)))
        errors.extend(_duplicate_errors("version", (x.version_id for x in self.versions)))
        errors.extend(
            _duplicate_errors("amendment event", (x.amendment_event_id for x in self.amendment_events))
        )
        errors.extend(_duplicate_errors("transition", (x.transition_id for x in self.transitions)))

        instrument_ids = {item.instrument_id for item in self.instruments}
        lineage_ids = {item.lineage_id for item in self.lineages}
        version_ids = {item.version_id for item in self.versions}
        event_ids = {item.amendment_event_id for item in self.amendment_events}
        for lineage in self.lineages:
            if lineage.instrument_id not in instrument_ids:
                errors.append(f"orphan lineage {lineage.lineage_id}")
        for version in self.versions:
            if version.lineage_id not in lineage_ids:
                errors.append(f"orphan version {version.version_id}")
            if sha256(version.exact_text.encode("utf-8")).hexdigest() != version.exact_text_sha256:
                errors.append(f"text hash mismatch for {version.version_id}")
            if not version.evidence.source_artifact_id or not version.evidence.locator:
                errors.append(f"missing evidence for {version.version_id}")
        for event in self.amendment_events:
            if event.target_lineage_id is not None and event.target_lineage_id not in lineage_ids:
                errors.append(f"event {event.amendment_event_id} targets missing lineage")
        edges: dict[str, list[str]] = {}
        for transition in self.transitions:
            if transition.before_version_id not in version_ids or transition.after_version_id not in version_ids:
                errors.append(f"transition {transition.transition_id} references missing version")
            if transition.amendment_event_id not in event_ids:
                errors.append(f"transition {transition.transition_id} references missing event")
            edges.setdefault(transition.before_version_id, []).append(transition.after_version_id)
        if _has_cycle(version_ids, edges):
            errors.append("version graph contains a cycle")
        return tuple(errors)

    def reconstruct(self, version_id: str) -> ProvisionVersion:
        matches = [item for item in self.versions if item.version_id == version_id]
        if len(matches) != 1:
            raise KeyError(f"Expected one version for {version_id}, found {len(matches)}")
        return matches[0]

    def versions_for_lineage(self, lineage_id: str) -> tuple[ProvisionVersion, ...]:
        return tuple(item for item in self.versions if item.lineage_id == lineage_id)


def make_instrument_id(official_identifier: str) -> str:
    return _stable_id("ins", official_identifier)


def make_lineage_id(instrument_id: str, canonical_path: str) -> str:
    return _stable_id("lin", instrument_id, canonical_path)


def make_version_id(lineage_id: str, source_sha256: str, text_hash: str) -> str:
    return _stable_id("ver", lineage_id, source_sha256, text_hash)


def make_amendment_event_id(instrument_id: str, locator: str, target: str, operation: str) -> str:
    return _stable_id("amd", instrument_id, locator, target, operation)


def make_transition_id(before: str, after: str, event: str) -> str:
    return _stable_id("trn", before, after, event)


def _duplicate_errors(label: str, identifiers: Iterable[str]) -> list[str]:
    values = list(identifiers)
    return [f"duplicate {label} ID"] if len(values) != len(set(values)) else []


def _has_cycle(nodes: set[str], edges: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(neighbor) for neighbor in edges.get(node, [])):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in nodes)
