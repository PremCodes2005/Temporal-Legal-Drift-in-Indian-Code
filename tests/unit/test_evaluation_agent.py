from __future__ import annotations

import unittest
from pathlib import Path

from temporal_legal_drift.evaluation_agent import ProjectEvaluationAgent


ROOT = Path(__file__).resolve().parents[2]


class ProjectEvaluationAgentTests(unittest.TestCase):
    def test_agent_reports_all_claimed_components_without_claiming_legal_approval(self) -> None:
        report = ProjectEvaluationAgent(ROOT).evaluate()
        self.assertEqual(len(report["components"]), 7)
        self.assertFalse(report["agent_policy"]["autonomous_legal_approval"])
        self.assertEqual(report["overall_status"], "incomplete_research_prototype")

    def test_agent_verifies_extreme_score_without_arithmetic_cancellation(self) -> None:
        report = ProjectEvaluationAgent(ROOT).evaluate()
        metrics = next(
            item for item in report["components"]
            if item["component"] == "evaluation_metrics"
        )
        self.assertTrue(any("70.7, not 50.0" in item for item in metrics["evidence"]))


if __name__ == "__main__":
    unittest.main()
