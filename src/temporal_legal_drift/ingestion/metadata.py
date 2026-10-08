"""Immutable document provenance with separate mutable coordination indexes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import (
    atomic_replace,
    atomic_write_new,
    canonical_json_bytes,
    load_json,
)


SUFFIXES = {"application/pdf": ".pdf", "text/html": ".html", "application/xml": ".xml", "text/plain": ".txt"}


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    source_id: str
    source_url: str
    final_url: str
    retrieved_at: str
    publication_date: str | None
    publication_date_precision: str
    sha256: str
    content_type: str
    file_path: str
    version: int
    previous_document_id: str | None
    status: str
    workflow_status: str
    review_status: str
    stage_history: tuple[str, ...]
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["stage_history"] = list(self.stage_history)
        return value


class IngestionStore:
    def __init__(self, project_root: Path, pipeline_version: str = "v1") -> None:
        self.project_root = project_root.resolve()
        self.root = self.project_root / "data/raw/ingestion" / pipeline_version
        self.artifact_root = self.root / "artifacts/sha256"
        self.record_root = self.root / "records"
        self.failure_root = self.root / "failures"
        self.queue_root = self.root / "review_queue"
        self.index_path = self.root / "state/document_index.json"

    def records(self) -> list[dict[str, object]]:
        if not self.index_path.is_file():
            return []
        value = load_json(self.index_path)
        rows = value.get("documents")
        if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows):
            raise ValueError("ingestion document index is malformed")
        return list(rows)

    def store_payload(self, payload: bytes, content_type: str) -> tuple[str, str]:
        digest = sha256(payload).hexdigest()
        suffix = SUFFIXES.get(content_type, ".bin")
        path = self.artifact_root / digest[:2] / f"{digest}{suffix}"
        atomic_write_new(path, payload)
        relative = path.relative_to(self.project_root).as_posix()
        return digest, relative

    def write_record(self, record: DocumentRecord) -> None:
        atomic_write_new(
            self.record_root / f"{record.document_id}.json",
            canonical_json_bytes(record.to_dict()),
        )
        rows = self.records()
        if any(item.get("document_id") == record.document_id for item in rows):
            return
        rows.append(record.to_dict())
        atomic_replace(
            self.index_path,
            canonical_json_bytes({
                "schema_version": "1.0.0",
                "documents": sorted(rows, key=lambda item: str(item["document_id"])),
            }),
        )

    def enqueue_review(self, record: DocumentRecord) -> str:
        queue_id = f"review_{sha256(record.document_id.encode()).hexdigest()[:24]}"
        atomic_write_new(
            self.queue_root / f"{queue_id}.json",
            canonical_json_bytes({
                "schema_version": "1.0.0",
                "queue_id": queue_id,
                "document_id": record.document_id,
                "source_id": record.source_id,
                "status": "HUMAN_REVIEW_PENDING",
                "legal_change_claimed": False,
                "created_at": record.retrieved_at,
            }),
        )
        return queue_id

    def log_failure(self, source_id: str, source_url: str, attempted_at: str, error: str) -> str:
        identity = f"{source_id}\n{source_url}\n{attempted_at}\n{error}"
        failure_id = f"failure_{sha256(identity.encode()).hexdigest()[:24]}"
        atomic_write_new(
            self.failure_root / f"{failure_id}.json",
            canonical_json_bytes({
                "schema_version": "1.0.0",
                "failure_id": failure_id,
                "source_id": source_id,
                "source_url": source_url,
                "attempted_at": attempted_at,
                "status": "DOWNLOAD_FAILED",
                "error": error,
            }),
        )
        return failure_id

    def failures(self) -> list[dict[str, object]]:
        return [load_json(path) for path in sorted(self.failure_root.glob("*.json"))]

    def queue_items(self) -> list[dict[str, object]]:
        return [load_json(path) for path in sorted(self.queue_root.glob("*.json"))]

    def write_provenance_manifest(self, path: Path) -> dict[str, object]:
        records = self.records()
        manifest = {
            "schema_version": "1.0.0",
            "pipeline_version": "gazette-ingestion-v1",
            "document_count": len(records),
            "unique_document_ids": len({str(item["document_id"]) for item in records}),
            "unique_artifact_hashes": len({str(item["sha256"]) for item in records}),
            "review_queue_count": len(self.queue_items()),
            "failure_count": len(self.failures()),
            "documents": records,
            "failures": self.failures(),
            "legal_change_claimed": False,
        }
        atomic_write_new(path, canonical_json_bytes(manifest))
        return manifest
