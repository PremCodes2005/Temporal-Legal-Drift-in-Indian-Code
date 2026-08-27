"""Content-addressed immutable storage for acquired legal evidence."""

from __future__ import annotations

from pathlib import Path

from temporal_legal_drift.errors import IntegrityError
from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json

from .models import SourceArtifact, content_sha256


MEDIA_SUFFIXES = {
    "application/pdf": ".pdf",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "text/html": ".html",
    "text/plain": ".txt",
    "application/json": ".json",
}


class RawArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.blob_root = root / "sha256"
        self.metadata_root = root / "metadata"

    def blob_relative_path(self, content_hash: str, media_type: str) -> Path:
        suffix = MEDIA_SUFFIXES.get(media_type.split(";", 1)[0].strip().lower(), ".bin")
        return Path("sha256") / content_hash[:2] / f"{content_hash}{suffix}"

    def store_blob(self, payload: bytes, media_type: str) -> tuple[str, str]:
        content_hash = content_sha256(payload)
        relative = self.blob_relative_path(content_hash, media_type)
        absolute = self.root / relative
        atomic_write_new(absolute, payload)
        if content_sha256(absolute.read_bytes()) != content_hash:
            raise IntegrityError(f"Stored raw artifact failed SHA-256 verification: {absolute}")
        return content_hash, relative.as_posix()

    def store_metadata(self, artifact: SourceArtifact) -> Path:
        path = self.metadata_root / f"{artifact.source_artifact_id}.json"
        atomic_write_new(path, canonical_json_bytes(artifact.to_dict()))
        return path

    def load_metadata(self, source_artifact_id: str) -> SourceArtifact:
        value = load_json(self.metadata_root / f"{source_artifact_id}.json")
        return SourceArtifact(**value)

    def verify(self, artifact: SourceArtifact) -> None:
        blob = self.root / artifact.blob_path
        if not blob.is_file():
            raise IntegrityError(f"Raw blob is missing: {blob}")
        payload = blob.read_bytes()
        if len(payload) != artifact.byte_length:
            raise IntegrityError(f"Byte-length mismatch for {artifact.source_artifact_id}")
        if content_sha256(payload) != artifact.sha256:
            raise IntegrityError(f"SHA-256 mismatch for {artifact.source_artifact_id}")

