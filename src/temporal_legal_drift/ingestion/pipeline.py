"""End-to-end source-to-review-queue ingestion orchestration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from temporal_legal_drift.errors import TemporalLegalDriftError

from .deduplicator import DocumentDeduplicator
from .discover import DiscoveryCandidate
from .downloader import LegalDocumentDownloader
from .metadata import DocumentRecord, IngestionStore


@dataclass(frozen=True)
class IngestionResult:
    source_id: str
    status: str
    document_id: str | None
    artifact_sha256: str | None
    duplicate: bool
    failure_id: str | None = None


class IngestionPipeline:
    def __init__(self, downloader: LegalDocumentDownloader, store: IngestionStore) -> None:
        self.downloader = downloader
        self.store = store
        self.deduplicator = DocumentDeduplicator()

    def process(self, candidate: DiscoveryCandidate) -> IngestionResult:
        source = candidate.source
        try:
            downloaded = self.downloader.download(source)
        except (TemporalLegalDriftError, OSError, TimeoutError) as error:
            attempted_at = self.downloader.clock()
            failure_id = self.store.log_failure(
                source.source_id,
                source.url,
                attempted_at,
                f"{type(error).__name__}: {error}",
            )
            return IngestionResult(source.source_id, "DOWNLOAD_FAILED", None, None, False, failure_id)

        content_hash = sha256(downloaded.payload).hexdigest()
        decision = self.deduplicator.decide(
            source.source_id, content_hash, self.store.records()
        )
        if decision.is_duplicate:
            return IngestionResult(
                source.source_id,
                "DUPLICATE",
                decision.existing_document_id,
                content_hash,
                True,
            )

        stored_hash, file_path = self.store.store_payload(
            downloaded.payload, downloaded.content_type
        )
        document_id = _document_id(source.source_type, source.source_id, decision.version, stored_hash)
        record = DocumentRecord(
            document_id=document_id,
            source_id=source.source_id,
            source_url=source.url,
            final_url=downloaded.final_url,
            retrieved_at=downloaded.retrieved_at,
            publication_date=source.publication_date,
            publication_date_precision=source.publication_date_precision,
            sha256=stored_hash,
            content_type=downloaded.content_type,
            file_path=file_path,
            version=decision.version,
            previous_document_id=decision.previous_document_id,
            status="INGESTED",
            workflow_status="EXTRACTION_QUEUE",
            review_status="HUMAN_REVIEW_PENDING",
            stage_history=(
                "NEW_DOCUMENT",
                "DISCOVERED",
                "DOWNLOADED",
                "HASHED",
                "EXTRACTION_QUEUE",
                "HUMAN_REVIEW_PENDING",
            ),
        )
        self.store.write_record(record)
        self.store.enqueue_review(record)
        return IngestionResult(source.source_id, "INGESTED", document_id, stored_hash, False)

    def run(self, candidates: tuple[DiscoveryCandidate, ...]) -> tuple[IngestionResult, ...]:
        return tuple(self.process(candidate) for candidate in candidates)


def _document_id(source_type: str, source_id: str, version: int, content_hash: str) -> str:
    prefixes = {
        "gazette_notification": "GAZ",
        "amending_act": "AMD",
        "central_act": "ACT",
        "consolidated_central_act": "ACT",
        "consolidated_central_code": "CODE",
    }
    prefix = prefixes.get(source_type, "LEGAL")
    slug = re.sub(r"[^A-Z0-9]+", "-", source_id.upper()).strip("-")[:36]
    return f"{prefix}-{slug}-V{version:03d}-{content_hash[:12].upper()}"
