"""Normalize every artifact referenced by a corpus checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from temporal_legal_drift.acquisition import RawArtifactStore
from temporal_legal_drift.jsonio import load_json
from temporal_legal_drift.parsing.service import NormalizationService

from .manifest import CorpusManifest


@dataclass(frozen=True)
class CorpusNormalizationSummary:
    manifest_id: str
    normalized_document_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "normalized_document_ids": list(self.normalized_document_ids),
        }


def normalize_corpus(
    manifest: CorpusManifest,
    raw_store: RawArtifactStore,
    service: NormalizationService,
) -> CorpusNormalizationSummary:
    checkpoint_path = raw_store.root / "checkpoints" / f"{manifest.manifest_id}.json"
    checkpoint = load_json(checkpoint_path)
    completed = checkpoint.get("completed")
    if not isinstance(completed, dict):
        raise ValueError(f"Invalid corpus checkpoint: {checkpoint_path}")

    document_ids: list[str] = []
    for entry in manifest.entries:
        source_artifact_id = completed.get(entry.entry_id)
        if not isinstance(source_artifact_id, str):
            raise ValueError(f"Corpus entry has not been downloaded: {entry.entry_id}")
        artifact = raw_store.load_metadata(source_artifact_id)
        raw_store.verify(artifact)
        document = service.normalize(artifact, raw_store.root)
        document_ids.append(document.normalized_document_id)
    return CorpusNormalizationSummary(manifest.manifest_id, tuple(document_ids))

