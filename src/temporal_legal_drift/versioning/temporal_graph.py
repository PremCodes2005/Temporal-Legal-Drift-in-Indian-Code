"""Phase 3 temporal legal knowledge graph built from evidence-constrained labels.

The graph keeps consolidated source snapshots separate from amendment-fragment
reconstructions.  This prevents a changed phrase from being misrepresented as a
complete historical provision.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.corpus import CorpusManifest
from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes, load_json

from .models import VersionGraph


RECONSTRUCTABLE_OPERATIONS = frozenset({"INSERT", "SUBSTITUTE", "OMIT", "REPLACE", "REPEAL"})
_GENERAL_COMMENCEMENT = re.compile(
    r"\b(?:this\s+act|it)\s+(?:shall\s+be\s+deemed\s+to\s+have\s+come|"
    r"shall\s+come)\s+into\s+force\s+on\s+the\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:\s+day\s+of)?\s+"
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)"
    r",?\s*(?P<year>\d{4})",
    re.I,
)
_PARTIAL_COMMENCEMENT = re.compile(
    r"\b(?:provisions?\s+of\s+sections?|different\s+dates|such\s+date\s+as\s+the\s+"
    r"(?:central\s+)?government\s+may|appointed\s+by\s+notification)\b",
    re.I,
)


def _id(prefix: str, *parts: object) -> str:
    return f"{prefix}_{sha256(chr(10).join(str(part) for part in parts).encode()).hexdigest()[:24]}"


@dataclass(frozen=True)
class TemporalGraph:
    legal_sources: tuple[dict[str, object], ...]
    acts: tuple[dict[str, object], ...]
    provisions: tuple[dict[str, object], ...]
    provision_versions: tuple[dict[str, object], ...]
    amendment_acts: tuple[dict[str, object], ...]
    amendment_events: tuple[dict[str, object], ...]
    commencement_events: tuple[dict[str, object], ...]
    transitions: tuple[dict[str, object], ...]
    unresolved_transitions: tuple[dict[str, object], ...]
    graph_status: str = "evidence_validated_technical_graph_not_legal_gold"
    schema_version: str = "2.0.0"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "TemporalGraph":
        return cls(
            legal_sources=tuple(value.get("legal_sources", [])),  # type: ignore[arg-type]
            acts=tuple(value.get("acts", [])),  # type: ignore[arg-type]
            provisions=tuple(value.get("provisions", [])),  # type: ignore[arg-type]
            provision_versions=tuple(value.get("provision_versions", [])),  # type: ignore[arg-type]
            amendment_acts=tuple(value.get("amendment_acts", [])),  # type: ignore[arg-type]
            amendment_events=tuple(value.get("amendment_events", [])),  # type: ignore[arg-type]
            commencement_events=tuple(value.get("commencement_events", [])),  # type: ignore[arg-type]
            transitions=tuple(value.get("transitions", [])),  # type: ignore[arg-type]
            unresolved_transitions=tuple(value.get("unresolved_transitions", [])),  # type: ignore[arg-type]
            graph_status=str(value.get("graph_status", "")),
            schema_version=str(value.get("schema_version", "")),
        )

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        collections = {
            "source": (self.legal_sources, "source_id"),
            "act": (self.acts, "act_id"),
            "provision": (self.provisions, "provision_id"),
            "version": (self.provision_versions, "version_id"),
            "amendment act": (self.amendment_acts, "amendment_act_id"),
            "amendment event": (self.amendment_events, "amendment_event_id"),
            "commencement event": (self.commencement_events, "commencement_event_id"),
            "transition": (self.transitions, "transition_id"),
        }
        identifiers: dict[str, set[str]] = {}
        for label, (items, key) in collections.items():
            values = [str(item.get(key, "")) for item in items]
            identifiers[label] = set(values)
            if "" in values or len(values) != len(set(values)):
                errors.append(f"invalid or duplicate {label} identifier")
        source_ids = identifiers["source"]
        act_ids = identifiers["act"]
        provision_ids = identifiers["provision"]
        version_ids = identifiers["version"]
        event_ids = identifiers["amendment event"]
        amendment_act_ids = identifiers["amendment act"]
        commencement_ids = identifiers["commencement event"]
        source_by_id = {str(item["source_id"]): item for item in self.legal_sources}
        provision_by_id = {str(item["provision_id"]): item for item in self.provisions}
        event_by_id = {str(item["amendment_event_id"]): item for item in self.amendment_events}
        for item in self.legal_sources:
            digest = str(item.get("sha256", ""))
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                errors.append(f"source {item.get('source_id')} has invalid SHA-256")
            if not str(item.get("source_url", "")).startswith("https://"):
                errors.append(f"source {item.get('source_id')} has invalid authoritative URL")
            if item.get("source_integrity_verified") is not True:
                errors.append(f"source {item.get('source_id')} integrity was not verified")
        for item in self.acts:
            if item.get("source_id") not in source_ids:
                errors.append(f"act {item.get('act_id')} has no legal source")
        for item in self.amendment_acts:
            if item.get("source_id") not in source_ids:
                errors.append(f"amendment act {item.get('amendment_act_id')} has no legal source")
        for item in self.provisions:
            if item.get("act_id") not in act_ids:
                errors.append(f"provision {item.get('provision_id')} has no Act")
        for item in self.provision_versions:
            if item.get("provision_id") not in provision_ids:
                errors.append(f"version {item.get('version_id')} has no provision")
            text = str(item.get("text", ""))
            if sha256(text.encode()).hexdigest() != item.get("text_sha256"):
                errors.append(f"version {item.get('version_id')} text hash mismatch")
            if not set(item.get("source_ids", [])) <= source_ids:
                errors.append(f"version {item.get('version_id')} has unknown source")
            if item.get("valid_from") and item.get("valid_to"):
                if date.fromisoformat(str(item["valid_from"])) >= date.fromisoformat(str(item["valid_to"])):
                    errors.append(f"version {item.get('version_id')} has invalid interval")
        edges: dict[str, list[str]] = {}
        for item in self.amendment_events:
            if item.get("amendment_act_id") not in amendment_act_ids:
                errors.append(f"event {item.get('amendment_event_id')} has no amending Act")
            if item.get("target_provision_id") and item.get("target_provision_id") not in provision_ids:
                errors.append(f"event {item.get('amendment_event_id')} has unknown target")
            evidence = item.get("evidence", {})
            source = source_by_id.get(str(evidence.get("source_id")))
            if source is None or source.get("sha256") != evidence.get("source_sha256"):
                errors.append(f"event {item.get('amendment_event_id')} source hash does not reconcile")
            if sha256(str(evidence.get("exact_text", "")).encode()).hexdigest() != evidence.get("exact_text_sha256"):
                errors.append(f"event {item.get('amendment_event_id')} evidence text hash mismatch")
            target = provision_by_id.get(str(item.get("target_provision_id")))
            if target and target.get("act_id") != item.get("principal_act_id"):
                errors.append(f"event {item.get('amendment_event_id')} principal Act conflicts with target provision")
        for item in self.commencement_events:
            if item.get("amendment_event_id") not in event_ids:
                errors.append(f"commencement {item.get('commencement_event_id')} has no event")
            if item.get("source_id") not in source_ids:
                errors.append(f"commencement {item.get('commencement_event_id')} has no source")
        for item in self.transitions:
            before = str(item.get("before_version_id", ""))
            after = str(item.get("after_version_id", ""))
            if before not in version_ids or after not in version_ids:
                errors.append(f"transition {item.get('transition_id')} has unknown version")
            if item.get("amendment_event_id") not in event_ids:
                errors.append(f"transition {item.get('transition_id')} has unknown event")
            if item.get("commencement_event_id") not in commencement_ids:
                errors.append(f"transition {item.get('transition_id')} has unknown commencement")
            before_version = next(
                (version for version in self.provision_versions if version.get("version_id") == before), None
            )
            after_version = next(
                (version for version in self.provision_versions if version.get("version_id") == after), None
            )
            if before_version and after_version:
                if before_version.get("provision_id") != after_version.get("provision_id"):
                    errors.append(f"transition {item.get('transition_id')} crosses provision identities")
                if item.get("target_provision_id") != before_version.get("provision_id"):
                    errors.append(f"transition {item.get('transition_id')} target does not match its versions")
            if item.get("operation") not in RECONSTRUCTABLE_OPERATIONS:
                errors.append(f"transition {item.get('transition_id')} has unsupported operation")
            if not set(item.get("source_ids", [])) <= source_ids:
                errors.append(f"transition {item.get('transition_id')} has unknown provenance source")
            event = event_by_id.get(str(item.get("amendment_event_id")))
            if event and event.get("target_provision_id") != item.get("target_provision_id"):
                errors.append(f"transition {item.get('transition_id')} target does not match event")
            if item.get("effective_date"):
                commencement = next(
                    (fact for fact in self.commencement_events
                     if fact.get("commencement_event_id") == item.get("commencement_event_id")), None
                )
                if commencement and commencement.get("effective_date") != item.get("effective_date"):
                    errors.append(f"transition {item.get('transition_id')} date disagrees with commencement evidence")
            edges.setdefault(before, []).append(after)
        if _has_cycle(version_ids, edges):
            errors.append("temporal graph contains a cycle")
        return tuple(dict.fromkeys(errors))

    def get_provision_version(self, act: str, section: str, on_date: str) -> dict[str, object]:
        query_date = date.fromisoformat(on_date)
        matching_acts = [
            item for item in self.acts
            if act.lower() in {
                str(item.get("act_id", "")).lower(),
                str(item.get("corpus_entry_id", "")).lower(),
                str(item.get("title", "")).lower(),
                str(item.get("official_identifier", "")).lower(),
            }
        ]
        if len(matching_acts) != 1:
            raise KeyError(f"Expected one Act for {act!r}, found {len(matching_acts)}")
        provision = next((
            item for item in self.provisions
            if item.get("act_id") == matching_acts[0]["act_id"]
            and str(item.get("section", "")).upper() == section.upper().removeprefix("SECTION:")
        ), None)
        if provision is None:
            raise KeyError(f"Section {section} was not found in {act}")
        transitions = [
            item for item in self.transitions
            if item.get("target_provision_id") == provision["provision_id"]
            and item.get("effective_date") is not None
        ]
        transitions.sort(key=lambda item: (str(item["effective_date"]), str(item["transition_id"])))
        if not transitions:
            return {
                "status": "UNRESOLVED",
                "reason": "no evidence-supported effective date for this provision transition",
                "act": matching_acts[0],
                "provision": provision,
                "reference_date": on_date,
            }
        applicable = [item for item in transitions if date.fromisoformat(str(item["effective_date"])) <= query_date]
        if len(applicable) > 1:
            applicable.sort(key=lambda item: (str(item["effective_date"]), str(item["transition_id"])))
            for previous, current in zip(applicable, applicable[1:]):
                previous_after = next(
                    version for version in self.provision_versions
                    if version["version_id"] == previous["after_version_id"]
                )
                current_before = next(
                    version for version in self.provision_versions
                    if version["version_id"] == current["before_version_id"]
                )
                if previous_after["text"] != current_before["text"]:
                    return {
                        "status": "UNRESOLVED",
                        "reason": "dated amendment fragments do not form a proven version chain",
                        "act": matching_acts[0],
                        "provision": provision,
                        "reference_date": on_date,
                        "candidate_transition_ids": [item["transition_id"] for item in applicable],
                    }
        chosen = applicable[-1] if applicable else transitions[0]
        version_id = chosen["after_version_id"] if applicable else chosen["before_version_id"]
        version = next(item for item in self.provision_versions if item["version_id"] == version_id)
        event = next(item for item in self.amendment_events if item["amendment_event_id"] == chosen["amendment_event_id"])
        return {
            "status": "RESOLVED_FRAGMENT",
            "reference_date": on_date,
            "act": matching_acts[0],
            "provision": provision,
            "version": version,
            "transition": chosen,
            "amendment_event": event,
            "source": next(
                item for item in self.legal_sources
                if item["source_id"] == event["evidence"]["source_id"]
            ),
            "sources": [
                item for item in self.legal_sources
                if item["source_id"] in chosen["source_ids"]
            ],
            "corroborating_consolidated_versions": [
                item for item in self.provision_versions
                if item["version_id"] in chosen.get("corroborating_consolidated_version_ids", [])
            ],
            "valid_from": version.get("valid_from"),
            "valid_to": version.get("valid_to"),
            "temporal_basis": chosen.get("date_basis"),
            "fragment_state": (
                "ABSENT_BEFORE_INSERTION"
                if chosen.get("operation") == "INSERT" and version["version_id"] == chosen["before_version_id"]
                else "AMENDMENT_CONTROLLED_TEXT"
            ),
            "scope_warning": (
                "The returned text is the amendment-controlled fragment, not a complete "
                "historical consolidation of the provision."
            ),
        }


class TemporalGraphBuilder:
    def build(self, root: Path) -> TemporalGraph:
        root = root.resolve()
        manifest = CorpusManifest.from_file(root / "configs/corpus/pilot_v1.json")
        report = load_json(root / "reports/corpus/india-code-temporal-pilot-v1.lock.json")
        base_graph = VersionGraph.from_dict(load_json(root / "data/interim/version_graph.v1.json"))
        extraction = load_json(root / "data/processed/amendments/v1/extraction.json")
        silver = load_json(root / "data/processed/amendments/v1/silver_labels.v1.json")
        report_by_entry = {
            str(item["entry_id"]): item for item in report.get("entries", []) if isinstance(item, dict)
        }
        integrity = _verify_all_source_hashes(root, report_by_entry)
        normalized_by_entry = {
            entry_id: load_json(root / "data/normalized" / f"{report_entry['normalized_document_id']}.json")
            for entry_id, report_entry in report_by_entry.items()
        }
        commencement_by_entry = {
            entry.entry_id: _general_commencement(normalized_by_entry[entry.entry_id])
            for entry in manifest.entries if entry.instrument_type == "amending_act"
        }
        entry_by_id = {entry.entry_id: entry for entry in manifest.entries}

        legal_sources = tuple(sorted((
            {
                "source_id": str(item["source_artifact_id"]),
                "corpus_entry_id": entry_id,
                "official_identifier": str(item["official_identifier"]),
                "source_url": str(item["parent_reference_url"]),
                "retrieval_url": str(item["request_url"]),
                "sha256": str(item["sha256"]),
                "normalized_document_id": str(item["normalized_document_id"]),
                "source_integrity_verified": integrity == len(report_by_entry),
            }
            for entry_id, item in report_by_entry.items()
        ), key=lambda item: str(item["source_id"])))

        principal_entries = [entry for entry in manifest.entries if entry.instrument_type != "amending_act"]
        amending_entries = [entry for entry in manifest.entries if entry.instrument_type == "amending_act"]
        acts = tuple(sorted((
            {
                "act_id": _id("act", entry.official_identifier),
                "corpus_entry_id": entry.entry_id,
                "official_identifier": entry.official_identifier,
                "title": _display_title(entry.entry_id),
                "source_id": str(report_by_entry[entry.entry_id]["source_artifact_id"]),
            }
            for entry in principal_entries
        ), key=lambda item: str(item["act_id"])))
        amendment_acts = tuple(sorted((
            {
                "amendment_act_id": _id("aact", entry.official_identifier),
                "corpus_entry_id": entry.entry_id,
                "official_identifier": entry.official_identifier,
                "title": _display_title(entry.entry_id),
                "source_id": str(report_by_entry[entry.entry_id]["source_artifact_id"]),
            }
            for entry in amending_entries
        ), key=lambda item: str(item["amendment_act_id"])))
        act_by_entry = {str(item["corpus_entry_id"]): item for item in acts}
        amendment_act_by_entry = {str(item["corpus_entry_id"]): item for item in amendment_acts}
        source_by_entry = {str(item["corpus_entry_id"]): item for item in legal_sources}

        base_instrument_by_id = {item.instrument_id: item for item in base_graph.instruments}
        provisions: list[dict[str, object]] = []
        provision_by_entry_section: dict[tuple[str, str], dict[str, object]] = {}
        for lineage in base_graph.lineages:
            instrument = base_instrument_by_id[lineage.instrument_id]
            if instrument.corpus_entry_id not in act_by_entry:
                continue
            provision = {
                "provision_id": _id("prov", act_by_entry[instrument.corpus_entry_id]["act_id"], lineage.canonical_path),
                "act_id": act_by_entry[instrument.corpus_entry_id]["act_id"],
                "canonical_path": lineage.canonical_path,
                "section": lineage.provision_number,
                "title": lineage.title,
            }
            provisions.append(provision)
            provision_by_entry_section[(instrument.corpus_entry_id, lineage.provision_number.upper())] = provision

        versions: list[dict[str, object]] = []
        base_lineage_by_id = {item.lineage_id: item for item in base_graph.lineages}
        for version in base_graph.versions:
            lineage = base_lineage_by_id[version.lineage_id]
            instrument = base_instrument_by_id[lineage.instrument_id]
            provision = provision_by_entry_section.get((instrument.corpus_entry_id, lineage.provision_number.upper()))
            if provision is None:
                continue
            versions.append({
                "version_id": _id("pver", provision["provision_id"], version.exact_text_sha256, "snapshot"),
                "provision_id": provision["provision_id"],
                "text": version.exact_text,
                "text_sha256": version.exact_text_sha256,
                "text_scope": "COMPLETE_CONSOLIDATED_SOURCE_SNAPSHOT",
                "valid_from": None,
                "valid_to": None,
                "temporal_status": "UNDATED_CONSOLIDATED_SNAPSHOT",
                "created_by_amendment_event_id": None,
                "derivation": "direct_source_extraction",
                "source_ids": [version.evidence.source_artifact_id],
            })

        phase2_events = {
            str(item["amendment_id"]): item
            for item in extraction.get("events", []) if isinstance(item, dict)
        }
        principal_mapping = _principal_mapping(amending_entries, principal_entries)
        labels = silver.get("labels", [])
        if not isinstance(labels, list):
            raise ValueError("silver label artifact must contain labels")
        label_by_event = {str(item["amendment_id"]): item for item in labels if isinstance(item, dict)}
        event_records: list[dict[str, object]] = []
        commencement_records: list[dict[str, object]] = []
        event_context: dict[str, tuple[dict[str, object], dict[str, object] | None]] = {}
        for amendment_id, raw_event in phase2_events.items():
            label = label_by_event.get(amendment_id, {})
            source_entry = str(raw_event["source_document"])
            field_status = label.get("field_status", {}) if isinstance(label, dict) else {}
            target_entry = (
                _resolve_target_entry(label, source_entry, principal_entries, principal_mapping)
                if field_status.get("principal_act") == "ACCEPTED"
                and field_status.get("target_provision") == "ACCEPTED"
                else None
            )
            section = str(raw_event.get("target_provision") or "").split(":")[-1].upper()
            target_provision = provision_by_entry_section.get((target_entry, section)) if target_entry else None
            graph_event_id = _id("aevent", amendment_id)
            label_status = str(label.get("label_status", "ABSTAIN"))
            act_commencement = commencement_by_entry.get(source_entry)
            event_record = {
                "amendment_event_id": graph_event_id,
                "phase2_amendment_id": amendment_id,
                "amendment_act_id": amendment_act_by_entry[source_entry]["amendment_act_id"],
                "principal_act_id": act_by_entry[target_entry]["act_id"] if target_entry else None,
                "target_provision_id": target_provision["provision_id"] if target_provision else None,
                "operation": label.get("operation") if label_status == "AUTO_ACCEPTED" else raw_event.get("operation"),
                "old_text": label.get("old_text") if label_status == "AUTO_ACCEPTED" else None,
                "new_text": label.get("new_text") if label_status == "AUTO_ACCEPTED" else None,
                # Never use Phase 2's document-wide date copied to each clause.
                # Re-derive only an unambiguous Act-wide commencement statement.
                "effective_date": act_commencement["effective_date"] if act_commencement and act_commencement["status"] == "ACT_WIDE_UNAMBIGUOUS" else None,
                "target_path_detail": _target_path_detail(str(raw_event["evidence_text"])),
                "resolution_status": (
                    "SILVER_EVIDENCE_RESOLVED" if label_status == "AUTO_ACCEPTED" and target_provision
                    else "UNRESOLVED"
                ),
                "evidence": {
                    "source_id": source_by_entry[source_entry]["source_id"],
                    "source_sha256": raw_event["source_sha256"],
                    "page": raw_event.get("source_page"),
                    "line": raw_event.get("source_line"),
                    "exact_text": raw_event["evidence_text"],
                    "exact_text_sha256": sha256(str(raw_event["evidence_text"]).encode()).hexdigest(),
                },
            }
            event_records.append(event_record)
            commencement_id = _id("comm", graph_event_id)
            commencement_records.append({
                "commencement_event_id": commencement_id,
                "amendment_event_id": graph_event_id,
                "effective_date": event_record["effective_date"],
                "temporal_facts": _temporal_facts(
                    act_commencement,
                    source_by_entry[source_entry],
                ),
                "retrospective_effect_status": "NOT_ASSESSED",
                "transitional_provision_status": "NOT_ASSESSED",
                "source_sha256": source_by_entry[source_entry]["sha256"],
                "status": (
                    "EFFECTIVE_DATE_EVIDENCED" if event_record["effective_date"]
                    else "COMMENCEMENT_UNRESOLVED"
                ),
                "source_id": source_by_entry[source_entry]["source_id"],
                "evidence_text": act_commencement.get("evidence_text") if act_commencement else None,
                "source_page": act_commencement.get("source_page") if act_commencement else None,
                "source_line": act_commencement.get("source_line") if act_commencement else None,
                "scope": act_commencement.get("scope") if act_commencement else "unknown_or_partial",
            })
            event_context[graph_event_id] = (event_record, target_provision)

        transition_candidates: list[tuple[dict[str, object], dict[str, object], str, str]] = []
        unresolved: list[dict[str, object]] = []
        for event_record, target_provision in event_context.values():
            reasons = []
            operation = str(event_record.get("operation"))
            old_text = event_record.get("old_text")
            new_text = event_record.get("new_text")
            if event_record.get("resolution_status") != "SILVER_EVIDENCE_RESOLVED":
                reasons.append("event_or_target_not_silver_resolved")
            if operation not in RECONSTRUCTABLE_OPERATIONS:
                reasons.append("operation_not_fragment_reconstructable")
            before, after = _fragments(operation, old_text, new_text)
            if before is None or after is None:
                reasons.append("required_fragment_wording_missing")
            if reasons or target_provision is None:
                unresolved.append(_unresolved_transition(event_record, reasons or ["target_provision_not_found"]))
                continue
            transition_candidates.append((event_record, target_provision, before, after))

        grouped: dict[tuple[str, str], list[tuple[dict[str, object], dict[str, object], str, str]]] = {}
        for candidate in transition_candidates:
            event = candidate[0]
            grouped.setdefault((str(event["amendment_act_id"]), str(candidate[1]["provision_id"])), []).append(candidate)

        transitions: list[dict[str, object]] = []
        for candidates in grouped.values():
            if len(candidates) != 1:
                for event_record, _, _, _ in candidates:
                    unresolved.append(_unresolved_transition(
                        event_record, ["compound_or_repeated_transition_requires_ordered_reconstruction"]
                    ))
                continue
            event_record, provision, before_text, after_text = candidates[0]
            operation = str(event_record["operation"])
            source_id = str(event_record["evidence"]["source_id"])
            before_id = _id("pver", provision["provision_id"], event_record["amendment_event_id"], "before")
            after_id = _id("pver", provision["provision_id"], event_record["amendment_event_id"], "after")
            effective_date = event_record.get("effective_date")
            versions.extend((
                {
                    "version_id": before_id,
                    "provision_id": provision["provision_id"],
                    "text": before_text,
                    "text_sha256": sha256(before_text.encode()).hexdigest(),
                    "text_scope": "AMENDMENT_CONTROLLED_FRAGMENT",
                    "valid_from": None,
                    "valid_to": effective_date,
                    "temporal_status": "UPPER_BOUND_EVIDENCED" if effective_date else "COMMENCEMENT_UNRESOLVED",
                    "created_by_amendment_event_id": None,
                    "derivation": "old_wording_from_amendment_instruction",
                    "source_ids": [source_id],
                },
                {
                    "version_id": after_id,
                    "provision_id": provision["provision_id"],
                    "text": after_text,
                    "text_sha256": sha256(after_text.encode()).hexdigest(),
                    "text_scope": "AMENDMENT_CONTROLLED_FRAGMENT",
                    "valid_from": effective_date,
                    "valid_to": None,
                    "temporal_status": "LOWER_BOUND_EVIDENCED" if effective_date else "COMMENCEMENT_UNRESOLVED",
                    "created_by_amendment_event_id": event_record["amendment_event_id"],
                    "derivation": "new_wording_from_amendment_instruction",
                    "source_ids": [source_id],
                },
            ))
            consolidated_versions = [
                item for item in versions
                if item.get("provision_id") == provision["provision_id"]
                and item.get("text_scope") == "COMPLETE_CONSOLIDATED_SOURCE_SNAPSHOT"
            ]
            after_supported_versions = [
                item for item in consolidated_versions
                if _normalise_for_match(after_text)
                and _normalise_for_match(after_text) in _normalise_for_match(str(item["text"]))
            ]
            checks = {
                "silver_label_auto_accepted": True,
                "target_provision_exists": True,
                "source_hash_verified": len(str(event_record["evidence"]["source_sha256"])) == 64,
                "old_new_fragments_reconstructable": True,
                "forward_operation_round_trip": _forward_round_trip(
                    operation, before_text, after_text, str(event_record["evidence"]["exact_text"])
                ),
                "after_fragment_matches_consolidated_principal_act": bool(after_supported_versions),
                "effective_date_evidenced": effective_date is not None,
                "human_legal_reviewed": False,
            }
            corroborating_source_ids = sorted({
                source_id,
                *(str(item["source_ids"][0]) for item in after_supported_versions if item.get("source_ids")),
            })
            transitions.append({
                "transition_id": _id("transition", before_id, after_id, event_record["amendment_event_id"]),
                "target_provision_id": provision["provision_id"],
                "before_version_id": before_id,
                "after_version_id": after_id,
                "amendment_event_id": event_record["amendment_event_id"],
                "commencement_event_id": _id("comm", event_record["amendment_event_id"]),
                "operation": operation,
                "effective_date": effective_date,
                "date_basis": (
                    "ACT_WIDE_COMMENCEMENT_NOT_SCENARIO_APPLICABILITY"
                    if effective_date else "UNRESOLVED"
                ),
                "validation_status": (
                    "MACHINE_CROSS_SOURCE_CORROBORATED"
                    if checks["after_fragment_matches_consolidated_principal_act"]
                    else "MACHINE_INTERNAL_CHECKS_ONLY"
                ),
                "validation_checks": checks,
                "source_ids": corroborating_source_ids,
                "corroborating_consolidated_version_ids": [item["version_id"] for item in after_supported_versions],
            })

        graph = TemporalGraph(
            legal_sources=legal_sources,
            acts=acts,
            provisions=tuple(sorted(provisions, key=lambda item: str(item["provision_id"]))),
            provision_versions=tuple(sorted(versions, key=lambda item: str(item["version_id"]))),
            amendment_acts=amendment_acts,
            amendment_events=tuple(sorted(event_records, key=lambda item: str(item["amendment_event_id"]))),
            commencement_events=tuple(sorted(commencement_records, key=lambda item: str(item["commencement_event_id"]))),
            transitions=tuple(sorted(transitions, key=lambda item: str(item["transition_id"]))),
            unresolved_transitions=tuple(sorted(unresolved, key=lambda item: str(item["unresolved_transition_id"]))),
        )
        errors = graph.validate()
        if errors:
            raise ValueError("Invalid temporal graph: " + "; ".join(errors))
        return graph


def write_temporal_graph_and_checkpoint(graph: TemporalGraph, root: Path) -> dict[str, object]:
    root = root.resolve()
    graph_path = root / "data/interim/temporal_legal_knowledge_graph.v2.json"
    payload = canonical_json_bytes(graph.to_dict())
    atomic_replace(graph_path, payload)
    fully_checked = [
        item for item in graph.transitions
        if all(
            value is True
            for key, value in item["validation_checks"].items()
            if key not in {"human_legal_reviewed", "effective_date_evidenced"}
        )
    ]
    dated = [item for item in fully_checked if item.get("effective_date")]
    validation_set = sorted(
        fully_checked,
        key=lambda item: (item.get("effective_date") is None, str(item["transition_id"])),
    )[:20]
    versions_by_id = {str(item["version_id"]): item for item in graph.provision_versions}
    events_by_id = {str(item["amendment_event_id"]): item for item in graph.amendment_events}
    sources_by_id = {str(item["source_id"]): item for item in graph.legal_sources}
    provisions_by_id = {str(item["provision_id"]): item for item in graph.provisions}
    validation_cases = []
    for transition in validation_set:
        event = events_by_id[str(transition["amendment_event_id"])]
        before = versions_by_id[str(transition["before_version_id"])]
        after = versions_by_id[str(transition["after_version_id"])]
        corroborating_versions = [
            versions_by_id[str(version_id)]
            for version_id in transition.get("corroborating_consolidated_version_ids", [])
        ]
        validation_cases.append({
            "transition": transition,
            "act": provisions_by_id[str(transition["target_provision_id"])],
            "before_version": before,
            "amendment_event": event,
            "after_version": after,
            "corroborating_consolidated_versions": corroborating_versions,
            "sources": [sources_by_id[source_id] for source_id in transition["source_ids"]],
            "human_review": {
                "status": "PENDING",
                "reviewer_id": None,
                "decision": None,
                "rationale": None,
                "reviewed_at": None,
            },
        })
    validation_document = {
        "schema_version": "1.0.0",
        "status": "machine_evidence_validated_human_legal_review_pending",
        "selection_policy": "20 deterministic cross-source cases, prioritising evidenced effective dates",
        "transition_count": len(validation_set),
        "manual_human_validation_count": 0,
        "machine_evidence_validation_count": len(validation_set),
        "independent_consolidated_text_corroboration_count": sum(
            item["transition"]["validation_checks"].get("after_fragment_matches_consolidated_principal_act") is True
            for item in validation_cases
        ),
        "manual_review_completed_count": 0,
        "cases": validation_cases,
    }
    validation_path = root / "data/interim/phase3_transition_validation_candidates.v1.json"
    validation_payload = canonical_json_bytes(validation_document)
    atomic_replace(validation_path, validation_payload)
    checks = {
        "all_seven_entity_types_present": all((
            graph.acts, graph.provisions, graph.provision_versions, graph.amendment_acts,
            graph.amendment_events, graph.legal_sources, graph.commencement_events,
        )),
        "all_100_documents_have_legal_sources": len(graph.legal_sources) == 100,
        "all_100_raw_and_normalized_source_hashes_recomputed": (
            len(graph.legal_sources) == 100
            and all(item.get("source_integrity_verified") is True for item in graph.legal_sources)
        ),
        "all_37_amending_acts_are_represented": len(graph.amendment_acts) == 37,
        "all_864_phase2_events_are_accounted_for": len(graph.amendment_events) == 864,
        "at_least_20_machine_evidence_validated_transitions": len(fully_checked) >= 20,
        "twenty_transition_validation_candidates_created": len(validation_set) == 20,
        "validation_candidate_ids_are_unique": (
            len({item["transition"]["transition_id"] for item in validation_cases}) == 20
        ),
        "before_after_versions_linked": all(
            item.get("before_version_id") and item.get("after_version_id") for item in graph.transitions
        ),
        "commencement_status_represented_for_every_event": (
            len(graph.commencement_events) == len(graph.amendment_events)
        ),
        "temporal_date_types_are_kept_distinct": all(
            {fact.get("fact_type") for fact in item.get("temporal_facts", [])}
            == {"commencement", "publication", "assent", "applicability", "legal_effect"}
            and item.get("retrospective_effect_status") == "NOT_ASSESSED"
            and item.get("transitional_provision_status") == "NOT_ASSESSED"
            for item in graph.commencement_events
        ),
        "commencement_not_mislabeled_as_scenario_applicability": all(
            item.get("date_basis") in {
                "ACT_WIDE_COMMENCEMENT_NOT_SCENARIO_APPLICABILITY", "UNRESOLVED"
            }
            for item in graph.transitions
        ),
        "unresolved_transitions_explicit": bool(graph.unresolved_transitions),
        "provenance_end_to_end": all(
            item.get("source_ids") and item.get("validation_checks", {}).get("source_hash_verified")
            for item in graph.transitions
        ),
        "graph_invariants_pass": not graph.validate(),
        "point_in_time_query_has_evidenced_examples": bool(dated),
        "selected_transitions_cross_source_corroborated": all(
            item["transition"]["validation_checks"].get("after_fragment_matches_consolidated_principal_act") is True
            for item in validation_cases
        ),
        "validation_cases_include_two_sources_and_review_fields": all(
            len(item["sources"]) >= 2
            and item["corroborating_consolidated_versions"]
            and item["before_version"].get("text_scope") == "AMENDMENT_CONTROLLED_FRAGMENT"
            and item["after_version"].get("text_scope") == "AMENDMENT_CONTROLLED_FRAGMENT"
            and item["human_review"].get("decision") is None
            and item["human_review"].get("status") == "PENDING"
            for item in validation_cases
        ),
        "no_false_human_validation_claim": validation_document["manual_human_validation_count"] == 0,
    }
    checkpoint = {
        "schema_version": "1.0.0",
        "phase": 3,
        "engineering_status": "passed" if all(checks.values()) else "failed",
        "scientific_gate_status": "pending_human_legal_validation",
        "checks": checks,
        "graph_path": str(graph_path.relative_to(root)),
        "graph_sha256": sha256(payload).hexdigest(),
        "validation_dataset_path": str(validation_path.relative_to(root)),
        "validation_dataset_sha256": sha256(validation_payload).hexdigest(),
        "counts": {
            "legal_sources": len(graph.legal_sources),
            "raw_and_normalized_source_hashes_recomputed": sum(
                item.get("source_integrity_verified") is True for item in graph.legal_sources
            ),
            "acts": len(graph.acts),
            "provisions": len(graph.provisions),
            "provision_versions": len(graph.provision_versions),
            "amendment_acts": len(graph.amendment_acts),
            "amendment_events": len(graph.amendment_events),
            "commencement_events": len(graph.commencement_events),
            "validated_transitions": len(fully_checked),
            "dated_transitions": len(dated),
            "unresolved_transitions": len(graph.unresolved_transitions),
            "human_validated_transitions": 0,
            "cross_source_corroborated_transitions": sum(
                item["validation_checks"].get("after_fragment_matches_consolidated_principal_act") is True
                and item["validation_checks"].get("forward_operation_round_trip") is True
                for item in graph.transitions
            ),
        },
        "claim_boundary": (
            "The graph contains evidence-validated amendment-fragment transitions. "
            "It does not claim complete historical consolidations or human legal validation."
        ),
    }
    checkpoint_path = root / "reports/phase3/temporal_graph_checkpoint.v2.json"
    atomic_replace(checkpoint_path, canonical_json_bytes(checkpoint))
    if checkpoint["engineering_status"] != "passed":
        raise ValueError("Phase 3 temporal graph engineering checkpoint failed")
    return checkpoint


def _principal_mapping(amending_entries: list[object], principal_entries: list[object]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for amendment in amending_entries:
        source_id = str(getattr(amendment, "entry_id"))
        ranked = sorted(
            ((_title_similarity(source_id, str(getattr(candidate, "entry_id"))), str(getattr(candidate, "entry_id")))
             for candidate in principal_entries),
            reverse=True,
        )
        if ranked and ranked[0][0] >= 0.5 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.1):
            mapping[source_id] = ranked[0][1]
    return mapping


def _resolve_target_entry(
    label: dict[str, object], source_entry: str, principal_entries: list[object], source_mapping: dict[str, str]
) -> str | None:
    principal = str(label.get("principal_act") or "")
    ranked = sorted(
        ((_title_similarity(principal, str(getattr(candidate, "entry_id"))), str(getattr(candidate, "entry_id")))
         for candidate in principal_entries),
        reverse=True,
    )
    if principal and ranked and ranked[0][0] >= 0.55 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.1):
        return ranked[0][1]
    return source_mapping.get(source_entry)


def _title_similarity(left: str, right: str) -> float:
    stop = {"amendment", "second", "validation", "and", "of", "the", "act", "code", "laws", "law", "consolidated"}
    left_tokens = {item for item in re.findall(r"[a-z]+", left.lower()) if item not in stop}
    right_tokens = {item for item in re.findall(r"[a-z]+", right.lower()) if item not in stop}
    if not left_tokens or not right_tokens:
        return 0.0
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence = SequenceMatcher(None, " ".join(sorted(left_tokens)), " ".join(sorted(right_tokens))).ratio()
    return round(0.75 * jaccard + 0.25 * sequence, 4)


def _display_title(entry_id: str) -> str:
    return " ".join(word.upper() if word in {"it", "rti", "gst"} else word.title() for word in entry_id.split("-"))


def _fragments(operation: str, old_text: object, new_text: object) -> tuple[str | None, str | None]:
    old = str(old_text) if old_text is not None else None
    new = str(new_text) if new_text is not None else None
    if operation in {"SUBSTITUTE", "REPLACE"} and old is not None and new is not None:
        return old, new
    if operation == "INSERT" and new is not None:
        return "", new
    if operation in {"OMIT", "REPEAL"} and old:
        return old, ""
    return None, None


def _forward_round_trip(operation: str, before: str, after: str, evidence: str) -> bool:
    normalized_evidence = _normalise_for_match(evidence)
    if before and _normalise_for_match(before) not in normalized_evidence:
        return False
    if after and _normalise_for_match(after) not in normalized_evidence:
        return False
    if operation in {"SUBSTITUTE", "REPLACE"}:
        cue = "substituted" if operation == "SUBSTITUTE" else "replaced"
        return bool(before) and bool(after) and before != after and bool(
            re.search(rf"\bshall\s+be\s+{cue}\b", evidence, re.I)
        )
    if operation == "INSERT":
        return before == "" and bool(after) and bool(re.search(r"\bshall\s+be\s+inserted\b", evidence, re.I))
    if operation in {"OMIT", "REPEAL"}:
        cue = "omitted" if operation == "OMIT" else "repealed"
        return bool(before) and after == "" and bool(
            re.search(rf"\bshall\s+be\s+{cue}\b", evidence, re.I)
        )
    return False


def _target_path_detail(text: str) -> str | None:
    section = re.search(r"\bin\s+section\s+(\d{1,3}[A-Z]{0,3})", text, re.I)
    if not section:
        return None
    parts = [f"section:{section.group(1).upper()}"]
    for label, pattern in (
        ("sub-section", r"\bin\s+sub-section\s*\(?([0-9A-Za-z]+)\)?"),
        # Word boundary after singular "clause" prevents "clauses" from
        # being misread as clause identifier "s" in multi-clause amendments.
        ("clause", r"\bin\s+clause\b\s*\(?([0-9A-Za-z]+)\)?"),
        ("sub-clause", r"\bin\s+sub-clause\s*\(?([0-9A-Za-z]+)\)?"),
        ("proviso", r"\bin\s+(?:the\s+)?(?:(\d+)(?:st|nd|rd|th)\s+)?proviso"),
    ):
        match = re.search(pattern, text, re.I)
        if match:
            value = next((group for group in match.groups() if group is not None), "1")
            parts.append(f"{label}:{value.lower()}")
    return "/".join(parts)


def _verify_all_source_hashes(root: Path, report_by_entry: dict[str, dict[str, object]]) -> int:
    verified = 0
    for entry_id, item in report_by_entry.items():
        expected = str(item.get("sha256", ""))
        raw_path = root / "data/raw" / str(item["blob_path"])
        if not raw_path.is_file() or sha256(raw_path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Raw legal source is missing or has a hash mismatch: {entry_id}")
        normalized_path = root / "data/normalized" / f"{item['normalized_document_id']}.json"
        normalized = load_json(normalized_path)
        if normalized.get("source_sha256") != expected:
            raise ValueError(f"Normalized legal source hash mismatch: {entry_id}")
        if normalized.get("source_artifact_id") != item.get("source_artifact_id"):
            raise ValueError(f"Normalized source artifact ID mismatch: {entry_id}")
        verified += 1
    return verified


def _unresolved_transition(event: dict[str, object], reasons: list[str]) -> dict[str, object]:
    return {
        "unresolved_transition_id": _id("unresolved_transition", event["amendment_event_id"], *reasons),
        "amendment_event_id": event["amendment_event_id"],
        "reason_codes": sorted(set(reasons)),
        "requires_review": True,
    }


def _general_commencement(document: dict[str, object]) -> dict[str, object] | None:
    blocks = document.get("blocks", [])
    all_text = "\n".join(
        str(block.get("normalized_text", ""))
        for block in blocks if isinstance(block, dict)
    )
    first_clause = _first_commencement_clause(all_text)
    matches = list(_GENERAL_COMMENCEMENT.finditer(first_clause))
    if len(matches) != 1:
        return None
    match = matches[0]
    if _PARTIAL_COMMENCEMENT.search(first_clause):
        return {
            "status": "PARTIAL_OR_DEFERRED_COMMENCEMENT",
            "effective_date": None,
            "evidence_text": match.group(0),
            "scope": "partial_or_deferred_scope_unresolved",
        }
    month_names = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )
    month = next(index for index, name in enumerate(month_names, 1) if name.lower() == match.group("month").lower())
    effective = date(int(match.group("year")), month, int(match.group("day"))).isoformat()
    offset = 0
    evidence = None
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = str(block.get("normalized_text", ""))
        local = _GENERAL_COMMENCEMENT.search(text)
        if local:
            page_match = re.search(r"page:(\d+)", str(block.get("source_anchor", "")))
            line = text[:local.start()].count("\n") + 1
            evidence = {
                "status": "ACT_WIDE_UNAMBIGUOUS",
                "effective_date": effective,
                "evidence_text": local.group(0),
                "source_page": int(page_match.group(1)) if page_match else None,
                "source_line": line,
                "scope": "whole_act_clause",
            }
            break
        offset += len(text)
    return evidence or {
        "status": "ACT_WIDE_UNAMBIGUOUS",
        "effective_date": effective,
        "evidence_text": match.group(0),
        "source_page": None,
        "source_line": None,
        "scope": "whole_act_clause",
    }


def _temporal_facts(
    commencement: dict[str, object] | None,
    source: dict[str, object],
) -> list[dict[str, object]]:
    """Preserve distinct legal date types without treating unknown dates as absent in law."""
    commencement_fact = {
        "fact_type": "commencement",
        "date_value": commencement.get("effective_date") if commencement else None,
        "status": (
            "EVIDENCED" if commencement and commencement.get("effective_date")
            else "UNRESOLVED"
        ),
        "scope": commencement.get("scope", "unknown_or_partial") if commencement else "unknown_or_partial",
        "source_id": source["source_id"],
        "source_sha256": source["sha256"],
        "evidence_text": commencement.get("evidence_text") if commencement else None,
        "source_page": commencement.get("source_page") if commencement else None,
        "source_line": commencement.get("source_line") if commencement else None,
    }
    additional_fact_types = ("publication", "assent", "applicability", "legal_effect")
    return [
        commencement_fact,
        *(
            {
                "fact_type": fact_type,
                "date_value": None,
                "status": "NOT_CAPTURED",
                "scope": "not_assessed_by_phase3_commencement_extractor",
                "source_id": source["source_id"],
                "source_sha256": source["sha256"],
                "evidence_text": None,
                "source_page": None,
                "source_line": None,
            }
            for fact_type in additional_fact_types
        ),
    ]


def _first_commencement_clause(text: str) -> str:
    start = re.search(r"(?m)^\s*1\.\s+", text)
    if start is None:
        return text[:5000]
    next_clause = re.search(r"(?m)^\s*2\.\s+", text[start.end():])
    end = start.end() + next_clause.start() if next_clause else min(len(text), start.start() + 5000)
    return text[start.start():end]


def _normalise_for_match(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.casefold()).split())


def _has_cycle(nodes: set[str], edges: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(neighbour) for neighbour in edges.get(node, [])):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in nodes)
