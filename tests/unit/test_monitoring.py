"""Incremental source monitoring with a fake clock, fake connector and fake HTTP; no network."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from hashlib import md5
from pathlib import Path

from temporal_legal_drift.acquisition.fetch import FetchResponse
from temporal_legal_drift.monitoring import IndiaCodeConnector, MonitoringService
from temporal_legal_drift.monitoring.indiacode import DiscoveredRecord, SourceShapeError

PDF_A = b"%PDF-1.4 synthetic test document A"
PDF_B = b"%PDF-1.4 synthetic test document B (revised)"


class Clock:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def record(official_id: str, accessioned: str, url: str = "https://indiacode.gov.in/server/api/core/bitstreams/x/content",
           checksum: str | None = None) -> DiscoveredRecord:
    return DiscoveredRecord("india_code", official_id, "123456789/1", f"Synthetic Act {official_id}",
                            f"https://indiacode.gov.in/items/{official_id}", accessioned, None,
                            {"issued": None, "enactment": None}, "a.pdf", url, checksum, 10)


class FakeConnector:
    def __init__(self) -> None:
        self.records: list[DiscoveredRecord] = []
        self.payloads: dict[str, bytes] = {}
        self.discover_calls = 0
        self.fail: Exception | None = None

    def discover(self, since, *, max_pages):
        self.discover_calls += 1
        if self.fail:
            raise self.fail
        return [item for item in self.records if since is None or item.accessioned_at > since]

    def download(self, url):
        if isinstance(self.payloads.get(url), Exception):
            raise self.payloads[url]
        return self.payloads[url]


class MonitoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = Clock("2026-10-12T00:00:00+00:00")
        self.connector = FakeConnector()
        self.service = MonitoringService(self.root, {"india_code": self.connector}, clock=self.clock)
        self.url = "https://indiacode.gov.in/server/api/core/bitstreams/a/content"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_at_most_one_automatic_attempt_per_rolling_24_hours(self) -> None:
        self.assertEqual(len(self.service.run_due("worker-1")), 1)
        self.clock.value = "2026-10-12T23:59:59+00:00"
        self.assertEqual(self.service.run_due("worker-1"), [])          # restart inside the window
        self.assertEqual(self.service.run_due("worker-2"), [])          # second worker inside the window
        self.clock.value = "2026-10-13T00:00:00+00:00"
        self.assertEqual(len(self.service.run_due("worker-2")), 1)      # window boundary is inclusive
        self.assertEqual(self.connector.discover_calls, 2)

    def test_concurrent_workers_do_not_duplicate_the_daily_attempt(self) -> None:
        results: list[list] = []
        threads = [threading.Thread(target=lambda name=name: results.append(self.service.run_due(name))) for name in ("a", "b", "c")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(self.connector.discover_calls, 1)
        self.assertEqual(sum(len(item) for item in results), 1)

    def test_new_unchanged_revised_and_duplicate_bytes(self) -> None:
        self.connector.records = [record("item-1", "2026-10-11T10:00:00Z", self.url, md5(PDF_A).hexdigest())]
        self.connector.payloads[self.url] = PDF_A
        first = self.service.run_due("w")[0]
        self.assertEqual(first["records"][0]["status"], "NEW")
        queue = list((self.root / "data/monitoring/review_queue").glob("*.json"))
        self.assertEqual(len(queue), 1)
        self.assertFalse(json.loads(queue[0].read_text())["legal_effect_claimed"])
        # Same official item, unchanged bytes (forced re-check): no new queue entry, no downstream work.
        unchanged = self.service.backfill("india_code", "w", pages=1, reason="Re-check unchanged bytes.")
        self.assertEqual(unchanged["records"][0]["status"], "UNCHANGED")
        self.assertEqual(len(list((self.root / "data/monitoring/review_queue").glob("*.json"))), 1)
        # Changed bytes for the same official ID: a linked revision, both artifacts kept.
        self.connector.records = [record("item-1", "2026-10-11T10:00:00Z", self.url, md5(PDF_B).hexdigest())]
        self.connector.payloads[self.url] = PDF_B
        revised = self.service.backfill("india_code", "w", pages=1, reason="Source revised in place.")["records"][0]
        self.assertEqual(revised["status"], "REVISED")
        self.assertIsNotNone(revised["previous_sha256"])
        self.assertEqual(len(list((self.root / "data/raw/monitoring/sha256").rglob("*.pdf"))), 2)
        # Same bytes under a second official item: one artifact, two observations.
        other = "https://indiacode.gov.in/server/api/core/bitstreams/b/content"
        self.connector.records = [record("item-2", "2026-10-11T11:00:00Z", other)]
        self.connector.payloads[other] = PDF_B
        self.service.backfill("india_code", "w", pages=1, reason="Duplicate bytes, other identity.")
        self.assertEqual(len(list((self.root / "data/raw/monitoring/sha256").rglob("*.pdf"))), 2)
        self.assertEqual({o["official_id"] for o in self.service.observations()}, {"item-1", "item-2"})

    def test_served_rendition_checksum_is_recorded_and_download_failure_is_not_dropped(self) -> None:
        self.connector.records = [record("stamped", "2026-10-11T10:00:00Z", self.url, "0" * 32),
                                  record("down", "2026-10-11T09:00:00Z", "https://indiacode.gov.in/x")]
        self.connector.payloads[self.url] = PDF_A
        self.connector.payloads["https://indiacode.gov.in/x"] = TimeoutError("network")
        result = self.service.run_due("w")[0]
        by_id = {item["official_id"]: item for item in result["records"]}
        self.assertEqual(by_id["stamped"]["status"], "NEW")
        self.assertEqual(by_id["stamped"]["repository_checksum"], "SERVED_RENDITION_DIFFERS_FROM_REPOSITORY_MD5")
        self.assertEqual(by_id["down"]["status"], "DOWNLOAD_FAILED")
        self.assertEqual(result["status"], "PARTIAL_FAILURE")
        self.assertEqual(self.service.health()["failed_observations"], 1)

    def test_outage_keeps_cursor_and_retry_is_audited(self) -> None:
        self.connector.fail = OSError("outage")
        result = self.service.run_due("w")[0]
        self.assertEqual(result["status"], "SOURCE_UNAVAILABLE")
        state = json.loads((self.root / "data/monitoring/state.v1.json").read_text())["sources"]["india_code"]
        self.assertIsNone(state.get("last_success_at"))
        self.assertEqual(self.service.run_due("w"), [])  # next automatic attempt waits for the window
        with self.assertRaises(ValueError):
            self.service.run_due("w", manual_reason="")
        self.connector.fail = None
        retry = self.service.run_due("w", manual_reason="Operator retry after outage.")[0]
        self.assertEqual((retry["mode"], retry["status"]), ("MANUAL_RETRY", "OK"))

    def test_parse_stage_is_cached_by_content_and_version_and_failures_stay_reviewable(self) -> None:
        class FailingParser:
            name, version = "test-parser", "1"

            def parse(self, payload, context):
                raise ValueError("unreadable")

        service = MonitoringService(self.root, {"india_code": self.connector}, clock=self.clock, parser=FailingParser())
        self.connector.records = [record("item-1", "2026-10-11T10:00:00Z", self.url)]
        self.connector.payloads[self.url] = PDF_A
        result = service.run_due("w")[0]["records"][0]
        self.assertEqual(result["stages"]["parse"], "FAILED")
        self.assertEqual(result["status"], "NEW")  # still queued for review

    def test_access_limited_source_is_reported_and_manual_import_is_attributed(self) -> None:
        health = self.service.health()
        self.assertIn({"source_key": "egazette", "status": "ACCESS_LIMITED",
                       "detail": "No documented machine interface; reviewed manual import only (S1 decision v1)."}, health["sources"])
        imported = self.service.manual_import("egazette", official_id="CG-DL-E-00000000-1", canonical_url="https://egazette.gov.in/",
                                              title="Synthetic gazette", payload=PDF_A, reviewer_id="project-engineer",
                                              reason="Downloaded from the portal by hand.")
        self.assertEqual((imported["mode"], imported["status"]), ("MANUAL_IMPORT", "NEW"))
        with self.assertRaises(ValueError):
            self.service.manual_import("india_code", official_id="x", canonical_url="https://indiacode.gov.in/", title="x",
                                       payload=PDF_A, reviewer_id="r", reason="not allowed here")


class FakeTransport:
    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def fetch(self, url, *, timeout, maximum_bytes, validate_url):
        validate_url(url)
        self.urls.append(url)
        for prefix, (media_type, payload) in self.responses.items():
            if url.startswith(prefix):
                return FetchResponse(payload, url, media_type, {})
        raise OSError(f"unexpected url {url}")


def _item(uuid: str, accessioned: str) -> dict:
    return {"_embedded": {"indexableObject": {"uuid": uuid, "handle": "123456789/9", "lastModified": accessioned,
            "metadata": {"dc.title": [{"value": f"Act {uuid}"}], "dc.date.accessioned": [{"value": accessioned}]}}}}


class IndiaCodeConnectorTests(unittest.TestCase):
    """Response shapes recorded in docs/sprint/s1_source_access_decision.v1.md; contents are synthetic."""

    def connector(self, items: list[dict]) -> tuple[IndiaCodeConnector, FakeTransport]:
        bundles = {"_embedded": {"bundles": [{"name": "ORIGINAL", "_embedded": {"bitstreams": {"_embedded": {"bitstreams": [
            {"name": "a.pdf", "sizeBytes": 10, "checkSum": {"checkSumAlgorithm": "MD5", "value": "abc"},
             "_links": {"content": {"href": "https://indiacode.gov.in/server/api/core/bitstreams/b1/content"}}}]}}}}]}}
        transport = FakeTransport({
            "https://indiacode.gov.in/server/api/discover/search/objects": ("application/json", json.dumps(
                {"_embedded": {"searchResult": {"_embedded": {"objects": items}}}}).encode()),
            "https://indiacode.gov.in/server/api/core/items/": ("application/json", json.dumps(bundles).encode()),
        })
        return IndiaCodeConnector(transport, pause_seconds=0, sleep=lambda _: None), transport

    def test_discovery_stops_at_the_cursor_and_reads_checksums(self) -> None:
        connector, transport = self.connector([_item("n2", "2026-10-10T00:00:00Z"), _item("n1", "2026-10-09T00:00:00Z")])
        found = connector.discover("2026-10-09T00:00:00Z")
        self.assertEqual([item.official_id for item in found], ["n2"])
        self.assertEqual((found[0].bitstream_md5, found[0].bitstream_bytes), ("abc", 10))
        self.assertIn("sort=dc.date.accessioned%2CDESC", transport.urls[0])

    def test_changed_response_shape_and_off_allowlist_urls_are_refused(self) -> None:
        connector, _ = self.connector([{"unexpected": True}])
        with self.assertRaises(SourceShapeError):
            connector.discover(None)
        with self.assertRaises(Exception):
            connector.download("https://example.com/a.pdf")


if __name__ == "__main__":
    unittest.main()
