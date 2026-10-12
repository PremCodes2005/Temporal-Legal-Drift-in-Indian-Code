"""End-to-end case runs over real versioned artifacts; outputs are engineering traces, not legal answers."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from temporal_legal_drift.explanations.contract import build_explanation, narrate, validate_explanation
from temporal_legal_drift.orchestration import run_case
from temporal_legal_drift.versioning.consumer import GraphConsumer

ROOT = Path(__file__).resolve().parents[2]
ARBITRATION = {"case_id": "arb-s7-2016", "act": "arbitration-and-conciliation-act-1996", "section": "7", "reference_date": "2016-01-01"}


class OrchestrationTests(unittest.TestCase):
    def test_source_backed_case_traces_every_stage_and_is_idempotent(self) -> None:
        first = run_case(ROOT, ARBITRATION, write=False)
        self.assertEqual(first, run_case(ROOT, ARBITRATION, write=False))
        stages = first["stages"]
        self.assertEqual(stages["source"]["output"]["corpus_entry_id"], "arbitration-and-conciliation-act-1996")
        self.assertEqual(stages["graph"]["output"]["version_scope"], "AMENDMENT_CONTROLLED_FRAGMENT")
        self.assertEqual(stages["materiality"]["output"]["status"], "SILVER_ASSESSED")
        self.assertFalse(stages["materiality"]["output"]["is_gold"])
        explanation = stages["explanation"]["output"]
        self.assertEqual(stages["explanation"]["errors"], [])
        self.assertEqual(explanation["legal_validation"], "UNVERIFIED")
        self.assertTrue(explanation["citations"][0]["quote"] and explanation["citations"][0]["source_sha256"])
        # Applicability needs approved facts, so even a supported fragment ends for review.
        self.assertEqual(first["review_state"], "ESCALATED_UNRESOLVED")
        self.assertIn("applicability", first["unresolved_stages"])

    def test_fragment_from_an_unreliable_source_stays_unresolved(self) -> None:
        consumer = GraphConsumer(ROOT, "v4")
        it_source = next(item["source_id"] for item in consumer.graph.legal_sources if item["corpus_entry_id"] == "it-amendment-act-2008")
        real = consumer.provision_at(ARBITRATION["act"], "7", "2016-01-01")
        tainted = {**real, "source_evidence": [{**real["source_evidence"][0], "source_id": it_source}]}
        with patch.object(GraphConsumer, "provision_at", return_value=tainted):
            record = run_case(ROOT, ARBITRATION, write=False)
        self.assertEqual(record["stages"]["graph"]["status"], "UNRESOLVED")
        self.assertEqual(record["stages"]["graph"]["output"]["source_text_unreliable"], [it_source])
        self.assertEqual(record["review_state"], "ESCALATED_UNRESOLVED")

    def test_unknown_provision_abstains_without_citations(self) -> None:
        record = run_case(ROOT, {**ARBITRATION, "case_id": "missing", "section": "9999"}, write=False)
        explanation = record["stages"]["explanation"]["output"]
        self.assertEqual(record["stages"]["graph"]["status"], "UNRESOLVED")
        self.assertEqual(explanation["citations"], [])
        self.assertIn("No supported version", explanation["claims"][0]["text"])

    def test_stage_failure_is_recorded_and_downstream_is_skipped(self) -> None:
        scenario = json.loads((ROOT / "data/risk/compliance_scenarios.v1.json").read_text())["conditional_demonstrations"][0]["scenario"]
        with patch("temporal_legal_drift.orchestration.pipeline.RiskService.assess", side_effect=OSError("registry unavailable")):
            record = run_case(ROOT, {**ARBITRATION, "scenario": scenario}, write=False)
        self.assertEqual(record["stages"]["risk"]["status"], "FAILED")
        self.assertIn("registry unavailable", record["stages"]["risk"]["error"])
        self.assertEqual(record["stages"]["explanation"]["status"], "SKIPPED_UPSTREAM_FAILURE")
        self.assertEqual(record["review_state"], "ESCALATED_UNRESOLVED")

    def test_risk_scenario_runs_end_to_end_with_evidence_anchors(self) -> None:
        demo = json.loads((ROOT / "data/risk/compliance_scenarios.v1.json").read_text())["conditional_demonstrations"][0]
        case = {"case_id": "s19-demo", "act": "it-act-2000-consolidated", "section": "19",
                "reference_date": demo["scenario"]["reference_date"], "scenario": demo["scenario"]}
        record = run_case(ROOT, case, write=False)
        risk = record["stages"]["risk"]["output"]
        explanation = record["stages"]["explanation"]["output"]
        self.assertEqual(record["stages"]["explanation"]["errors"], [])
        self.assertEqual(explanation["risk"]["risk_level"], risk["risk_level"])
        self.assertIn("historical_applicability_stipulated_for_demonstration", explanation["uncertainty"])
        self.assertTrue({"obligation", "temporal"} <= {item["role"] for item in explanation["citations"]})
        self.assertEqual(record["stages"]["graph"]["status"], "UNRESOLVED")  # graph does not support the stipulation

    def test_case_input_is_validated(self) -> None:
        for bad in ({**ARBITRATION, "reference_date": "01/01/2016"}, {**ARBITRATION, "drift_score": 90}, {"act": "x"}):
            with self.assertRaises(ValueError):
                run_case(ROOT, bad, write=False)


class ExplanationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = run_case(ROOT, ARBITRATION, write=False)
        self.trace = {"correlation_id": self.record["correlation_id"], "case": self.record["case"],
                      "stages": {k: v for k, v in self.record["stages"].items() if k != "explanation"}}
        self.explanation = build_explanation(self.trace)

    def test_validator_rejects_unsupported_dates_anchors_and_completeness_claims(self) -> None:
        self.assertEqual(validate_explanation(self.explanation, self.trace), [])
        for mutate in (
            lambda e: e["claims"].append({"text": "In force from 1999-01-01.", "anchors": []}),
            lambda e: e["claims"].append({"text": "x", "anchors": ["anc_invented"]}),
            lambda e: e["provision"].update(is_complete_consolidated_text=True),
            lambda e: e["citations"][0].update(quote="fabricated"),
            lambda e: e["escalation"].update(required=False),
        ):
            broken = copy.deepcopy(self.explanation)
            mutate(broken)
            self.assertTrue(validate_explanation(broken, self.trace))

    def test_constrained_rephrase_is_accepted_only_when_it_keeps_the_contract(self) -> None:
        good = json.dumps({"claims": [{"text": f"Plainly: {c['text']}", "anchors": c["anchors"]} for c in self.explanation["claims"]]})
        accepted = narrate(self.explanation, self.trace, lambda messages: good, "injected")
        self.assertEqual(accepted["generation"]["method"], "llm_constrained_rephrase")
        self.assertEqual(validate_explanation(accepted, self.trace), [])
        bad = json.dumps({"claims": [{"text": "The law changed on 2001-02-03.", "anchors": []}]})
        rejected = narrate(self.explanation, self.trace, lambda messages: bad, "injected")
        self.assertEqual(rejected["generation"]["method"], "deterministic_template")
        self.assertIn("model output rejected", rejected["generation"]["fallback_reason"])
        self.assertEqual(rejected["claims"], self.explanation["claims"])
        timeout = narrate(self.explanation, self.trace, lambda messages: (_ for _ in ()).throw(TimeoutError()), "injected")
        self.assertIn("TimeoutError", timeout["generation"]["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
