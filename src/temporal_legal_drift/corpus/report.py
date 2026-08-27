"""Deterministic reconciliation report for a downloaded and normalized corpus."""

from __future__ import annotations

from pathlib import Path

from temporal_legal_drift.acquisition import RawArtifactStore
from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes, load_json

from .manifest import CorpusManifest


def build_corpus_report(
    manifest: CorpusManifest,
    raw_store: RawArtifactStore,
    normalized_root: Path,
) -> dict[str, object]:
    checkpoint_path = raw_store.root / "checkpoints" / f"{manifest.manifest_id}.json"
    checkpoint = load_json(checkpoint_path)
    completed = checkpoint.get("completed")
    if not isinstance(completed, dict):
        raise ValueError(f"Invalid corpus checkpoint: {checkpoint_path}")

    normalized_by_source: dict[str, dict[str, object]] = {}
    for path in sorted(normalized_root.glob("doc_*.json")):
        value = load_json(path)
        source_artifact_id = value.get("source_artifact_id")
        if isinstance(source_artifact_id, str):
            normalized_by_source[source_artifact_id] = value

    entries: list[dict[str, object]] = []
    total_bytes = 0
    total_blocks = 0
    for entry in manifest.entries:
        source_artifact_id = completed.get(entry.entry_id)
        if not isinstance(source_artifact_id, str):
            raise ValueError(f"Missing downloaded artifact for {entry.entry_id}")
        artifact = raw_store.load_metadata(source_artifact_id)
        raw_store.verify(artifact)
        normalized = normalized_by_source.get(source_artifact_id)
        if normalized is None:
            raise ValueError(f"Missing normalized document for {entry.entry_id}")
        blocks = normalized.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError(f"Invalid normalized blocks for {entry.entry_id}")
        total_bytes += artifact.byte_length
        total_blocks += len(blocks)
        entries.append(
            {
                "entry_id": entry.entry_id,
                "research_role": entry.research_role,
                "known_extraction_risk": entry.known_extraction_risk,
                "official_identifier": artifact.official_identifier,
                "request_url": artifact.request_url,
                "parent_reference_url": artifact.parent_reference_url,
                "source_artifact_id": artifact.source_artifact_id,
                "sha256": artifact.sha256,
                "byte_length": artifact.byte_length,
                "media_type": artifact.media_type,
                "blob_path": artifact.blob_path,
                "normalized_document_id": normalized["normalized_document_id"],
                "parser_name": normalized["parser_name"],
                "parser_version": normalized["parser_version"],
                "normalized_block_count": len(blocks),
                "warnings": normalized.get("warnings", []),
            }
        )

    return {
        "schema_version": "1.0.0",
        "manifest_id": manifest.manifest_id,
        "manifest_status": manifest.status,
        "legal_validation_status": "not_reviewed",
        "entry_count": len(entries),
        "total_bytes": total_bytes,
        "total_normalized_blocks": total_blocks,
        "entries": entries,
    }


def write_corpus_report(path: Path, report: dict[str, object]) -> None:
    atomic_replace(path, canonical_json_bytes(report))
