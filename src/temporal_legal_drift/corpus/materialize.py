"""Create human-readable local copies of integrity-checked corpus PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from temporal_legal_drift.acquisition import RawArtifactStore
from temporal_legal_drift.jsonio import (
    atomic_replace,
    atomic_write_new,
    canonical_json_bytes,
    load_json,
)

from .manifest import CorpusManifest


@dataclass(frozen=True)
class MaterializationSummary:
    manifest_id: str
    materialized: tuple[str, ...]
    skipped: tuple[str, ...]
    output_directory: Path
    index_path: Path
    total_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "materialized": list(self.materialized),
            "skipped": list(self.skipped),
            "output_directory": str(self.output_directory),
            "index_path": str(self.index_path),
            "total_bytes": self.total_bytes,
        }


def materialize_corpus(
    manifest: CorpusManifest,
    raw_store: RawArtifactStore,
    output_directory: Path,
) -> MaterializationSummary:
    """Copy downloaded PDFs to stable readable names without altering raw evidence."""
    checkpoint_path = raw_store.root / "checkpoints" / f"{manifest.manifest_id}.json"
    checkpoint = load_json(checkpoint_path)
    if checkpoint.get("manifest_id") != manifest.manifest_id:
        raise ValueError(f"Checkpoint manifest mismatch in {checkpoint_path}")
    completed = checkpoint.get("completed")
    if not isinstance(completed, dict):
        raise ValueError(f"Checkpoint completed field must be an object in {checkpoint_path}")

    materialized: list[str] = []
    skipped: list[str] = []
    index_entries: list[dict[str, object]] = []
    total_bytes = 0

    for entry in manifest.entries:
        artifact_id = completed.get(entry.entry_id)
        if not isinstance(artifact_id, str):
            raise ValueError(
                f"Corpus entry {entry.entry_id} has not been downloaded in {checkpoint_path}"
            )
        artifact = raw_store.load_metadata(artifact_id)
        raw_store.verify(artifact)
        if artifact.corpus_entry_id != entry.entry_id:
            raise ValueError(
                f"Checkpoint entry {entry.entry_id} points to mismatched artifact {artifact_id}"
            )
        if artifact.media_type.split(";", 1)[0].strip().lower() != "application/pdf":
            raise ValueError(f"Corpus entry {entry.entry_id} is not stored as a PDF")

        source = raw_store.root / artifact.blob_path
        target = output_directory / f"{entry.entry_id}.pdf"
        existed = target.exists()
        atomic_write_new(target, source.read_bytes())
        if existed:
            skipped.append(entry.entry_id)
        else:
            materialized.append(entry.entry_id)
        total_bytes += artifact.byte_length
        index_entries.append(
            {
                "entry_id": entry.entry_id,
                "filename": target.name,
                "official_identifier": entry.official_identifier,
                "source_url": entry.url,
                "parent_reference_url": entry.parent_reference_url,
                "source_artifact_id": artifact.source_artifact_id,
                "sha256": artifact.sha256,
                "byte_length": artifact.byte_length,
            }
        )

    index_path = output_directory.parent / "index.json"
    index = {
        "schema_version": "1.0.0",
        "manifest_id": manifest.manifest_id,
        "manifest_status": manifest.status,
        "notice": (
            "Readable local copies of verified raw evidence; this index does not imply "
            "legal validation or benchmark-gold status."
        ),
        "entries": index_entries,
        "total_documents": len(index_entries),
        "total_bytes": total_bytes,
    }
    atomic_replace(index_path, canonical_json_bytes(index))
    return MaterializationSummary(
        manifest.manifest_id,
        tuple(materialized),
        tuple(skipped),
        output_directory,
        index_path,
        total_bytes,
    )
