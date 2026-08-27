from __future__ import annotations

import json
import unittest
from pathlib import Path

from temporal_legal_drift.phase0 import EXPECTED_LEVELS, validate_contract, validate_contract_file


ROOT = Path(__file__).resolve().parents[2]


class ResearchContractTests(unittest.TestCase):
    def test_repository_contract_is_valid_but_human_review_gate_is_open(self) -> None:
        result = validate_contract_file(ROOT / "configs" / "research_contract.v1.json")
        self.assertTrue(result.structurally_valid, result.errors)
        self.assertFalse(result.gate_passed)
        self.assertGreater(len(result.blockers), 0)

    def test_materiality_cannot_become_primary_or_absorb_consequence(self) -> None:
        contract = json.loads((ROOT / "configs" / "research_contract.v1.json").read_text())
        contract["materiality"]["role"] = "primary_project"
        contract["materiality"]["levels"] = ["cosmetic", "substantive"]
        contract["materiality"]["compliance_consequence_is_separate"] = False
        result = validate_contract(contract)
        self.assertFalse(result.structurally_valid)
        self.assertEqual(EXPECTED_LEVELS, ["High", "Medium", "Low", "None"])
        self.assertEqual(len(result.errors), 3)

    def test_ecfr_cannot_be_active_primary_source(self) -> None:
        contract = json.loads((ROOT / "configs" / "research_contract.v1.json").read_text())
        contract["corpus"]["primary_source_family"] = "eCFR"
        result = validate_contract(contract)
        self.assertFalse(result.structurally_valid)
        self.assertTrue(any("eCFR" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
