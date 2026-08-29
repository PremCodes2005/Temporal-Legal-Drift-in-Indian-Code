from __future__ import annotations

import unittest
from pathlib import Path

from temporal_legal_drift.gates import check_engineering_gates


ROOT = Path(__file__).resolve().parents[2]


class EngineeringGateTests(unittest.TestCase):
    def test_phase_0_to_11_engineering_gates_pass_without_faking_review(self) -> None:
        results = check_engineering_gates(ROOT)
        self.assertEqual([result.phase for result in results], list(range(12)))
        self.assertTrue(all(result.engineering_passed for result in results))
        self.assertTrue(all(result.review_status.startswith("pending") for result in results[:4]))
        self.assertEqual(
            results[4].review_status,
            "internal_cross_source_validation_passed_external_legal_review_not_performed",
        )
        self.assertEqual(
            results[5].review_status,
            "technical_annotation_workload_passed_research_annotation_not_performed",
        )
        self.assertEqual(
            results[6].review_status,
            "technical_scenario_scaffolds_passed_expert_scenarios_not_authored",
        )
        self.assertEqual(
            results[7].review_status,
            "technical_release_dry_run_passed_benchmark_not_frozen",
        )
        self.assertEqual(
            results[8].review_status,
            "baseline_framework_passed_evaluation_not_run_without_gold",
        )
        self.assertEqual(
            results[9].review_status,
            "controlled_llm_pipeline_executed_performance_unscored_without_gold",
        )
        self.assertEqual(
            results[10].review_status,
            "automated_explanation_support_evaluated_legal_quality_unscored",
        )
        self.assertEqual(
            results[11].review_status,
            "fresh_environment_reproduction_passed_independent_expert_review_unavailable",
        )
        self.assertTrue(all(result.review_blockers for result in results))


if __name__ == "__main__":
    unittest.main()
