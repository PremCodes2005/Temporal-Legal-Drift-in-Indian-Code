"""Exercise real HTTP routing and the repository-backed risk service."""

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from temporal_legal_drift.webapp.server import DashboardRequestHandler
from temporal_legal_drift.webapp.service import DashboardService

ROOT = Path(__file__).resolve().parents[2]


class RiskApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(DashboardRequestHandler):
            project_root = ROOT
            static_root = ROOT / "web"
            dashboard_service = DashboardService(ROOT)

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def catalog(self):
        with urlopen(self.url + "/api/risk/catalog", timeout=5) as response:
            return json.load(response)

    def post(self, scenario):
        request = Request(self.url + "/api/risk/assess", data=json.dumps(scenario).encode(), headers={"Content-Type": "application/json"})
        return urlopen(request, timeout=5)

    def test_catalog_and_conditional_pre_post_results(self):
        catalog = self.catalog()
        self.assertEqual(len(catalog["scenarios"]), 13)
        self.assertFalse(catalog["drift_used_in_risk"])
        flags = []
        for row in catalog["conditional_demonstrations"]:
            with self.post(row["scenario"]) as response:
                result = json.load(response)
            self.assertEqual(result["risk_level"], row["expected"]["risk_level"])
            self.assertEqual(result["legal_validation"], "UNVERIFIED")
            self.assertTrue(result["evidence"])
            flags.append(result["risk_flag"])
        self.assertEqual(flags, [True, False])

    def test_empty_scaffold_returns_unknown_not_zero_risk(self):
        with self.post(self.catalog()["scenarios"][0]["scenario"]) as response:
            result = json.load(response)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result["risk_level"])

    def test_client_cannot_supply_drift_or_replace_server_rules(self):
        scenario = self.catalog()["conditional_demonstrations"][0]["scenario"]
        for extra in ({"drift_score": 100}, {"rules": []}):
            with self.assertRaises(HTTPError) as error:
                self.post({**scenario, **extra})
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
