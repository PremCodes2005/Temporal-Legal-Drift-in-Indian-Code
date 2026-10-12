"""Review ledger and run/review HTTP routes on an isolated temporary project root."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from temporal_legal_drift.jsonio import canonical_json_bytes
from temporal_legal_drift.orchestration import run_case
from temporal_legal_drift.review import ReviewLedger, ReviewRejected
from temporal_legal_drift.webapp.server import DashboardRequestHandler
from temporal_legal_drift.webapp.service import DashboardService

ROOT = Path(__file__).resolve().parents[2]
CASE = {"case_id": "arb-s7-2016", "act": "arbitration-and-conciliation-act-1996", "section": "7", "reference_date": "2016-01-01"}


class ReviewApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        (cls.root / "configs/review").mkdir(parents=True)
        shutil.copy2(ROOT / "configs/review/reviewers.v1.json", cls.root / "configs/review/reviewers.v1.json")
        cls.record = run_case(ROOT, CASE, write=False)  # computed on real artifacts, stored in the temp root
        (cls.root / "data/runs").mkdir(parents=True)
        (cls.root / "data/runs" / f"{cls.record['correlation_id']}.json").write_bytes(canonical_json_bytes(cls.record))

        class Handler(DashboardRequestHandler):
            project_root = cls.root
            static_root = ROOT / "web"
            dashboard_service = DashboardService(cls.root)

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temporary.cleanup()

    def request(self, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def test_review_flow_is_append_only_attributed_and_never_legal_approval(self) -> None:
        run_id = self.record["correlation_id"]
        status, run = self.request(f"/api/runs/{run_id}")
        self.assertEqual(status, 200)
        self.assertEqual(run["review_state"], "ESCALATED_UNRESOLVED")
        review = {"subject_id": run_id, "reviewer_id": "project-engineer", "action": "ACKNOWLEDGE",
                  "reason": "Checked the fragment against the cited page.", "expected_prior_state": "ESCALATED_UNRESOLVED"}
        status, result = self.request("/api/reviews", review)
        self.assertEqual(status, 201)
        entry = result["entry"]
        self.assertEqual((entry["prior_state"], entry["new_state"]), ("ESCALATED_UNRESOLVED", "REVIEW_ACKNOWLEDGED"))
        self.assertEqual(entry["reviewer_role"], "unqualified_engineering_review")
        self.assertFalse(entry["qualified_legal_reviewer"])
        self.assertEqual(entry["legal_validation"], "UNVERIFIED")
        self.assertTrue(entry["recorded_at"])
        # A stale prior state is refused instead of silently overwritten.
        status, error = self.request("/api/reviews", review)
        self.assertEqual(status, 400)
        self.assertIn("reload", error["error"])
        for bad in ({**review, "reviewer_id": "anyone"}, {**review, "reason": "ok"},
                    {**review, "action": "APPROVE_AS_LAW", "expected_prior_state": "REVIEW_ACKNOWLEDGED"},
                    {**review, "subject_id": "run_" + "0" * 24}):
            self.assertEqual(self.request("/api/reviews", bad)[0], 400)
        status, run = self.request(f"/api/runs/{run_id}")
        self.assertEqual(len(run["review_history"]), 1)
        self.assertEqual(run["ledger_integrity_errors"], [])

    def test_run_routes_validate_identifiers(self) -> None:
        self.assertEqual(self.request("/api/runs/../../etc")[0], 400)
        self.assertEqual(self.request("/api/runs/run_" + "f" * 24)[0], 404)
        status, listing = self.request("/api/runs")
        self.assertEqual(status, 200)
        self.assertEqual(listing["legal_validation"], "UNVERIFIED")
        self.assertEqual(self.request("/api/runs", {**CASE, "reference_date": "yesterday"})[0], 400)


class LedgerIntegrityTests(unittest.TestCase):
    def test_tampering_is_detected_and_blocks_further_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "configs/review").mkdir(parents=True)
            shutil.copy2(ROOT / "configs/review/reviewers.v1.json", root / "configs/review/reviewers.v1.json")
            ledger = ReviewLedger(root)
            ledger.record(subject_id="run_a", initial_state="PENDING_REVIEW", action="ESCALATE",
                          reviewer_id="project-engineer", reason="Needs a qualified reviewer.", expected_prior_state="PENDING_REVIEW")
            ledger.record(subject_id="run_a", initial_state="PENDING_REVIEW", action="RECORD_OPINION",
                          reviewer_id="project-engineer", reason="Fragment wording matches the page.",
                          expected_prior_state="ESCALATED_FOR_QUALIFIED_REVIEW")
            self.assertEqual(ledger.verify(), [])
            lines = ledger.path.read_text().splitlines()
            ledger.path.write_text(lines[0].replace("Needs a qualified", "Approved by a qualified") + "\n" + lines[1] + "\n")
            self.assertTrue(ledger.verify())
            with self.assertRaises(ReviewRejected):
                ledger.record(subject_id="run_a", initial_state="PENDING_REVIEW", action="ACKNOWLEDGE",
                              reviewer_id="project-engineer", reason="Trying to append after tampering.",
                              expected_prior_state="OPINION_RECORDED")


if __name__ == "__main__":
    unittest.main()
