"""Integrity-checked normalization orchestration."""

from __future__ import annotations

from pathlib import Path

from temporal_legal_drift.acquisition.models import SourceArtifact, content_sha256
from temporal_legal_drift.errors import IntegrityError, ParseError

from .models import NormalizedDocument, ParseContext
from .registry import ParserRegistry, default_registry
from .store import NormalizedDocumentStore, QuarantineStore


class NormalizationService:
    def __init__(
        self,
        normalized_store: NormalizedDocumentStore,
        quarantine_store: QuarantineStore,
        registry: ParserRegistry | None = None,
    ) -> None:
        self.normalized_store = normalized_store
        self.quarantine_store = quarantine_store
        self.registry = registry or default_registry()

    def normalize(self, artifact: SourceArtifact, raw_root: Path) -> NormalizedDocument:
        blob = raw_root / artifact.blob_path
        try:
            payload = blob.read_bytes()
        except OSError as error:
            self._quarantine(artifact, "raw_blob_unreadable", str(error), {"blob": str(blob)})
            raise IntegrityError(f"Could not read raw blob {blob}: {error}") from error

        actual_hash = content_sha256(payload)
        if actual_hash != artifact.sha256 or len(payload) != artifact.byte_length:
            message = (
                f"Raw artifact integrity mismatch: expected {artifact.sha256}/{artifact.byte_length}, "
                f"got {actual_hash}/{len(payload)}"
            )
            self._quarantine(artifact, "raw_integrity_mismatch", message, {"blob": str(blob)})
            raise IntegrityError(message)

        context = ParseContext(
            source_artifact_id=artifact.source_artifact_id,
            source_sha256=artifact.sha256,
            media_type=artifact.media_type,
            filename=blob.name,
        )
        try:
            parser = self.registry.select(artifact.media_type, blob.name)
            document = parser.parse(payload, context)
        except ParseError as error:
            self._quarantine(
                artifact,
                type(error).__name__,
                str(error),
                {"media_type": artifact.media_type, "blob": str(blob)},
            )
            raise

        self.normalized_store.store(document)
        return document

    def _quarantine(
        self,
        artifact: SourceArtifact,
        reason_code: str,
        message: str,
        details: dict[str, object],
    ) -> None:
        self.quarantine_store.record(
            stage="normalization",
            reason_code=reason_code,
            message=message,
            source_artifact_id=artifact.source_artifact_id,
            source_sha256=artifact.sha256,
            details=details,
        )

