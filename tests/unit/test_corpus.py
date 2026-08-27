from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from temporal_legal_drift.acquisition import (
    AcquisitionService,
    FetchResponse,
    RawArtifactStore,
    SourcePolicy,
)
from temporal_legal_drift.corpus import CorpusDownloader, CorpusManifest
from temporal_legal_drift.errors import AcquisitionError


ROOT = Path(__file__).resolve().parents[2]


class FakePdfTransport:
    def __init__(self, payload: bytes = b"%PDF-1.4\nfixture") -> None:
        self.payload = payload
        self.calls = 0

    def fetch(self, url, *, timeout, maximum_bytes, validate_url):  # type: ignore[no-untyped-def]
        self.calls += 1
        validate_url(url)
        return FetchResponse(self.payload, url, "application/pdf", {})


class CorpusTests(unittest.TestCase):
    def test_repository_pilot_manifest_is_explicitly_not_legal_gold(self) -> None:
        manifest = CorpusManifest.from_file(ROOT / "configs" / "corpus" / "pilot_v1.json")
        self.assertEqual(manifest.status, "bounded_technical_pilot_not_legal_gold")
        self.assertEqual(len(manifest.entries), 4)
        amendment = next(entry for entry in manifest.entries if entry.entry_id == "it-amendment-act-2008")
        self.assertIsNotNone(amendment.known_extraction_risk)

    def test_download_is_resumable_and_verifies_existing_artifacts(self) -> None:
        manifest = CorpusManifest.from_file(ROOT / "configs" / "corpus" / "pilot_v1.json")
        transport = FakePdfTransport()
        policy = SourcePolicy(
            "test",
            frozenset({"https"}),
            frozenset({"www.indiacode.nic.in"}),
            4096,
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = RawArtifactStore(Path(directory))
            downloader = CorpusDownloader(
                AcquisitionService(
                    policy,
                    store,
                    transport,
                    clock=lambda: "2026-08-27T00:00:00Z",
                ),
                store,
            )
            first = downloader.download(manifest)
            second = downloader.download(manifest)
            self.assertEqual(len(first.downloaded), 4)
            self.assertEqual(len(second.skipped), 4)
            self.assertEqual(transport.calls, 4)

    def test_expected_pdf_signature_is_enforced(self) -> None:
        manifest = CorpusManifest.from_file(ROOT / "configs" / "corpus" / "pilot_v1.json")
        transport = FakePdfTransport(b"not a pdf")
        policy = SourcePolicy(
            "test",
            frozenset({"https"}),
            frozenset({"www.indiacode.nic.in"}),
            4096,
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = RawArtifactStore(Path(directory))
            downloader = CorpusDownloader(
                AcquisitionService(policy, store, transport),
                store,
            )
            with self.assertRaises(AcquisitionError):
                downloader.download(manifest)
            self.assertEqual(list((Path(directory) / "sha256").rglob("*")), [])


if __name__ == "__main__":
    unittest.main()
