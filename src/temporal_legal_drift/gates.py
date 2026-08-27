"""Executable engineering gates for the Phase 0-2 research foundation.

These checks deliberately do not impersonate research-lead or legal-review approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .acquisition import SourcePolicy
from .corpus import CorpusManifest
from .jsonio import load_json
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


def check_engineering_gates(root: Path) -> tuple[PhaseGateResult, ...]:
    """Return all Phase 0-2 engineering-gate results in order."""
    return (_phase0(root), _phase1(root), _phase2(root))
