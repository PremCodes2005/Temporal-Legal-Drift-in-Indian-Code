from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from temporal_legal_drift.acquisition import (
    AcquisitionService,
    FetchResponse,
    RawArtifactStore,
    SourcePolicy,
    SourceRequest,
)
from temporal_legal_drift.acquisition.models import SourceArtifact, content_sha256
from temporal_legal_drift.errors import IntegrityError, UnsupportedFormatError
from temporal_legal_drift.parsing.service import NormalizationService
from temporal_legal_drift.parsing.store import NormalizedDocumentStore, QuarantineStore


class FakeTransport:
    def __init__(self, payload: bytes, media_type: str = "text/html") -> None:
        self.payload = payload
        self.media_type = media_type

    def fetch(self, url, *, timeout, maximum_bytes, validate_url):  # type: ignore[no-untyped-def]
        validate_url(url)
        return FetchResponse(self.payload, url, self.media_type, {})


class NormalizationPipelineTests(unittest.TestCase):
    def test_acquire_then_normalize_preserves_provenance(self) -> None:
        payload = b"<html><body><h1>Chapter I</h1><p>Legal text.</p></body></html>"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_root = root / "raw"
            policy = SourcePolicy(
                "test",
                frozenset({"https"}),
                frozenset({"example.gov.in"}),
                4096,
                1,
            )
            artifact = AcquisitionService(
                policy,
                RawArtifactStore(raw_root),
                FakeTransport(payload),
                clock=lambda: "2026-08-27T00:00:00Z",
            ).acquire(SourceRequest("https://example.gov.in/act", "ACT-1", "Act"))

            normalized_root = root / "normalized"
            quarantine_root = root / "quarantine"
            service = NormalizationService(
                NormalizedDocumentStore(normalized_root),
                QuarantineStore(quarantine_root),
            )
            document = service.normalize(artifact, raw_root)
            self.assertEqual(document.source_artifact_id, artifact.source_artifact_id)
            self.assertEqual(document.source_sha256, artifact.sha256)
            self.assertTrue((normalized_root / f"{document.normalized_document_id}.json").is_file())
            self.assertEqual(list(quarantine_root.glob("*.json")), [])

    def test_corrupted_raw_blob_is_quarantined(self) -> None:
        payload = b"Original legal text"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_root = root / "raw"
            policy = SourcePolicy(
                "test",
                frozenset({"https"}),
                frozenset({"example.gov.in"}),
                4096,
                1,
            )
            artifact = AcquisitionService(
                policy,
                RawArtifactStore(raw_root),
                FakeTransport(payload, "text/plain"),
                clock=lambda: "2026-08-27T00:00:00Z",
            ).acquire(SourceRequest("https://example.gov.in/act", "ACT-1", "Act"))
            (raw_root / artifact.blob_path).write_bytes(b"Tampered")

            quarantine_root = root / "quarantine"
            service = NormalizationService(
                NormalizedDocumentStore(root / "normalized"),
                QuarantineStore(quarantine_root),
            )
            with self.assertRaises(IntegrityError):
                service.normalize(artifact, raw_root)
            self.assertEqual(len(list(quarantine_root.glob("*.json"))), 1)

    def test_unsupported_format_is_quarantined(self) -> None:
        payload = b"unsupported fixture"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_root = root / "raw"
            raw_root.mkdir()
            blob = raw_root / "fixture.bin"
            blob.write_bytes(payload)
            artifact = SourceArtifact(
                source_artifact_id="src_000000000000000000000000",
                request_url="https://example.gov.in/source",
                final_url="https://example.gov.in/source",
                official_identifier="FIXTURE",
                instrument_type="fixture",
                retrieved_at="2026-08-27T00:00:00Z",
                media_type="application/octet-stream",
                byte_length=len(payload),
                sha256=content_sha256(payload),
                blob_path="fixture.bin",
                acquisition_method="fixture",
            )
            quarantine_root = root / "quarantine"
            service = NormalizationService(
                NormalizedDocumentStore(root / "normalized"),
                QuarantineStore(quarantine_root),
            )
            with self.assertRaises(UnsupportedFormatError):
                service.normalize(artifact, raw_root)
            self.assertEqual(len(list(quarantine_root.glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
