"""Immutable normalized-document and quarantine record storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Mapping

from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes

from .models import NormalizedDocument


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class NormalizedDocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def store(self, document: NormalizedDocument) -> Path:
        path = self.root / f"{document.normalized_document_id}.json"
        atomic_write_new(path, canonical_json_bytes(document.to_dict()))
        return path


@dataclass(frozen=True)
class QuarantineRecord:
    quarantine_id: str
    created_at: str
    stage: str
    reason_code: str
    message: str
    source_artifact_id: str | None = None
    source_sha256: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["details"] = dict(sorted(self.details.items()))
        return value


class QuarantineStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def record(
        self,
        *,
        stage: str,
        reason_code: str,
        message: str,
        source_artifact_id: str | None = None,
        source_sha256: str | None = None,
        details: Mapping[str, object] | None = None,
        created_at: str | None = None,
    ) -> Path:
        created_at = created_at or _utc_now_iso()
        identity = "\n".join(
            [stage, reason_code, message, source_artifact_id or "", source_sha256 or "", created_at]
        ).encode("utf-8")
        record = QuarantineRecord(
            quarantine_id=f"qnt_{sha256(identity).hexdigest()[:24]}",
            created_at=created_at,
            stage=stage,
            reason_code=reason_code,
            message=message,
            source_artifact_id=source_artifact_id,
            source_sha256=source_sha256,
            details=details or {},
        )
        path = self.root / f"{record.quarantine_id}.json"
        atomic_write_new(path, canonical_json_bytes(record.to_dict()))
        return path

