"""Versioned read interface for downstream consumers (RAG, risk) of the temporal graph.

Consumers receive an explicit contract instead of a graph file path: the graph
version and hash, the version scope of any returned text, applicability status,
source evidence and abstention reasons. A fragment is never presented as a
complete consolidated provision, and weakly supported transitions abstain.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import load_json

from .temporal_graph import TemporalGraph, _normalise_for_match

INTERFACE_VERSION = "graph-consumer-v1"
SUPPORTED_GRAPH_SCHEMAS = frozenset({"2.0.0"})
SUPPORTED_GRAPH_VERSIONS = frozenset({"v3", "v4"})
STRONG_STATUS = "MACHINE_CROSS_SOURCE_CORROBORATED"


class IncompatibleGraphError(ValueError):
    pass


class GraphConsumer:
    def __init__(self, root: Path, graph_version: str = "v4") -> None:
        if graph_version not in SUPPORTED_GRAPH_VERSIONS:
            raise IncompatibleGraphError(f"{INTERFACE_VERSION} does not support graph {graph_version}")
        checkpoint = load_json(root / f"reports/phase3/temporal_graph_checkpoint.{graph_version}.json")
        path = root / str(checkpoint["graph_path"])
        payload = path.read_bytes()
        digest = sha256(payload).hexdigest()
        if checkpoint.get("engineering_status") != "passed" or digest != checkpoint.get("graph_sha256"):
            raise IncompatibleGraphError(f"graph {graph_version} does not match its passed checkpoint")
        self.graph = TemporalGraph.from_dict(json.loads(payload))
        if self.graph.schema_version not in SUPPORTED_GRAPH_SCHEMAS:
            raise IncompatibleGraphError(f"unsupported graph schema {self.graph.schema_version}")
        self.graph_version = graph_version
        self.graph_sha256 = digest

    def aligned_fragments(self, amending_entry_id: str, target_entry_id: str, instruction_text: str) -> dict[str, object] | None:
        """Before/after fragments of the one strongly corroborated transition whose clause appears in the text."""
        entry_by_source = {str(item["source_id"]): str(item["corpus_entry_id"]) for item in self.graph.legal_sources}
        act_entry = {str(item["act_id"]): str(item["corpus_entry_id"]) for item in self.graph.acts}
        provisions = {str(item["provision_id"]): item for item in self.graph.provisions}
        versions = {str(item["version_id"]): item for item in self.graph.provision_versions}
        events = {str(item["amendment_event_id"]): item for item in self.graph.amendment_events}
        haystack = _normalise_for_match(instruction_text)
        matches = []
        for transition in self.graph.transitions:
            if transition["validation_status"] != STRONG_STATUS:
                continue
            event = events[str(transition["amendment_event_id"])]
            provision = provisions[str(transition["target_provision_id"])]
            clause = _normalise_for_match(str(event["evidence"]["exact_text"]))[:120]
            if (entry_by_source.get(str(event["evidence"]["source_id"])) == amending_entry_id
                    and act_entry.get(str(provision["act_id"])) == target_entry_id
                    and len(clause) >= 40 and clause in haystack):
                matches.append((transition, event, provision))
        if len(matches) != 1:
            return None  # none or ambiguous: the caller abstains from version comparison
        transition, event, provision = matches[0]
        return {
            "interface_version": INTERFACE_VERSION,
            "graph_version": self.graph_version,
            "graph_sha256": self.graph_sha256,
            "transition_id": transition["transition_id"],
            "validation_status": transition["validation_status"],
            "section": provision["section"],
            "version_scope": "AMENDMENT_CONTROLLED_FRAGMENT",
            "is_complete_consolidated_text": False,
            "legal_validation": "UNVERIFIED",
            "before_text": versions[str(transition["before_version_id"])]["text"],
            "after_text": versions[str(transition["after_version_id"])]["text"],
            "effective_date": transition.get("effective_date"),
            "source_evidence": event["evidence"],
        }

    def provision_at(self, act: str, section: str, on_date: str) -> dict[str, object]:
        base = {
            "interface_version": INTERFACE_VERSION,
            "graph_version": self.graph_version,
            "graph_sha256": self.graph_sha256,
            "query": {"act": act, "section": section, "reference_date": on_date},
            # The graph dates amendment fragments; scenario applicability needs facts and review.
            "applicability_status": "NOT_DETERMINED_REQUIRES_SCENARIO_FACTS_AND_REVIEW",
            "legal_validation": "UNVERIFIED",
            "is_complete_consolidated_text": False,
        }
        try:
            result = self.graph.get_provision_version(act, section, on_date)
        except KeyError as error:
            return {**base, "status": "UNRESOLVED", "version_scope": None, "text": None,
                    "source_evidence": [], "abstention_reasons": [f"provision_not_in_graph: {error.args[0]}"]}
        if result["status"] != "RESOLVED_FRAGMENT":
            return {
                **base, "status": "UNRESOLVED", "version_scope": None, "text": None,
                "source_evidence": [item["source_evidence"] for item in result.get("unresolved_transitions", [])],
                "abstention_reasons": [str(result["reason"]), *sorted({
                    code for item in result.get("unresolved_transitions", []) for code in item["reason_codes"]
                })],
            }
        transition = result["transition"]
        evidence = {
            **result["amendment_event"]["evidence"],
            "source_url": result["source"]["source_url"],
            "retrieval_url": result["source"]["retrieval_url"],
        }
        if transition["validation_status"] != STRONG_STATUS:
            return {
                **base, "status": "UNRESOLVED", "version_scope": None, "text": None,
                "source_evidence": [evidence],
                "abstention_reasons": [f"transition_not_strongly_corroborated: {transition['validation_status']}"],
                "candidate_transition_id": transition["transition_id"],
            }
        version = result["version"]
        return {
            **base,
            "status": "FRAGMENT_SUPPORTED",
            "version_scope": version["text_scope"],
            "fragment_state": result["fragment_state"],
            "text": version["text"],
            "valid_from": version.get("valid_from"),
            "valid_to": version.get("valid_to"),
            "effective_date_basis": result["temporal_basis"],
            "transition_id": transition["transition_id"],
            "validation_status": transition["validation_status"],
            "source_evidence": [evidence],
            "corroborating_consolidated_version_ids": transition.get("corroborating_consolidated_version_ids", []),
            "abstention_reasons": [],
            "scope_warning": result["scope_warning"],
        }
