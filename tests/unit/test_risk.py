"""Synthetic decision-boundary tests; fixtures are not Indian legal evidence."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import fields
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import canonical_json_bytes
from temporal_legal_drift.risk import ComplianceRisk, ComplianceScenario, ObligationRule, evaluate_risk
from temporal_legal_drift.risk.builder import build_risk_artifacts, evaluate_benchmark, phase4_preflight
from temporal_legal_drift.risk.service import RiskService

ROOT = Path(__file__).resolve().parents[2]


def synthetic_fixture():
    text = "SYNTHETIC UNIT TEST ONLY. A covered company shall file within 10 calendar days, excluding the trigger day. Effective 2020-01-01."
    evidence = {role: {"evidence_id": role, "source_id": "synthetic-fixture",
        "source_sha256": sha256(text.encode()).hexdigest(), "locator": "synthetic:line:1",
        "quote": text, "source_text": text, "text_sha256": sha256(text.encode()).hexdigest(), "role": role}
        for role in ("obligation", "temporal")}
    scenario = {"scenario_id": "synthetic-deadline", "organization_type": "company", "industry": "testing",
        "jurisdiction": "TEST", "facts": {"trigger_on": "2020-01-01", "completed_on": "2020-01-12"},
        "reference_date": "2020-01-13", "applicable_provision": "synthetic:section:1", "activity": "filing",
        "exposure": {"description": "Synthetic engineering case", "amount": None}}
    rule = {"rule_id": "synthetic-deadline-v1", "provision": scenario["applicable_provision"], "provision_version": "synthetic-version-1",
        "materiality": "High", "kind": "deadline", "obligation": "File by the modelled deadline",
        "consequence": "Synthetic adverse operational consequence", "consequence_severity": "Medium",
        "scope": {k: scenario[k] for k in ("organization_type", "industry", "jurisdiction", "activity")},
        "conditions": {}, "reference_dates": [scenario["reference_date"]], "applicability_status": "RESOLVED",
        "fact_key": "completed_on", "required_value": None, "trigger_fact_key": "trigger_on", "deadline_days": 10,
        "counting_convention": "calendar_days_exclusive_trigger", "evidence_ids": list(evidence),
        "rationale": "Synthetic rule solely for testing the deterministic decision contract"}
    return scenario, rule, evidence


class ComplianceRiskTests(unittest.TestCase):
    def setUp(self):
        self.scenario, self.rule, self.evidence = synthetic_fixture()

    def assess(self):
        return evaluate_risk(ComplianceScenario.from_dict(self.scenario), [ObligationRule.from_dict(self.rule)], self.evidence)

    def test_deadline_false_negative_regression_late_submission_is_flagged(self):
        result = self.assess()
        self.assertTrue(result.risk_flag)
        self.assertEqual((result.risk_level, result.urgency), ("Medium", "IMMEDIATE"))

    def test_deadline_false_positive_regression_on_time_and_exact_boundary(self):
        for completed in ("2020-01-01", "2020-01-10", "2020-01-11"):
            with self.subTest(completed=completed):
                self.scenario["facts"]["completed_on"] = completed
                result = self.assess()
                self.assertFalse(result.risk_flag)
                self.assertEqual(result.risk_level, "None")

    def test_active_deadline_change_can_remove_risk_without_drift_input(self):
        self.assertTrue(self.assess().risk_flag)
        self.rule["deadline_days"] = 15
        self.assertFalse(self.assess().risk_flag)

    def test_missing_completion_and_explicit_noncompletion_are_different(self):
        del self.scenario["facts"]["completed_on"]
        self.assertIsNone(self.assess().risk_flag)
        self.scenario["facts"]["completed_on"] = None
        self.assertTrue(self.assess().risk_flag)

    def test_pending_deadline_is_not_a_present_violation(self):
        self.scenario["facts"]["completed_on"] = None
        for day, urgency in (("2020-01-02", "ROUTINE"), ("2020-01-10", "SOON"), ("2020-01-11", "SOON")):
            self.scenario["reference_date"] = day
            self.rule["reference_dates"] = [day]
            result = self.assess()
            self.assertFalse(result.risk_flag)
            self.assertEqual(result.urgency, urgency)

    def test_future_completion_or_trigger_is_not_treated_as_known_fact(self):
        for key in ("completed_on", "trigger_on"):
            scenario = copy.deepcopy(self.scenario)
            self.scenario["facts"][key] = "2020-02-01"
            self.assertEqual(self.assess().status, "REVIEW_REQUIRED")
            self.scenario = scenario

    def test_unknown_and_conflicting_applicability_abstain(self):
        self.rule["applicability_status"] = "UNRESOLVED"
        self.assertIsNone(self.assess().risk_level)
        self.rule["applicability_status"] = "RESOLVED"
        r = ObligationRule.from_dict(self.rule)
        output = evaluate_risk(ComplianceScenario.from_dict(self.scenario), [r, r], self.evidence)
        self.assertEqual(output.status, "REVIEW_REQUIRED")
        self.scenario["reference_date"] = "2021-01-13"
        self.assertIsNone(self.assess().risk_flag)

    def test_wrong_jurisdiction_is_not_a_false_positive(self):
        self.scenario["jurisdiction"] = "OTHER"
        self.assertEqual(self.assess().status, "NOT_APPLICABLE")
        self.assertFalse(self.assess().risk_flag)

    def test_materiality_does_not_set_risk(self):
        values = []
        for label in (None, "None", "Low", "Medium", "High"):
            self.rule["materiality"] = label
            result = self.assess()
            values.append((result.risk_level, result.risk_flag, result.urgency))
        self.assertEqual(len(set(values)), 1)
        self.scenario["facts"]["completed_on"] = "2020-01-10"
        self.assertEqual(self.assess().risk_level, "None")

    def test_drift_fields_are_rejected_and_do_not_enter_risk_api(self):
        for key in ("drift_score", "similarity", "risk_level"):
            with self.assertRaises(ValueError):
                ComplianceScenario.from_dict({**self.scenario, key: 100})

    def test_invalid_types_and_nonfinite_exposure_rejected(self):
        for amount in (True, float("nan"), float("inf"), -1):
            with self.assertRaises(ValueError):
                ComplianceScenario.from_dict({**self.scenario, "exposure": {"description": None, "amount": amount}})
        with self.assertRaises(ValueError):
            ObligationRule.from_dict({**self.rule, "deadline_days": True})

    def test_tampered_evidence_abstains(self):
        self.evidence["obligation"]["quote"] = "This quote is not in the source."
        self.assertIsNone(self.assess().risk_flag)
        self.assertTrue(self.assess().escalation_required)

    def test_evidence_id_cannot_point_to_a_different_record(self):
        self.evidence["obligation"]["evidence_id"] = "unrelated-evidence"
        self.assertIsNone(self.assess().risk_flag)

    def test_missing_temporal_evidence_abstains(self):
        self.rule["evidence_ids"] = ["obligation"]
        self.assertEqual(self.assess().status, "INSUFFICIENT_EVIDENCE")

    def test_requirements_and_prohibitions_have_opposite_polarity(self):
        self.rule.update(kind="requirement", fact_key="permission_present", required_value=True)
        self.scenario["facts"]["permission_present"] = True
        self.assertFalse(self.assess().risk_flag)
        self.rule["kind"] = "prohibition"
        self.assertTrue(self.assess().risk_flag)
        self.scenario["facts"]["permission_present"] = "true"
        self.assertIsNone(self.assess().risk_flag)

    def test_reproducibility_and_input_immutability(self):
        original = copy.deepcopy((self.scenario, self.rule, self.evidence))
        self.assertEqual(self.assess(), self.assess())
        self.assertEqual(original, (self.scenario, self.rule, self.evidence))
        risk_id = self.assess().risk_id
        self.scenario["facts"]["completed_on"] = "2020-01-10"
        self.assertNotEqual(risk_id, self.assess().risk_id)

    def test_schema_fields_match_runtime_contracts(self):
        for model, name in ((ComplianceScenario, "compliance_scenario"), (ComplianceRisk, "compliance_risk")):
            schema = json.loads((ROOT / f"schemas/risk/{name}.v1.schema.json").read_text())
            self.assertEqual(set(schema["required"]), {f.name for f in fields(model)})
            self.assertFalse(schema["additionalProperties"])

    def test_phase4_preflight_and_migration_do_not_overwrite_originals(self):
        paths = [ROOT / "data/silver/materiality_silver_labels.v1.json", ROOT / "data/scenarios/phase6_scaffolds.v1.json"]
        original = [p.read_bytes() for p in paths]
        self.assertTrue(phase4_preflight(ROOT)["engineering_preflight_passed"])
        artifacts = build_risk_artifacts(ROOT)
        self.assertEqual(len(artifacts["benchmark"]["scenarios"]), 13)
        self.assertTrue(artifacts["evaluation"]["all_expected_behavior_checks_passed"])
        self.assertEqual(artifacts["evaluation"]["expert_validated_scenario_count"], 0)
        self.assertIsNone(artifacts["evaluation"]["legal_false_negative_rate"])
        self.assertEqual(original, [p.read_bytes() for p in paths])
        changed = copy.deepcopy(artifacts["benchmark"])
        changed["conditional_demonstrations"][0]["expected"]["risk_flag"] = False
        comparison = evaluate_benchmark(changed, artifacts["registry"])
        self.assertFalse(comparison["all_expected_behavior_checks_passed"])
        self.assertEqual([r["result"] for r in comparison["results"]], [r["result"] for r in artifacts["evaluation"]["results"]])

    def test_registry_rejects_changed_input_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/risk").mkdir(parents=True)
            (root / "data/risk/obligation_registry.v1.json").write_bytes(canonical_json_bytes({"input_sha256": {"missing.pdf": "0" * 64}}))
            with self.assertRaisesRegex(ValueError, "changed or missing"):
                RiskService(root).assess(self.scenario)


if __name__ == "__main__":
    unittest.main()
