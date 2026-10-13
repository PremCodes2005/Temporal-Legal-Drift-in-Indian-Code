"""rag-answer-v4: stable analysis IDs, stored results, minimum facts and the evidence/facts/method separation."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from temporal_legal_drift.rag.analysis import facts_from_question, load, store
from temporal_legal_drift.rag.rag_pipeline import RagPipeline

ROOT = Path(__file__).resolve().parents[2]
IT19 = "Compare Section 19 before and after the IT Amendment Act, 2008."
DM31 = "How often must the district disaster management plan be reviewed under section 31 of the Disaster Management Act after the 2025 amendment?"


class AnalysisRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._env = {k: os.environ.get(k) for k in ("TLD_LIVE_INDIA_CODE", "TLD_RAG_PROVIDER", "TLD_RAG_API_KEY", "OPENAI_API_KEY")}
        os.environ.update({"TLD_LIVE_INDIA_CODE": "0", "TLD_RAG_PROVIDER": "openai_compatible", "TLD_RAG_API_KEY": "", "OPENAI_API_KEY": ""})
        cls.pipeline = RagPipeline(ROOT)

    @classmethod
    def tearDownClass(cls) -> None:
        for name, value in cls._env.items():
            os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value)

    def test_same_inputs_same_id_different_facts_different_id(self) -> None:
        first, again = self.pipeline.answer(IT19, "specific"), self.pipeline.answer(IT19, "specific")
        self.assertEqual(first["analysis_id"], again["analysis_id"])
        self.assertNotEqual(first["analysis_id"], self.pipeline.answer(IT19, "generic")["analysis_id"])
        self.assertNotEqual(first["analysis_id"], self.pipeline.answer(IT19, "specific", scenario={"reference_date": "2010-01-01"})["analysis_id"])
        with patch("temporal_legal_drift.rag.rag_pipeline.DETERMINATIONS_VERSION", "determinations-vX"):  # a method change never reuses a stored record
            self.assertNotEqual(first["analysis_id"], self.pipeline.answer(IT19, "specific")["analysis_id"])

    def test_a_stored_analysis_is_returned_unchanged_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            response = self.pipeline.answer(DM31, "specific", scenario={"facts": {"elapsed_months": 18}})
            stored = store(Path(directory), response)
            reloaded = load(Path(directory), response["analysis_id"])
            self.assertEqual(reloaded, json.loads(json.dumps(response)))
            self.assertEqual(reloaded["fingerprint"]["wording_drift"]["details"]["spans"], stored["fingerprint"]["wording_drift"]["details"]["spans"])
            with self.assertRaises(ValueError):
                load(Path(directory), "../../etc/passwd")
            with self.assertRaises(KeyError):
                load(Path(directory), "an_" + "0" * 24)

    def test_http_round_trip_by_analysis_id(self) -> None:
        from temporal_legal_drift.webapp.service import DashboardService

        from unittest.mock import PropertyMock

        with tempfile.TemporaryDirectory() as directory, patch.object(DashboardService, "rag", new_callable=PropertyMock, return_value=self.pipeline):
            service = DashboardService(Path(directory))
            posted = service.query_rag({"query": DM31, "mode": "specific", "scenario": {"facts": {"elapsed_months": 18}}})
            self.assertEqual(service.get_analysis(posted["analysis_id"]), posted)  # every view reads this same record
            self.assertTrue((Path(directory) / "data/runtime/analyses" / f"{posted['analysis_id']}.json").is_file())

    def test_minimum_facts_are_grouped_deduplicated_and_never_offered_for_missing_evidence(self) -> None:
        request = self.pipeline.answer(IT19, "specific")["scenario_request"]
        keys = [row["key"] for row in request["fields"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys[0], "reference_date")
        core = {row["key"] for row in request["fields"] if row["group"] == "core"}
        self.assertIn("facts.is_digital_signature", core)  # unlocks the before/after comparison under the modelled rules
        self.assertTrue(all(row["unlocks"] for row in request["fields"]))  # every requested fact says what it unlocks
        wrong = self.pipeline.answer("Compare section 46 of the Companies Act before and after the Competition (Amendment) Act, 2023.", "specific")
        self.assertEqual(wrong["scenario_request"]["fields"], [])  # facts cannot repair missing evidence
        self.assertIn("whether your answer changes", wrong["scenario_request"]["blocked_by_evidence"])

    def test_facts_written_in_the_question_are_applied_and_attributed(self) -> None:
        self.assertEqual(facts_from_question("After 18 months without a review, is the plan overdue?"), {"elapsed_months": 18})
        result = self.pipeline.answer("After 18 months without a review, is the district disaster management plan overdue under section 31 of the Disaster Management Act after the 2025 amendment?", "specific")
        self.assertEqual(result["fingerprint"]["outcome_drift"]["label"], "Changed")
        self.assertEqual(result["scenario_request"]["facts_in_use"], {"facts.elapsed_months": "question"})

    def test_evidence_facts_and_method_limits_are_distinct(self) -> None:
        it19 = self.pipeline.answer(IT19, "specific")
        self.assertEqual(it19["fingerprint"]["rule_drift"]["limit"]["kind"], "method")      # renamed term: outside the rule fields
        self.assertEqual(it19["determinations"]["applicability"]["limit"]["kind"], "facts")  # a reference date is needed
        self.assertEqual(it19["determinations"]["applicability"]["limit"]["action"]["type"], "add_facts")
        ocr = self.pipeline.answer("What changed in the IT Act amendment regarding data privacy?", "specific")
        self.assertEqual(ocr["fingerprint"]["wording_drift"]["limit"]["kind"], "evidence")
        self.assertEqual(ocr["fingerprint"]["wording_drift"]["limit"]["action"]["type"], "verify_source")

    def test_an_unscored_rule_change_never_reads_as_unchanged(self) -> None:
        outcome = self.pipeline.answer(IT19, "specific", scenario={"facts": {"within_scope": True}})["fingerprint"]["outcome_drift"]
        self.assertNotEqual(outcome["label"], "Unchanged")


if __name__ == "__main__":
    unittest.main()
