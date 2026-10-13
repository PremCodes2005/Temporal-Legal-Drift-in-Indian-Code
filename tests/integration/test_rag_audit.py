"""Cross-corpus regression: the 24-case audit set v2 (12 Acts, 15 strata) against source-derived expectations."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from temporal_legal_drift.rag.audit import offline_extractive, run_audit
from temporal_legal_drift.rag.rag_pipeline import RagPipeline

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas/rag/rag_answer.v3.schema.json").read_text())


class RagAuditRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with offline_extractive():
            cls.report = run_audit(ROOT, ROOT / "configs/rag_audit/cases.v2.json", pipeline=RagPipeline(ROOT))

    def test_no_support_pairing_or_citation_errors(self) -> None:
        summary = self.report["summary"]
        failing = {row["case_id"]: row["support_errors"] + row["pairing_errors"] + row["citation_errors"]
                   for row in self.report["cases"] if row["support_errors"] or row["pairing_errors"] or row["citation_errors"]}
        self.assertEqual(failing, {})
        self.assertEqual(summary["errors"], 0)

    def test_every_determination_state_matches_the_source_derived_expectation(self) -> None:
        mismatched = {row["case_id"]: row["state_mismatch"] for row in self.report["cases"] if row["state_mismatch"]}
        self.assertEqual(mismatched, {})


class ContractTests(unittest.TestCase):
    """Responses carry every rag-answer-v2 field and use only the declared states and roles."""

    def test_responses_follow_the_v3_contract(self) -> None:
        determination = SCHEMA["$defs"]["determination"]
        states = set(determination["properties"]["state"]["enum"])
        roles = set(SCHEMA["properties"]["evidence"]["items"]["properties"]["role"]["enum"])
        sections = set(SCHEMA["properties"]["answer"]["properties"]["sections"]["items"]["properties"]["id"]["enum"])
        with offline_extractive():
            pipeline = RagPipeline(ROOT)
            responses = [pipeline.answer(q, "specific") for q in (
                "Compare Section 19 before and after the IT Amendment Act, 2008.",
                "What does the Consumer Protection Act say about mediation?",
                "Compare section 46 of the Companies Act before and after the Competition (Amendment) Act, 2023.",
                "What does section 5 of the Shops and Commercial Establishments Act require?")]
        for response in responses:
            with self.subTest(query=response["query"]):
                self.assertLessEqual(set(SCHEMA["required"]), set(response))
                self.assertEqual((response["schema_version"], response["contract_version"]), ("3.0.0", "rag-answer-v3"))
                self.assertLessEqual(set(SCHEMA["properties"]["answer"]["required"]), set(response["answer"]))
                component = SCHEMA["$defs"]["component"]
                for name in ("wording_drift", "rule_drift", "outcome_drift"):
                    value = response["fingerprint"][name]
                    self.assertEqual(set(value), set(component["required"]))
                    self.assertIn(value["state"], set(component["properties"]["state"]["enum"]))
                    if value["state"] in {"INSUFFICIENT_EVIDENCE", "OUT_OF_SCOPE", "NEEDS_FACTS"}:
                        self.assertIsNone(value["value"])  # a missing component is never 0
                for name in ("textual_drift", "materiality", "applicability", "answer_change", "risk"):
                    value = response["determinations"][name]
                    self.assertEqual(set(value), set(determination["required"]))
                    self.assertIn(value["state"], states)
                    self.assertTrue(value["reason"] and value["summary"])
                    if value["state"] not in {"DETERMINED", "PROVISIONAL", "CONDITIONAL"}:
                        self.assertIsNone(value["label"])  # no label is shown without a supported result
                self.assertLessEqual({item["role"] for item in response["evidence"]}, roles)
                self.assertLessEqual({section["id"] for section in response["answer"]["sections"]}, sections)


if __name__ == "__main__":
    unittest.main()
