"""Mocked end to end: e-Gazette listing -> download -> processing -> monitored index overlay -> retrieval; no network."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from temporal_legal_drift.monitoring import EGazetteConnector, MonitoringService
from temporal_legal_drift.rag.retriever import HybridRetriever, update_monitored_overlay
from unit.test_monitoring import AMENDMENT, Clock, FakeParser, FakeTransport, _listing

ROW = {"Ministry": "Ministry of Law", "Department": "Legislative Department", "Office": "x", "Category": "Extra Ordinary",
       "IssueDate": "09-Oct-2026", "PublishDate": "10-Oct-2026", "FileSize": "0.00 MB",
       "Subject": "The Synthetic (Amendment) Act, 2026", "PartSection": "Part II-Section 1", "UGID": "CG-DL-E-10102026-277026"}
PDF = b"%PDF-1.4 synthetic gazette"


class MonitoringEndToEndTests(unittest.TestCase):
    def test_new_gazette_act_reaches_retrieval_once_and_unchanged_is_not_refetched(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(HybridRetriever, "_active_version", return_value={"rag_index_version": "t"}), \
                patch.object(HybridRetriever, "ensure_index", return_value={"index_identity": "base-1"}):
            root = Path(directory)
            fetched: list[str] = []
            transport = FakeTransport({
                "https://egazette.gov.in/WriteReadData/2026/277026.pdf": ("application/pdf", PDF, None),
                "https://egazette.gov.in/RecentUploads": ("text/html", b"", None),
                "https://egazette.gov.in/(S(abc123))/RecentUploads.aspx": ("text/html", _listing([ROW]), None),
                "https://egazette.gov.in/": ("text/html", b"<html/>", "https://egazette.gov.in/(S(abc123))/default.aspx"),
            })
            original = transport.fetch
            transport.fetch = lambda url, **kw: fetched.append(url) or original(url, **kw)
            clock = Clock("2026-10-12T00:00:00+00:00")
            service = MonitoringService(root, {"egazette": EGazetteConnector(transport, pause_seconds=0, sleep=lambda _: None)},
                                        clock=clock, parser=FakeParser(AMENDMENT), index_updater=update_monitored_overlay,
                                        graph_mapper=lambda event: {"status": "TARGET_NOT_IN_CORPUS"})

            first = service.run_due("e2e")[0]["records"][0]
            self.assertEqual((first["status"], first["outcome"]), ("NEW", "PROCESSED"))
            self.assertEqual(first["stages"]["applicability"]["status"], "NOT_DETERMINED")
            chunks = HybridRetriever(root)._overlay_chunks()
            self.assertTrue(any("fifteen days" in chunk["text"] for chunk in chunks))
            self.assertEqual({chunk["metadata"]["review_status"] for chunk in chunks}, {"HUMAN_REVIEW_PENDING"})
            self.assertEqual(service.health()["review_queue_pending"], 1)

            self.assertEqual(service.run_due("e2e"), [])  # same day: not due, no network
            clock.value = "2026-10-13T00:00:01+00:00"
            downloads = [url for url in fetched if url.endswith(".pdf")]
            self.assertEqual(service.run_due("e2e")[0]["records"][0]["status"], "UNCHANGED")
            self.assertEqual([url for url in fetched if url.endswith(".pdf")], downloads)  # not re-downloaded

    def test_changed_listing_layout_fails_visibly_and_serves_nothing_new(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport = FakeTransport({
                "https://egazette.gov.in/RecentUploads": ("text/html", b"", None),
                "https://egazette.gov.in/(S(abc123))/RecentUploads.aspx": ("text/html", b"<html>new layout</html>", None),
                "https://egazette.gov.in/": ("text/html", b"<html/>", "https://egazette.gov.in/(S(abc123))/default.aspx"),
            })
            service = MonitoringService(root, {"egazette": EGazetteConnector(transport, pause_seconds=0, sleep=lambda _: None)},
                                        clock=Clock("2026-10-12T00:00:00+00:00"), parser=FakeParser(), index_updater=update_monitored_overlay,
                                        graph_mapper=lambda event: {"status": "TARGET_UNRESOLVED"})
            result = service.run_due("e2e")[0]
            self.assertNotEqual(result["status"], "SUCCEEDED")
            self.assertEqual(service.documents(), [])
            self.assertFalse((root / "data/runtime/rag_overlay").exists())


if __name__ == "__main__":
    unittest.main()
