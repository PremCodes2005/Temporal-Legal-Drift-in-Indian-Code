"""The rule-drift field weights: stated rationale, arithmetic and held-out sensitivity (rule-drift-v1.2; weights unchanged)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from temporal_legal_drift.webapp.service import DashboardService

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "configs/metrics/rule_drift.v1.2.json").read_text())
REPORT = json.loads((ROOT / "reports/fingerprint/rule_weights_sensitivity.v1.json").read_text())


class RuleWeightTests(unittest.TestCase):
    def test_the_active_weights_are_unchanged_and_total_100(self) -> None:
        weights = {name: row["weight"] for name, row in CONFIG["fields"].items()}
        self.assertEqual(weights, {"modality": 25, "penalty": 15, "threshold": 15, "deadline": 15, "exception": 10, "scope": 10, "actor": 5, "action": 5})
        self.assertEqual(sum(weights.values()), 100)
        self.assertEqual(CONFIG["contract"], "rule-drift-v1.2")

    def test_the_rationale_states_each_tier_once_and_its_honest_status(self) -> None:
        rationale = CONFIG["weights_rationale"]
        tiers = {field: tier["weight"] for tier in rationale["tiers"] for field in tier["fields"]}
        self.assertEqual(tiers, {name: row["weight"] for name, row in CONFIG["fields"].items()})
        self.assertEqual([tier["weight"] for tier in rationale["tiers"]], [25, 15, 10, 5])
        self.assertRegex(rationale["status"], r"not learned from data, not optimised and not reviewed or approved by a legal expert")
        self.assertIn("lower bound", rationale["counting"])
        self.assertIn("once", rationale["counting"])
        self.assertIn("separate from the 0.2 / 0.3 / 0.4 / 0.1 weights of the combined indicator", rationale["not_the_combined_weights"])

    def test_the_sensitivity_check_reproduces_the_stored_scores_and_keeps_weights_summing_to_100(self) -> None:
        self.assertEqual(REPORT["invariant_violations"], [])
        self.assertEqual(REPORT["transitions_scored"], 59)
        for name, row in REPORT["weightings"].items():
            self.assertAlmostEqual(sum(row["weights"].values()), 100, msg=name)
        self.assertEqual(REPORT["weightings"]["current"]["spearman_vs_current"], 1.0)
        self.assertGreaterEqual(min(row["ordered_pairs_kept_percent"] for row in REPORT["weightings"].values()), 99.9)

    def test_the_method_endpoint_serves_the_rule_weights_apart_from_the_combined_weights(self) -> None:
        method = DashboardService(ROOT).rule_drift_method()
        self.assertEqual(method["version"], "rule-drift-v1.2")
        self.assertEqual([row["weight"] for row in method["fields"]], [25, 15, 15, 15, 10, 10, 5, 5])
        self.assertEqual(set(method["sensitivity"]["weightings"]), {"current", "equal", "flatter_tiers", "no_heuristic_discount", "core_heavy"})
        self.assertNotIn("legal_effect", json.dumps(method))  # the TLDS components belong to /api/methods/tlds


if __name__ == "__main__":
    unittest.main()
