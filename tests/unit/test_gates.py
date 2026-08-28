from __future__ import annotations

import unittest
from pathlib import Path

from temporal_legal_drift.gates import check_engineering_gates


ROOT = Path(__file__).resolve().parents[2]


class EngineeringGateTests(unittest.TestCase):
    def test_phase_0_to_4_engineering_gates_pass_without_faking_review(self) -> None:
        results = check_engineering_gates(ROOT)
        self.assertEqual([result.phase for result in results], [0, 1, 2, 3, 4])
        self.assertTrue(all(result.engineering_passed for result in results))
        self.assertTrue(all(result.review_status.startswith("pending") for result in results[:4]))
        self.assertEqual(
            results[4].review_status,
            "internal_cross_source_validation_passed_external_legal_review_not_performed",
        )
        self.assertTrue(all(result.review_blockers for result in results))


if __name__ == "__main__":
    unittest.main()
