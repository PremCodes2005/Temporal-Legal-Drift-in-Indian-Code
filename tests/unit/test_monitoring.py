"""Incremental source monitoring with a fake clock, fake connectors, fake parser and fake HTTP; no network."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from temporal_legal_drift.acquisition.fetch import FetchResponse
from temporal_legal_drift.monitoring import EGazetteConnector, IndiaCodeConnector, MonitoringService
from temporal_legal_drift.monitoring.egazette import parse_listing
from temporal_legal_drift.monitoring.indiacode import DiscoveredRecord, SourceShapeError

PDF_A = b"%PDF-1.4 synthetic test document A"
PDF_B = b"%PDF-1.4 synthetic test document B (revised)"
AMENDMENT = ("THE SYNTHETIC (AMENDMENT) ACT, 2026\nAn Act to amend the Synthetic Act, 2020.\n"
             "1. This Act may be called the Synthetic (Amendment) Act, 2026.\n"
             '2. In section 5 of the Synthetic Act, 2020, for the words "ten days", the words "fifteen days" shall be substituted.\n'
             + "Filler sentence with ordinary words to exceed the readable-text threshold. " * 4)


class Clock:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class Document:
    def __init__(self, text: str) -> None:
        self.text = text

    def to_dict(self) -> dict:
        return {"blocks": [{"block_id": "b1", "source_anchor": "pdf:page:1", "normalized_text": self.text}]}


class FakeParser:
    name, version = "fake-parser", "1"

    def __init__(self, text: str = AMENDMENT) -> None:
        self.text = text
        self.calls = 0

    def parse(self, payload, context):
        self.calls += 1
        return Document(self.text)


def record(source: str, official_id: str, accessioned: str, url: str, *, md5: str | None = "m1", size: int | None = 10,
           eligible: bool = True, tolerance: float | None = None) -> DiscoveredRecord:
    return DiscoveredRecord(source, official_id, None, f"Synthetic (Amendment) Act {official_id}", url, accessioned, None,
                            {"issued": None, "published": accessioned[:10]}, "a.pdf", url, md5, size,
                            download_eligible=eligible, size_tolerance=tolerance)


class FakeConnector:
    def __init__(self) -> None:
        self.records: list[DiscoveredRecord] = []
        self.payloads: dict[str, object] = {}
        self.discover_calls = 0
        self.downloads: list[str] = []
        self.fail: Exception | None = None

    def discover(self, since, *, max_pages):
        self.discover_calls += 1
        if self.fail:
            raise self.fail
        return list(self.records)

    def download(self, url):
        self.downloads.append(url)
        value = self.payloads[url]
        if isinstance(value, Exception):
            raise value
        return value


class MonitoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = Clock("2026-10-12T00:00:00+00:00")
        self.india, self.gazette = FakeConnector(), FakeConnector()
        self.parser = FakeParser()
        self.index_calls: list[int] = []
        self.service = MonitoringService(
            self.root, {"india_code": self.india, "egazette": self.gazette}, clock=self.clock, parser=self.parser,
            index_updater=lambda root, docs: self.index_calls.append(len(docs)) or {"status": "ACTIVATED", "documents": len(docs)},
            graph_mapper=lambda event: {"status": "TARGET_UNRESOLVED"})
        self.url = "https://indiacode.gov.in/server/api/core/bitstreams/a/content"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def next_day(self, hours: int = 24) -> None:
        from datetime import datetime, timedelta
        self.clock.value = (datetime.fromisoformat(self.clock.value) + timedelta(hours=hours)).isoformat()

    def queue(self) -> list[dict]:
        return [json.loads(p.read_text()) for p in sorted((self.root / "data/monitoring/review_queue").glob("*.json"))]

    # --- scheduling ---
    def test_never_starts_earlier_than_24_hours_after_the_previous_start(self) -> None:
        self.assertEqual(len(self.service.run_due("w1")), 2)
        self.next_day(23)
        self.assertEqual(self.service.run_due("w1"), [])
        self.assertEqual(self.service.run_due("w2"), [])
        self.next_day(1)
        self.assertEqual(len(self.service.run_due("w2")), 2)
        self.assertEqual((self.india.discover_calls, self.gazette.discover_calls), (2, 2))

    def test_concurrent_scheduler_attempts_start_one_run_per_source(self) -> None:
        results: list[list] = []
        threads = [threading.Thread(target=lambda n=n: results.append(self.service.run_due(n))) for n in "abc"]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual((self.india.discover_calls, self.gazette.discover_calls), (1, 1))

    def test_outage_is_visible_and_waits_for_the_next_window(self) -> None:
        self.india.fail = OSError("outage")
        result = next(r for r in self.service.run_due("w") if r["source_key"] == "india_code")
        self.assertEqual(result["status"], "SOURCE_UNAVAILABLE")
        health = {s["source_key"]: s for s in self.service.health()["sources"]}
        self.assertEqual(health["india_code"]["last_status"], "SOURCE_UNAVAILABLE")
        self.assertFalse(health["india_code"]["scheduled_ingestion_healthy"])
        self.india.fail = None
        self.next_day(12)
        self.assertEqual(self.service.run_due("w"), [])  # no hidden rapid retry after an error

    # --- incremental processing ---
    def test_first_discovery_is_processed_once_and_unchanged_next_cycle_is_not_refetched(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url)]
        self.india.payloads[self.url] = PDF_A
        first = self.service.run_due("w")[1]["records"][0]
        self.assertEqual((first["status"], first["outcome"]), ("NEW", "PROCESSED"))
        stages = first["stages"]
        self.assertEqual(stages["applicability"]["status"], "NOT_DETERMINED")
        self.assertEqual(stages["applicability"]["publication_fact"]["status"], "UNAPPROVED")
        self.assertEqual(stages["index"]["status"], "ACTIVATED")
        doc = self.service.documents()[0]
        self.assertEqual([h["state"] for h in doc["versions"][0]["history"]],
                         ["DISCOVERED", "FETCHED", "HASHED", "VERIFIED", "EXTRACTION_PENDING", "PROCESSED"])
        self.next_day()
        second = self.service.run_due("w")[1]["records"][0]
        self.assertEqual(second["status"], "UNCHANGED")
        self.assertEqual(len(self.india.downloads), 1)       # not re-downloaded
        self.assertEqual(self.parser.calls, 1)               # no duplicate processing run
        self.assertEqual(len(self.queue()), 1)

    def test_changed_bytes_under_same_official_id_create_a_linked_version(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url, md5="m1")]
        self.india.payloads[self.url] = PDF_A
        self.service.run_due("w")
        self.next_day()
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url, md5="m2")]
        self.india.payloads[self.url] = PDF_B
        revised = self.service.run_due("w")[1]["records"][0]
        self.assertEqual(revised["status"], "REVISED")
        self.assertEqual(revised["version"], 2)
        self.assertIsNotNone(revised["previous_sha256"])
        self.assertEqual(len(list((self.root / "data/raw/monitoring/sha256").rglob("*.pdf"))), 2)
        self.assertTrue(all(not item["legal_effect_claimed"] for item in self.queue()))

    def test_same_bytes_under_another_official_id_share_one_artifact(self) -> None:
        other = "https://indiacode.gov.in/server/api/core/bitstreams/b/content"
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url),
                              record("india_code", "item-2", "2026-10-11T11:00:00Z", other)]
        self.india.payloads[self.url] = PDF_A
        self.india.payloads[other] = PDF_A
        records = self.service.run_due("w")[1]["records"]
        self.assertEqual(len(list((self.root / "data/raw/monitoring/sha256").rglob("*.pdf"))), 1)
        self.assertEqual(records[1]["same_bytes_as_official_ids"], ["item-1"])

    def test_same_amendment_from_both_portals_links_one_candidate(self) -> None:
        gazette_url = "https://egazette.gov.in/WriteReadData/2026/1.pdf"
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url)]
        self.gazette.records = [record("egazette", "CG-DL-E-11102026-1", "2026-10-11", gazette_url, md5=None)]
        self.india.payloads[self.url] = PDF_A
        self.gazette.payloads[gazette_url] = PDF_B  # different bytes (stamped vs gazette copy), same amendment text
        self.service.run_due("w")
        candidates = self.service.candidates()
        substitute = [c for c in candidates if c["event"]["operation"] == "SUBSTITUTE"]
        self.assertEqual(len(substitute), 1)
        self.assertEqual(substitute[0]["linked_sources"], ["egazette", "india_code"])
        self.assertEqual(len(substitute[0]["provenance"]), 2)
        self.assertEqual(substitute[0]["materiality_triage"]["status"], "PROVISIONAL_RULE_OUTPUT")
        self.assertFalse(substitute[0]["legal_effect_claimed"])

    def test_failed_download_retries_only_at_the_next_eligible_cycle(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url)]
        self.india.payloads[self.url] = TimeoutError("network")
        failed = self.service.run_due("w")[1]
        self.assertEqual((failed["status"], failed["records"][0]["status"]), ("PARTIAL_FAILURE", "FAILED"))
        self.india.payloads[self.url] = PDF_A
        self.next_day(6)
        self.service.run_due("w")
        self.assertEqual(len(self.india.downloads), 1)  # no refetch before the window
        self.next_day(18)
        retried = self.service.run_due("w")[1]["records"][0]
        self.assertEqual((retried["status"], retried["outcome"]), ("NEW", "PROCESSED"))

    def test_interrupted_processing_resumes_only_incomplete_stages(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url)]
        self.india.payloads[self.url] = PDF_A
        calls = {"n": 0}

        def flaky(event):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("crash during graph mapping")
            return {"status": "TARGET_UNRESOLVED"}

        self.service.graph_mapper = flaky
        interrupted = self.service.run_due("w")[1]["records"][0]
        self.assertEqual(interrupted["status"], "FAILED")
        resumed = self.service.resume_incomplete()
        self.assertEqual(resumed[0]["outcome"], "PROCESSED")
        self.assertEqual(len(self.india.downloads), 1)  # fetched once
        self.assertEqual(self.parser.calls, 1)           # parse output reused from cache

    def test_tampered_artifact_is_detected_on_resume(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url)]
        self.india.payloads[self.url] = PDF_A
        self.service.graph_mapper = lambda event: (_ for _ in ()).throw(RuntimeError("crash"))
        self.service.run_due("w")
        artifact = next((self.root / "data/raw/monitoring/sha256").rglob("*.pdf"))
        artifact.chmod(0o644)
        artifact.write_bytes(b"%PDF-1.4 tampered")
        resumed = self.service.resume_incomplete()
        self.assertIn("no longer matches its recorded SHA-256", resumed[0]["error"])

    def test_unreadable_and_ocr_uncertain_documents_go_to_review(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url)]
        self.india.payloads[self.url] = PDF_A
        self.parser.text = "scan"
        unreadable = self.service.run_due("w")[1]["records"][0]
        self.assertEqual((unreadable["outcome"], unreadable["review_reason"]), ("REVIEW_REQUIRED", "SOURCE_TEXT_UNREADABLE"))
        # Legacy-font/OCR garbage lines are withheld; the clean amendment text is still processed.
        garbled = AMENDMENT + "\n" + "~h~ ~a~ette (j{ ~i4 1{flT sh@ll b€ subst!tuted\n" * 20
        service = MonitoringService(self.root / "other", {"india_code": self.india}, clock=self.clock,
                                    parser=FakeParser(garbled), graph_mapper=lambda event: {"status": "TARGET_UNRESOLVED"})
        result = service.run_due("w")[0]["records"][0]
        self.assertEqual(result["stages"]["text_fidelity"]["quarantine"]["by_reason"], {"LEGACY_FONT_MOJIBAKE": 20})
        self.assertTrue(all("~" not in c["event"]["evidence_text"] for c in service.candidates()))
        # Garbage that matches no quarantine rule still makes the whole document unreliable: reviewed, never indexed.
        odd = AMENDMENT + " " + "subst!tuted b€ (j{ th|s 0f|ence " * 30
        calls: list[int] = []
        service = MonitoringService(self.root / "third", {"india_code": self.india}, clock=self.clock, parser=FakeParser(odd),
                                    index_updater=lambda root, docs: calls.append(len(docs)) or {"status": "ACTIVATED"},
                                    graph_mapper=lambda event: {"status": "TARGET_UNRESOLVED"})
        result = service.run_due("w")[0]["records"][0]
        self.assertEqual((result["stages"]["text_fidelity"]["status"], result["outcome"], result["stages"]["index"]["status"]),
                         ("UNRELIABLE", "REVIEW_REQUIRED", "WITHHELD"))
        self.assertEqual(calls, [])
        self.assertTrue(all(c["materiality_triage"]["status"] == "REVIEW_REQUIRED" for c in service.candidates()))

    def test_index_failure_keeps_document_reviewable(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-11T10:00:00Z", self.url)]
        self.india.payloads[self.url] = PDF_A
        self.service.index_updater = lambda root, docs: (_ for _ in ()).throw(OSError("disk full"))
        result = self.service.run_due("w")[1]["records"][0]
        self.assertEqual((result["outcome"], result["review_reason"]), ("REVIEW_REQUIRED", "INDEX_UPDATE_FAILED"))

    def test_gazette_metadata_only_rows_and_size_mismatch(self) -> None:
        url = "https://egazette.gov.in/WriteReadData/2026/2.pdf"
        self.gazette.records = [record("egazette", "CG-DL-E-11102026-9", "2026-10-11", "https://egazette.gov.in/x", eligible=False),
                                record("egazette", "CG-DL-E-11102026-2", "2026-10-11", url, md5=None, size=10_000, tolerance=0.15)]
        self.gazette.payloads[url] = PDF_A  # far smaller than listed
        records = self.service.run_due("w")[0]["records"]
        self.assertEqual(records[0]["status"], "METADATA_ONLY")
        self.assertEqual(records[1]["outcome"], "REVIEW_REQUIRED")
        self.assertIn("listed size", records[1]["review_reason"])
        self.assertEqual(self.gazette.downloads, [url])


class FakeTransport:
    def __init__(self, responses: dict[str, tuple[str, bytes, str | None]]) -> None:
        self.responses = responses

    def fetch(self, url, *, timeout, maximum_bytes, validate_url, headers=None):
        validate_url(url)
        self.requests = getattr(self, "requests", []) + [(url, headers)]
        for prefix, (media_type, payload, final_url) in self.responses.items():
            if url.startswith(prefix):
                return FetchResponse(payload, final_url or url, media_type, {})
        raise OSError(f"unexpected url {url}")


def _listing(rows: list[dict[str, str]]) -> bytes:
    cells = []
    for index, row in enumerate(rows):
        for name, value in row.items():
            cells.append(f'<span id="gvGazetteList_lbl_{name}_{index}"><font color="Black">{value}</font></span>')
    return ("<table>" + "".join(cells) + "</table>").encode()


class ConnectorTests(unittest.TestCase):
    def test_egazette_listing_is_parsed_filtered_and_mapped_to_static_pdf(self) -> None:
        base = {"Ministry": "Ministry of Law", "Department": "Legislative Department", "Office": "x", "Category": "Extra Ordinary",
                "IssueDate": "09-Oct-2026", "PublishDate": "10-Oct-2026", "FileSize": "0.58 MB"}
        rows = [{**base, "Subject": "The Synthetic (Amendment) Act, 2026", "PartSection": "Part II-Section 1", "UGID": "CG-DL-E-10102026-277026"},
                {**base, "Subject": "Notification under the Railway Act 1989", "PartSection": "Part II-Section 3-Sub-Section (ii)", "UGID": "CG-DL-E-10102026-277027"}]
        transport = FakeTransport({
            "https://egazette.gov.in/RecentUploads": ("text/html", b"", None),
            "https://egazette.gov.in/(S(abc123))/RecentUploads.aspx": ("text/html", _listing(rows), None),
            "https://egazette.gov.in/": ("text/html", b"<html/>", "https://egazette.gov.in/(S(abc123))/default.aspx"),
        })
        found = EGazetteConnector(transport, pause_seconds=0, sleep=lambda _: None).discover(None)
        self.assertEqual(transport.requests[-1], ("https://egazette.gov.in/(S(abc123))/RecentUploads.aspx?Category=1",
                                                  {"Referer": "https://egazette.gov.in/(S(abc123))/default.aspx"}))
        self.assertEqual([r.official_id for r in found], ["CG-DL-E-10102026-277026", "CG-DL-E-10102026-277027"])
        self.assertEqual(found[0].canonical_url, "https://egazette.gov.in/WriteReadData/2026/277026.pdf")
        self.assertEqual([r.download_eligible for r in found], [True, False])
        self.assertEqual(found[0].stated_dates, {"issued": "2026-10-09", "published": "2026-10-10"})
        with self.assertRaises(SourceShapeError):
            parse_listing("<html>changed layout</html>")

    def test_egazette_error_page_redirect_is_a_visible_shape_failure(self) -> None:
        transport = FakeTransport({
            "https://egazette.gov.in/(S(abc123))/RecentUploads.aspx": ("text/html", b"<html/>", "https://egazette.gov.in/(S(abc123))/error.aspx"),
            "https://egazette.gov.in/": ("text/html", b"<html/>", "https://egazette.gov.in/(S(abc123))/default.aspx"),
        })
        with self.assertRaisesRegex(SourceShapeError, "error page"):
            EGazetteConnector(transport, pause_seconds=0, sleep=lambda _: None).discover(None)

    def test_indiacode_shape_change_and_allowlist(self) -> None:
        transport = FakeTransport({"https://indiacode.gov.in/server/api/discover": ("application/json", b'{"unexpected": 1}', None)})
        connector = IndiaCodeConnector(transport, pause_seconds=0, sleep=lambda _: None)
        with self.assertRaises(SourceShapeError):
            connector.discover(None)
        with self.assertRaises(Exception):
            connector.download("https://example.com/a.pdf")


class OverlayTests(unittest.TestCase):
    def test_tampered_or_rebased_overlay_is_never_served(self) -> None:
        from temporal_legal_drift.rag.retriever import OVERLAY_DIR, OVERLAY_POINTER, HybridRetriever
        from temporal_legal_drift.jsonio import canonical_json_bytes
        from hashlib import sha256

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = canonical_json_bytes({"chunks": [{"chunk_id": "mon_1", "text": "x", "embedding": [], "metadata": {}}]})
            digest = sha256(body).hexdigest()
            (root / OVERLAY_DIR).mkdir(parents=True)
            (root / OVERLAY_DIR / f"overlay.{digest}.json").write_bytes(body)
            (root / OVERLAY_POINTER).write_bytes(canonical_json_bytes({"overlay_sha256": digest, "base_index_identity": "base-1"}))
            with patch.object(HybridRetriever, "_active_version", return_value={"rag_index_version": "t"}), \
                    patch.object(HybridRetriever, "ensure_index", return_value={"index_identity": "base-1"}):
                retriever = HybridRetriever(root)
                self.assertEqual(len(retriever._overlay_chunks()), 1)
                (root / OVERLAY_DIR / f"overlay.{digest}.json").write_bytes(body + b" ")
                self.assertEqual(retriever._overlay_chunks(), [])  # tampered
            (root / OVERLAY_DIR / f"overlay.{digest}.json").write_bytes(body)
            with patch.object(HybridRetriever, "_active_version", return_value={"rag_index_version": "t"}), \
                    patch.object(HybridRetriever, "ensure_index", return_value={"index_identity": "base-2"}):
                self.assertEqual(HybridRetriever(root)._overlay_chunks(), [])  # bound to another base index


if __name__ == "__main__":
    unittest.main()
