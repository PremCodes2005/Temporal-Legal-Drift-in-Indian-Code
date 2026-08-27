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
from temporal_legal_drift.errors import SourcePolicyError


class FakeTransport:
    def __init__(self, response: FetchResponse) -> None:
        self.response = response
        self.calls = 0

    def fetch(self, url, *, timeout, maximum_bytes, validate_url):  # type: ignore[no-untyped-def]
        self.calls += 1
        validate_url(self.response.final_url)
        if len(self.response.payload) > maximum_bytes:
            raise AssertionError("fake response exceeds configured limit")
        return self.response


class AcquisitionTests(unittest.TestCase):
    def policy(self, *hosts: str) -> SourcePolicy:
        return SourcePolicy(
            version="test",
            allowed_schemes=frozenset({"https"}),
            approved_hosts=frozenset(hosts),
            maximum_response_bytes=1024,
            request_timeout_seconds=1,
        )

    def test_deny_by_default_policy_blocks_network_transport(self) -> None:
        transport = FakeTransport(FetchResponse(b"law", "https://example.gov.in/a", "text/plain", {}))
        with tempfile.TemporaryDirectory() as directory:
            service = AcquisitionService(self.policy(), RawArtifactStore(Path(directory)), transport)
            with self.assertRaises(SourcePolicyError):
                service.acquire(SourceRequest("https://example.gov.in/a", "ID-1", "Act"))
        self.assertEqual(transport.calls, 0)

    def test_acquisition_is_hashed_content_addressed_and_verified(self) -> None:
        response = FetchResponse(
            b"SECTION 1\nAuthoritative source fixture.",
            "https://example.gov.in/final",
            "text/plain",
            {"etag": "fixture-v1"},
        )
        transport = FakeTransport(response)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = RawArtifactStore(root)
            service = AcquisitionService(
                self.policy("example.gov.in"),
                store,
                transport,
                clock=lambda: "2026-08-27T00:00:00Z",
            )
            artifact = service.acquire(
                SourceRequest("https://example.gov.in/start", "ID-1", "Act")
            )
            self.assertEqual(artifact.byte_length, len(response.payload))
            self.assertTrue((root / artifact.blob_path).is_file())
            self.assertTrue((root / "metadata" / f"{artifact.source_artifact_id}.json").is_file())
            store.verify(artifact)

            repeated = service.acquire(
                SourceRequest("https://example.gov.in/start", "ID-1", "Act")
            )
            self.assertEqual(artifact.source_artifact_id, repeated.source_artifact_id)
            self.assertEqual(artifact.blob_path, repeated.blob_path)

    def test_redirect_to_unapproved_host_is_blocked(self) -> None:
        transport = FakeTransport(
            FetchResponse(b"law", "https://unapproved.example/final", "text/plain", {})
        )
        with tempfile.TemporaryDirectory() as directory:
            service = AcquisitionService(
                self.policy("approved.example"),
                RawArtifactStore(Path(directory)),
                transport,
            )
            with self.assertRaises(SourcePolicyError):
                service.acquire(SourceRequest("https://approved.example/start", "ID-1", "Act"))


if __name__ == "__main__":
    unittest.main()

