from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from temporal_legal_drift.acquisition import FetchResponse, SourcePolicy
from temporal_legal_drift.errors import AcquisitionError
from temporal_legal_drift.ingestion import (
    IngestionPipeline,
    IngestionStore,
    LegalDocumentDownloader,
    LegalSource,
    SourceDiscoverer,
    SourceRegistry,
)
from temporal_legal_drift.ingestion.scheduler import IngestionScheduler


ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = "2026-10-08T09:30:00Z"


class SequenceTransport:
    def __init__(self, payloads: list[bytes]) -> None:
        self.payloads = payloads
        self.calls = 0

    def fetch(self, url, *, timeout, maximum_bytes, validate_url):  # type: ignore[no-untyped-def]
        validate_url(url)
        if not self.payloads:
            raise AcquisitionError("controlled failure")
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return FetchResponse(payload, url, "application/pdf", {})


class PhaseOneIngestionTests(unittest.TestCase):
    def source(self) -> LegalSource:
        return LegalSource(
            "fixture-act-2026",
            "central_act",
            "Controlled authority",
            "Fixture Act 2026",
            "https://example.gov.in/fixture.pdf",
            "2026-08-14",
            "day_from_authoritative_metadata",
            mime_type="application/pdf",
        )

    def policy(self) -> SourcePolicy:
        return SourcePolicy(
            "test", frozenset({"https"}), frozenset({"example.gov.in"}), 4096, 1
        )

    def test_checkpoint_source_registry_has_25_unique_legal_sources(self) -> None:
        registry = SourceRegistry.from_file(ROOT / "configs/ingestion/source_registry.v1.json")
        self.assertEqual(len(registry.sources), 25)
        self.assertEqual(len({item.source_id for item in registry.sources}), 25)
        self.assertTrue(all(item.publication_date for item in registry.sources))

    def test_duplicate_reuses_artifact_and_revision_creates_linked_version(self) -> None:
        transport = SequenceTransport([
            b"%PDF-1.4\noriginal legal document",
            b"%PDF-1.4\noriginal legal document",
            b"%PDF-1.4\nrevised legal document",
        ])
        with tempfile.TemporaryDirectory() as directory:
            store = IngestionStore(Path(directory))
            pipeline = IngestionPipeline(
                LegalDocumentDownloader(self.policy(), transport, lambda: FIXED_TIME), store
            )
            candidate = SourceDiscoverer(
                SourceRegistry("test", "1.0.0", (self.source(),)), lambda: FIXED_TIME
            ).discover()[0]
            first = pipeline.process(candidate)
            duplicate = pipeline.process(candidate)
            revised = pipeline.process(candidate)
            records = store.records()

            self.assertEqual(first.status, "INGESTED")
            self.assertTrue(duplicate.duplicate)
            self.assertEqual(duplicate.document_id, first.document_id)
            self.assertNotEqual(revised.document_id, first.document_id)
            self.assertEqual([item["version"] for item in records], [1, 2])
            self.assertEqual(records[1]["previous_document_id"], records[0]["document_id"])
            self.assertTrue(all(item["status"] == "INGESTED" for item in records))
            self.assertTrue(all(item["workflow_status"] == "EXTRACTION_QUEUE" for item in records))
            self.assertTrue(all(item["review_status"] == "HUMAN_REVIEW_PENDING" for item in records))
            self.assertEqual(len(store.queue_items()), 2)
            self.assertTrue(all(item["legal_change_claimed"] is False for item in store.queue_items()))

    def test_failures_are_immutable_and_scheduler_is_explicit(self) -> None:
        transport = SequenceTransport([])
        with tempfile.TemporaryDirectory() as directory:
            store = IngestionStore(Path(directory))
            discoverer = SourceDiscoverer(
                SourceRegistry("test", "1.0.0", (self.source(),)), lambda: FIXED_TIME
            )
            pipeline = IngestionPipeline(
                LegalDocumentDownloader(self.policy(), transport, lambda: FIXED_TIME), store
            )
            run = IngestionScheduler(discoverer, pipeline, lambda: FIXED_TIME).run_once()
            self.assertEqual(run.results[0].status, "DOWNLOAD_FAILED")
            self.assertEqual(len(store.failures()), 1)
            self.assertEqual(store.records(), [])


if __name__ == "__main__":
    unittest.main()
