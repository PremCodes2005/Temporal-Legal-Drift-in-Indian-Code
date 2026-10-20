"""Latest-amendment notifications (source-notifications-v1): read only from the monitoring ledger, with a fake clock; no network."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from temporal_legal_drift.monitoring import MonitoringService
from temporal_legal_drift.monitoring.service import ITEM_STATUS, notifications
from temporal_legal_drift.review import ReviewLedger

from .test_monitoring import PDF_A, Clock, FakeConnector, FakeParser, record


class NotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = Clock("2026-10-12T00:00:00+00:00")
        self.india, self.gazette = FakeConnector(), FakeConnector()
        self.service = MonitoringService(self.root, {"india_code": self.india, "egazette": self.gazette}, clock=self.clock,
                                         parser=FakeParser(), index_updater=lambda root, docs: {"status": "ACTIVATED"},
                                         graph_mapper=lambda event: {"status": "TARGET_UNRESOLVED"})

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def later(self, hours: int) -> None:
        from datetime import datetime, timedelta
        self.clock.value = (datetime.fromisoformat(self.clock.value) + timedelta(hours=hours)).isoformat()

    def view(self) -> dict:
        return notifications(self.service, ReviewLedger(self.root))

    def downloaded(self, official_id: str, accessioned: str) -> str:
        url = f"https://indiacode.gov.in/server/api/core/bitstreams/{official_id}/content"
        self.india.records.append(record("india_code", official_id, accessioned, url))
        self.india.payloads[url] = PDF_A + official_id.encode()
        return url

    def test_an_empty_ledger_lists_nothing_and_says_no_check_succeeded(self) -> None:
        out = self.view()
        self.assertEqual((out["items"], out["listed"], out["total"]), ([], [], 0))
        self.assertEqual({row["state"] for row in out["sources"]}, {"NEVER_SUCCEEDED"})
        self.assertIn("Not a complete list of Indian amendments", out["scope"])

    def test_documents_carry_provenance_and_official_links_newest_first(self) -> None:
        self.downloaded("first", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        self.later(25)
        self.downloaded("second", "2026-10-02T00:00:00Z")
        self.service.run_due("w1")
        out = self.view()
        self.assertEqual([row["id"] for row in out["items"]], ["second", "first"])  # newest discovery first
        for row in out["items"]:
            self.assertEqual((row["source_key"], row["source"]), ("india_code", "India Code"))
            self.assertTrue(row["official_url"].startswith("https://indiacode.gov.in/"))
            self.assertEqual(row["published"], {"first": "2026-10-01", "second": "2026-10-02"}[row["id"]])
            self.assertFalse(row["legal_effect_claimed"])
        self.assertLess(out["items"][1]["discovered_at"], out["items"][0]["discovered_at"])

    def test_a_record_seen_in_several_runs_is_one_item_with_its_first_discovery_time(self) -> None:
        self.downloaded("same", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        first = self.view()["items"][0]["discovered_at"]
        self.later(25)
        self.service.run_due("w1")  # observed again, unchanged
        out = self.view()
        self.assertEqual([row["id"] for row in out["items"]], ["same"])
        self.assertEqual(out["items"][0]["discovered_at"], first)
        self.assertGreater(out["items"][0]["last_checked_at"], first)

    def test_status_wording_never_claims_a_change_to_law(self) -> None:
        for label in ITEM_STATUS.values():
            self.assertNotRegex(label.casefold(), r"\b(?:confirmed|in force|commenced|changed the law|verified amendment)\b")
        self.downloaded("candidate", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        row = self.view()["items"][0]
        self.assertEqual(row["status"], "CANDIDATE_UNVERIFIED")  # the fake parser yields amendment text
        self.assertIn("not verified", row["status_label"])
        self.assertGreater(row["candidate_events"], 0)

    def test_review_ledger_progress_is_reported_as_it_is(self) -> None:
        self.downloaded("reviewed", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        queue_id = self.view()["items"][0]["queue_id"]
        (self.root / "configs/review").mkdir(parents=True)
        (self.root / "configs/review/reviewers.v1.json").write_text(json.dumps({"reviewers": {"eng": {"role": "engineering", "qualified_legal_reviewer": False}}}))
        ReviewLedger(self.root).record(subject_id=queue_id, initial_state="HUMAN_REVIEW_PENDING", action="ESCALATE", reviewer_id="eng",
                                       reason="needs a qualified lawyer", expected_prior_state="HUMAN_REVIEW_PENDING")
        row = self.view()["items"][0]
        self.assertEqual((row["status"], row["status_label"]), ("ESCALATED_FOR_QUALIFIED_REVIEW", "Escalated for qualified legal review"))

    def test_listings_not_downloaded_are_kept_apart_from_documents(self) -> None:
        self.downloaded("doc", "2026-10-01T00:00:00Z")
        url = "https://egazette.gov.in/WriteReadData/2026/1.pdf"
        self.gazette.records.append(record("egazette", "notice", "2026-10-01T00:00:00Z", url, eligible=False))
        self.service.run_due("w1")
        out = self.view()
        self.assertEqual([row["id"] for row in out["items"]], ["doc"])
        self.assertEqual([(row["id"], row["status_label"]) for row in out["listed"]], [("notice", "Listed by the source; document not downloaded")])

    def test_stale_and_failed_sources_are_stated(self) -> None:
        self.downloaded("doc", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        self.assertEqual({row["state"] for row in self.view()["sources"]}, {"OK"})
        self.later(25)
        self.india.fail = OSError("connection refused")
        self.service.run_due("w1")
        self.later(49)
        states = {row["source_key"]: row for row in self.view()["sources"]}
        self.assertEqual(states["india_code"]["state"], "FAILED")
        self.assertIn("source unavailable", states["india_code"]["detail"])
        self.assertIn("No successful check for 74 hours", states["india_code"]["detail"])
        self.assertEqual(states["egazette"]["state"], "STALE")
        self.assertEqual([row["id"] for row in self.view()["items"]], ["doc"])  # earlier items stay listed

    def test_a_link_outside_the_official_hosts_is_never_offered(self) -> None:
        self.downloaded("doc", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        path = next((self.root / "data/monitoring/review_queue").glob("*.json"))
        item = json.loads(path.read_text())
        path.write_text(json.dumps({**item, "canonical_url": "https://example.com/fake.pdf"}))
        self.assertIsNone(self.view()["items"][0]["official_url"])

    def test_reading_notifications_never_fetches(self) -> None:
        self.downloaded("doc", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        calls = (self.india.discover_calls, len(self.india.downloads))
        self.view()
        self.assertEqual((self.india.discover_calls, len(self.india.downloads)), calls)


    # ---------- source-notifications-v2 ----------
    def test_the_latest_five_records_come_first_and_older_ones_stay_available(self) -> None:
        for day in range(7):
            self.downloaded(f"doc{day}", f"2026-10-0{day + 1}T00:00:00Z")
            self.service.run_due("w1")
            self.later(25)
        out = self.view()
        self.assertEqual([row["id"] for row in out["latest"]], ["doc6", "doc5", "doc4", "doc3", "doc2"])
        self.assertEqual([row["id"] for row in out["older"]], ["doc1", "doc0"])
        self.assertEqual(out["total"], 7)

    def test_fewer_than_five_records_are_never_padded(self) -> None:
        self.downloaded("only", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        out = self.view()
        self.assertEqual(([row["id"] for row in out["latest"]], out["older"]), (["only"], []))

    def test_a_repeat_check_is_not_a_new_record_but_a_revised_pdf_is(self) -> None:
        url = self.downloaded("doc", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        first = [row["key"] for row in self.view()["latest"]]
        self.later(25)
        self.service.run_due("w1")  # same bytes again
        self.assertEqual([row["key"] for row in self.view()["latest"]], first)
        self.later(25)
        self.india.records[:] = [record("india_code", "doc", "2026-10-03T00:00:00Z", url, md5="m2")]
        self.india.payloads[url] = PDF_A + b" revised"
        self.service.run_due("w1")
        keys = [row["key"] for row in self.view()["latest"]]
        self.assertEqual(len(keys), 2)
        self.assertTrue(all(key.startswith("doc:") for key in keys))
        self.assertEqual(len(set(keys)), 2)  # same official id, two content hashes

    def test_the_same_bytes_under_two_official_ids_are_one_record(self) -> None:
        for official_id in ("first-id", "second-id"):
            url = f"https://indiacode.gov.in/server/api/core/bitstreams/{official_id}/content"
            self.india.records.append(record("india_code", official_id, "2026-10-01T00:00:00Z", url))
            self.india.payloads[url] = PDF_A
        self.service.run_due("w1")
        latest = self.view()["latest"]
        self.assertEqual(len(latest), 1)
        self.assertEqual(sorted([latest[0]["id"]] + latest[0].get("same_document_ids", [])), ["first-id", "second-id"])

    def test_categories_keep_new_documents_possible_amendments_and_verified_amendments_apart(self) -> None:
        self.downloaded("candidate", "2026-10-01T00:00:00Z")
        self.service.run_due("w1")
        out = self.view()
        self.assertEqual(out["latest"][0]["category_label"], "Possible amendment awaiting review")
        counts = {row["category"]: row["count"] for row in out["categories"]}
        self.assertEqual(counts, {"NEW_DOCUMENT": 0, "POSSIBLE_AMENDMENT": 1, "VERIFIED_AMENDMENT": 0})
        verified = next(row for row in out["categories"] if row["category"] == "VERIFIED_AMENDMENT")
        self.assertIn("nothing is in this category", verified["note"])


if __name__ == "__main__":
    unittest.main()
