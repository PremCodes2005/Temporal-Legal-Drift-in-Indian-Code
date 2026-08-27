"""Resumable corpus download with immutable artifacts and mutable checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from temporal_legal_drift.acquisition import AcquisitionService, RawArtifactStore
from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes, load_json

from .manifest import CorpusManifest


@dataclass(frozen=True)
class DownloadSummary:
    manifest_id: str
    downloaded: tuple[str, ...]
    skipped: tuple[str, ...]
    checkpoint_path: Path
    artifact_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "downloaded": list(self.downloaded),
            "skipped": list(self.skipped),
            "checkpoint_path": str(self.checkpoint_path),
            "artifact_ids": list(self.artifact_ids),
        }


class CorpusDownloader:
    checkpoint_schema_version = "1.0.0"

    def __init__(self, acquisition: AcquisitionService, store: RawArtifactStore) -> None:
        self.acquisition = acquisition
        self.store = store

    def checkpoint_path(self, manifest: CorpusManifest) -> Path:
        return self.store.root / "checkpoints" / f"{manifest.manifest_id}.json"

    def download(self, manifest: CorpusManifest, *, refresh: bool = False) -> DownloadSummary:
        checkpoint_path = self.checkpoint_path(manifest)
        checkpoint = self._load_checkpoint(checkpoint_path, manifest)
        completed: dict[str, str] = dict(checkpoint["completed"])
        downloaded: list[str] = []
        skipped: list[str] = []

        for entry in manifest.entries:
            existing_id = completed.get(entry.entry_id)
            if existing_id and not refresh:
                artifact = self.store.load_metadata(existing_id)
                self.store.verify(artifact)
                if artifact.corpus_entry_id != entry.entry_id:
                    raise ValueError(
                        f"Checkpoint entry {entry.entry_id} points to mismatched artifact {existing_id}"
                    )
                skipped.append(entry.entry_id)
                continue

            artifact = self.acquisition.acquire(entry.to_request())
            completed[entry.entry_id] = artifact.source_artifact_id
            downloaded.append(entry.entry_id)
            self._write_checkpoint(checkpoint_path, manifest, completed)

        self._write_checkpoint(checkpoint_path, manifest, completed)
        artifact_ids = tuple(completed[entry.entry_id] for entry in manifest.entries)
        return DownloadSummary(
            manifest.manifest_id,
            tuple(downloaded),
            tuple(skipped),
            checkpoint_path,
            artifact_ids,
        )

    def _load_checkpoint(self, path: Path, manifest: CorpusManifest) -> dict[str, object]:
        if not path.exists():
            return {
                "schema_version": self.checkpoint_schema_version,
                "manifest_id": manifest.manifest_id,
                "manifest_schema_version": manifest.schema_version,
                "completed": {},
            }
        value = load_json(path)
        if value.get("schema_version") != self.checkpoint_schema_version:
            raise ValueError(f"Unsupported checkpoint schema in {path}")
        if value.get("manifest_id") != manifest.manifest_id:
            raise ValueError(f"Checkpoint manifest mismatch in {path}")
        if not isinstance(value.get("completed"), dict):
            raise ValueError(f"Checkpoint completed field must be an object in {path}")
        return value

    def _write_checkpoint(
        self,
        path: Path,
        manifest: CorpusManifest,
        completed: dict[str, str],
    ) -> None:
        value = {
            "schema_version": self.checkpoint_schema_version,
            "manifest_id": manifest.manifest_id,
            "manifest_schema_version": manifest.schema_version,
            "status": manifest.status,
            "completed": dict(sorted(completed.items())),
        }
        atomic_replace(path, canonical_json_bytes(value))

