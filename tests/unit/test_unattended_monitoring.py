"""Unattended daily monitoring with mocked sources: schedule slot, retries the listing will not repeat, restart, missed runs,
workers in separate processes, stale sources, machine states and alerts sent once per key. No network."""

from __future__ import annotations

import json
import multiprocessing
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from temporal_legal_drift.monitoring import MonitoringService
from temporal_legal_drift.monitoring.service import deliver_alerts, next_eligible, notifications, pending_alerts

from .test_monitoring import PDF_A, PDF_B, Clock, FakeConnector, FakeParser, record

URL_1 = "https://indiacode.gov.in/server/api/core/bitstreams/a/content"
URL_2 = "https://indiacode.gov.in/server/api/core/bitstreams/b/content"
SLOT = (6, 30, "Asia/Kolkata")  # 01:00 UTC


class CursorConnector(FakeConnector):
    """Like the real India Code connector: lists only items accessioned after the cursor."""

    def discover(self, since, *, max_pages):
        return [r for r in super().discover(since, max_pages=max_pages) if since is None or r.accessioned_at > since]


class Unreachable:
    def discover(self, since, *, max_pages):
        raise AssertionError("a source was contacted")

    def download(self, url):
        raise AssertionError("a source was contacted")


class Outbox:
    def __init__(self, ok: bool = True) -> None:
        self.ok, self.messages = ok, []

    def __call__(self, message: str) -> bool:
        self.messages.append(message)
        return self.ok


def _worker(root: str, owner: str, calls: str) -> None:
    class Counting(FakeConnector):
        def discover(self, since, *, max_pages):
            with open(calls, "a", encoding="utf-8") as handle:
                handle.write(f"{owner}\n")
            return []

    service = MonitoringService(Path(root), {"india_code": Counting(), "egazette": Counting()},
                                clock=Clock("2026-10-27T01:00:00+00:00"), schedule=SLOT, sleep=lambda s: None)
    service.run_due(owner)


class UnattendedMonitoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = Clock("2026-10-27T01:00:00+00:00")
        self.india, self.gazette = CursorConnector(), CursorConnector()
        self.slept: list[float] = []
        self.service = self.make()

    def make(self, **overrides) -> MonitoringService:
        options = {"clock": self.clock, "parser": FakeParser(), "schedule": SLOT, "sleep": self.sleep,
                   "index_updater": lambda root, docs: {"status": "ACTIVATED", "documents": len(docs)},
                   "graph_mapper": lambda event: {"status": "TARGET_UNRESOLVED"}, **overrides}
        return MonitoringService(self.root, {"india_code": self.india, "egazette": self.gazette}, **options)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.advance(seconds=seconds)

    def advance(self, **delta) -> None:
        self.clock.value = (datetime.fromisoformat(self.clock.value) + timedelta(**delta)).isoformat()

    def india_run(self) -> dict:
        return next(r for r in self.service.run_due("w") if r["source_key"] == "india_code")

    def source(self, key: str = "india_code") -> dict:
        return next(s for s in self.service.health()["sources"] if s["source_key"] == key)

    # --- first run, unchanged second run, revised file ---
    def test_first_run_processes_new_records_into_machine_states_and_counts(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1)]
        self.india.payloads[URL_1] = PDF_A
        run = self.india_run()
        self.assertEqual((run["status"], run["records"][0]["machine_state"]), ("OK", "CANDIDATE_AMENDMENT"))
        source = self.source()
        self.assertEqual(source["last_run_counts"], {"listed": 1, "retried": 0, "NEW": 1})
        self.assertEqual((source["freshness"], source["stage"], source["schedule"]), ("FRESH", "IDLE", "06:30 Asia/Kolkata"))
        self.assertEqual(self.service.health()["machine_states"], {"CANDIDATE_AMENDMENT": 1})
        item = notifications(self.service)["items"][0]
        self.assertEqual(item["machine_state"], "CANDIDATE_AMENDMENT")
        candidate = self.service.candidates()[0]
        self.assertEqual(candidate["status"], "MACHINE_CANDIDATE_PENDING_REVIEW")  # never promoted to a verified amendment
        self.assertFalse(candidate["legal_effect_claimed"])

    def test_unchanged_second_run_skips_and_a_revised_file_becomes_a_new_version(self) -> None:
        self.india = FakeConnector()  # relists the same item every day
        self.service = self.make()
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1, md5="m1")]
        self.india.payloads[URL_1] = PDF_A
        self.india_run()
        self.advance(hours=24)
        unchanged = self.india_run()
        self.assertEqual(unchanged["records"][0]["status"], "UNCHANGED")
        self.assertEqual(self.source()["last_run_counts"], {"listed": 1, "retried": 0, "UNCHANGED": 1})
        self.assertEqual(len(self.india.downloads), 1)
        self.advance(hours=24)
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1, md5="m2")]
        self.india.payloads[URL_1] = PDF_B
        revised = self.india_run()["records"][0]
        self.assertEqual((revised["status"], revised["version"]), ("REVISED", 2))
        self.assertEqual(len(list((self.root / "data/raw/monitoring/sha256").rglob("*.pdf"))), 2)  # both versions kept

    # --- partial failure the incremental listing will not repeat ---
    def test_failed_download_is_retried_although_the_listing_has_moved_past_it(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1),
                              record("india_code", "item-2", "2026-10-26T11:00:00Z", URL_2)]
        self.india.payloads = {URL_1: TimeoutError("network"), URL_2: PDF_B}
        first = self.india_run()
        self.assertEqual(first["status"], "PARTIAL_FAILURE")
        self.assertEqual(self.service.health()["machine_states"], {"CANDIDATE_AMENDMENT": 1, "FAILED_RETRYING": 1})
        self.india.payloads[URL_1] = PDF_A
        self.advance(hours=24)
        second = self.india_run()
        self.assertEqual([r["official_id"] for r in second["records"]], ["item-1"])  # not relisted, retried from the ledger
        self.assertEqual((second["records"][0]["retried"], second["records"][0]["outcome"]), (True, "PROCESSED"))
        self.assertEqual(self.india.downloads, [URL_1, URL_2, URL_1])  # item-2 is not fetched again

    def test_a_document_that_keeps_failing_stops_at_unresolved(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1)]
        self.india.payloads[URL_1] = TimeoutError("network")
        for _ in range(4):
            self.india_run()
            self.advance(hours=24)
        self.assertEqual(len(self.india.downloads), 3)  # bounded attempts, then no more retries
        self.assertEqual(self.service.health()["machine_states"], {"UNRESOLVED": 1})
        failures = [a for a in pending_alerts(self.service) if a["kind"] == "DOCUMENT_FAILURE"]
        self.assertEqual(len(failures), 1)  # alerted once, when retrying stopped; not on each automatic retry
        self.assertIn("REVIEW_REQUIRED after 3 attempt(s)", failures[0]["text"])

    def test_an_item_without_a_single_pdf_is_listed_not_fetched_and_old_failures_settle_without_a_download(self) -> None:
        no_pdf = record("india_code", "item-3", "2026-10-26T12:00:00Z", None)
        self.india.records = [no_pdf]
        self.assertEqual(self.india_run()["records"][0]["status"], "METADATA_ONLY")
        self.assertEqual(self.india.downloads, [])
        # A ledger entry from before this rule: a FAILED version whose record has no PDF link.
        from dataclasses import asdict
        doc = {"schema_version": "1.0.0", "doc_id": "doc_legacy", "source_key": "india_code", "official_id": "item-0",
               "versions": [{"version": 1, "metadata_fingerprint": "x", "state": "FAILED", "attempts": 1, "error": "allowlist: None",
                             "history": [{"state": "FAILED", "at": self.clock.value, "run_id": "r"}],
                             "record": asdict(record("india_code", "item-0", "2026-10-26T09:00:00Z", None))}]}
        legacy = self.root / "data/monitoring/documents/doc_legacy.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps(doc))
        self.advance(hours=24)
        self.india.records = []
        self.india_run()
        self.assertEqual(self.india.downloads, [])
        self.assertEqual(self.service.health()["machine_states"], {"UNRESOLVED": 1})
        self.assertEqual([a["kind"] for a in pending_alerts(self.service)], [])  # an abstention, not an actionable failure
        self.assertEqual([row["status"] for row in notifications(self.service)["listed"]], ["LISTED_NOT_DOWNLOADED", "LISTED_NOT_DOWNLOADED"])

    # --- restart ---
    def test_a_crashed_run_neither_repeats_early_nor_loses_its_downloaded_document(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1)]
        self.india.payloads[URL_1] = PDF_A

        def crash(root, docs):
            raise KeyboardInterrupt("process killed")

        self.service = self.make(index_updater=crash)
        with self.assertRaises(KeyboardInterrupt):
            self.service.run_due("w")
        self.service = self.make()  # restarted process
        self.advance(hours=1)
        self.assertEqual(self.service.run_due("w"), [])
        self.assertTrue(self.source()["stage"].startswith("RUNNING"))  # the dead run's lease is visible, not hidden
        self.advance(hours=23)
        self.service.run_due("w")
        self.assertEqual(self.service.health()["machine_states"], {"CANDIDATE_AMENDMENT": 1})
        self.assertEqual(len(self.india.downloads), 1)
        self.assertEqual(self.source()["stage"], "IDLE")

    # --- schedule slot and missed runs ---
    def test_the_daily_slot_survives_start_up_jitter_without_starting_before_24_hours(self) -> None:
        self.advance(seconds=5)
        self.service.run_due("w")
        self.assertEqual(self.source()["next_eligible_at"], "2026-10-28T01:00:05+00:00")
        self.clock.value = "2026-10-28T01:00:00+00:00"  # the trigger fires 5 s before eligibility
        self.assertEqual(len(self.service.run_due("w")), 2)
        self.assertEqual(self.slept, [5.0])
        self.assertEqual(self.service.health()["sources"][0]["last_attempt_at"], "2026-10-28T01:00:05+00:00")

    def test_a_trigger_offset_from_the_slot_still_runs_every_day(self) -> None:
        self.clock.value = "2026-10-27T01:30:00+00:00"  # trigger 30 min after the 06:30 IST slot (e.g. host in another zone)
        self.service.run_due("w")
        for day in ("2026-10-28", "2026-10-29", "2026-10-30"):
            self.clock.value = f"{day}T01:30:00+00:00"
            self.assertEqual(len(self.service.run_due("w")), 2, day)

    def test_a_missed_slot_is_caught_up_once_then_the_run_returns_to_its_slot(self) -> None:
        self.service.run_due("w")
        self.clock.value = "2026-10-29T05:00:00+00:00"  # host asleep through the 28 Oct slot
        self.assertIn("SCHEDULER_MISSED_RUN", {a["code"] for a in self.service.health()["alerts"]})
        self.assertEqual(len(self.service.run_due("w")), 2)  # catch-up on wake
        self.assertEqual(self.source()["next_eligible_at"], "2026-10-31T01:00:00+00:00")
        self.assertEqual(next_eligible(datetime.fromisoformat("2026-10-29T05:00:00+00:00"), None).isoformat(),
                         "2026-10-30T05:00:00+00:00")
        self.clock.value = "2026-10-30T05:00:00+00:00"
        self.assertEqual(self.service.run_due("w"), [])
        self.assertEqual(self.service.health()["alerts"], [])  # waiting for the slot is not a missed run
        self.clock.value = "2026-10-31T01:00:00+00:00"
        self.assertEqual(len(self.service.run_due("w")), 2)

    # --- separate processes ---
    def test_workers_in_separate_processes_start_one_run_per_source(self) -> None:
        calls = self.root / "calls.txt"
        context = multiprocessing.get_context("fork")
        workers = [context.Process(target=_worker, args=(str(self.root), f"w{n}", str(calls))) for n in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(30)
        self.assertEqual([worker.exitcode for worker in workers], [0, 0, 0, 0])
        self.assertEqual(len(calls.read_text().splitlines()), 2)  # one discovery per source in total

    # --- stale sources and alerts ---
    def test_a_stale_source_alerts_once_per_failed_attempt(self) -> None:
        self.india.fail = OSError("portal down")
        self.service.run_due("w")
        outbox = Outbox()
        first = deliver_alerts(self.service, outbox)
        self.assertEqual(first["status"], "SENT")
        self.assertIn("INGESTION_STALE", outbox.messages[0])
        self.assertEqual(self.source()["freshness"], "NEVER_SUCCEEDED")
        self.advance(hours=3)
        self.assertEqual(deliver_alerts(self.service, outbox)["status"], "NOTHING_NEW")  # hourly checks stay quiet
        self.advance(hours=21)
        self.service.run_due("w")  # failed again: a new attempt is a new, actionable alert
        self.assertEqual(deliver_alerts(self.service, outbox)["sent"], 1)
        self.assertEqual(len(outbox.messages), 2)

    def test_new_records_are_announced_once_and_a_failed_channel_is_retried(self) -> None:
        deliver_alerts(self.service, Outbox())  # first use: baseline of an empty ledger
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1)]
        self.india.payloads[URL_1] = PDF_A
        self.advance(hours=24)
        self.service.run_due("w")
        broken = Outbox(ok=False)
        self.assertEqual(deliver_alerts(self.service, broken)["status"], "UNDELIVERED")
        self.assertEqual(deliver_alerts(self.service, None)["status"], "NO_ALERT_CHANNEL")
        outbox = Outbox()
        sent = deliver_alerts(self.service, outbox)
        self.assertEqual((sent["status"], sent["new_records"]), ("SENT", 1))
        self.assertIn("not all Indian legal changes", outbox.messages[0])
        self.assertIn("CANDIDATE_AMENDMENT", outbox.messages[0])
        self.advance(hours=24)
        self.service.run_due("w")  # same hash seen again
        self.assertEqual(deliver_alerts(self.service, outbox)["status"], "NOTHING_NEW")
        self.assertEqual(len(outbox.messages), 1)

    def test_first_use_does_not_announce_records_that_were_already_listed(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1)]
        self.india.payloads[URL_1] = PDF_A
        self.service.run_due("w")
        outbox = Outbox()
        self.assertEqual(deliver_alerts(self.service, outbox)["status"], "NOTHING_NEW")
        ledger = [json.loads(line) for line in (self.root / "data/monitoring/alerts_sent.v1.jsonl").read_text().splitlines()]
        self.assertEqual([row["delivery"] for row in ledger], ["BASELINE"])

    # --- reading never crawls ---
    def test_health_notifications_and_alerts_never_contact_a_source(self) -> None:
        self.india.records = [record("india_code", "item-1", "2026-10-26T10:00:00Z", URL_1)]
        self.india.payloads[URL_1] = PDF_A
        self.service.run_due("w")
        reader = MonitoringService(self.root, {"india_code": Unreachable(), "egazette": Unreachable()}, clock=self.clock)
        reader.health()
        notifications(reader)
        pending_alerts(reader)
        deliver_alerts(reader, Outbox())


if __name__ == "__main__":
    unittest.main()
