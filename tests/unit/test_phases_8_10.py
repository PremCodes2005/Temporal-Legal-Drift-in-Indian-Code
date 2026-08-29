from __future__ import annotations

import unittest

from temporal_legal_drift.baselines import (
    ClassPriorBaseline,
    MajorityBaseline,
    OperationPriorBaseline,
)
from temporal_legal_drift.explanations import evaluate_explanation_support
from temporal_legal_drift.llm_evaluation import (
    build_llm_evaluation_plan,
    build_drift_evaluation_from_executed_plan,
    normalize_structured_assertion,
    score_paired_assertions,
)
from temporal_legal_drift.metrics import classification_metrics, multiclass_brier_score


LABELS = ("High", "Medium", "Low", "None")


class PhaseEightToTenTests(unittest.TestCase):
    def test_executed_pre_post_runs_are_paired_and_scored(self) -> None:
        pre = {
            "conclusion": "non_compliant",
            "cited_version_id": "v1",
            "citations": ["e1"],
            "explanation": "before",
            "uncertainty": None,
        }
        post = {
            "conclusion": "compliant",
            "cited_version_id": "v2",
            "citations": ["e2"],
            "explanation": "after",
            "uncertainty": None,
        }
        result = build_drift_evaluation_from_executed_plan(
            {
                "experiment_id": "demo",
                "runs": [
                    {"scenario_id": "s1", "condition": "pre_amendment_legal_context", "run_id": "r1", "raw_response": pre},
                    {"scenario_id": "s1", "condition": "post_amendment_legal_context", "run_id": "r2", "raw_response": post},
                ],
            },
            {
                "scenarios": [
                    {
                        "scenario_id": "s1",
                        "expected_change": 1,
                        "expected_pre_conclusion": "non_compliant",
                        "expected_post_conclusion": "compliant",
                        "pre_applicable_version_id": "v1",
                        "post_applicable_version_id": "v2",
                        "pre_amendment_legal_context": {"evidence_id": "e1"},
                        "post_amendment_legal_context": {"evidence_id": "e2"},
                    }
                ]
            },
        )
        self.assertEqual(result["metrics"]["false_stability_rate"], 0)
        self.assertEqual(result["metrics"]["version_accuracy"], 1)
        self.assertEqual(result["metrics"]["citation_precision"], 1)

    def test_execution_enabled_plan_requires_a_model(self) -> None:
        scenarios = {"scenarios": [{"scenario_id": "s1", "facts": []}]}
        release = {"benchmark_frozen": False}
        baseline = {"metrics": None}
        config = {
            "conditions": [
                "no_legal_context",
                "pre_amendment_legal_context",
                "post_amendment_legal_context",
                "both_versions",
                "both_versions_plus_reference_date",
                "reconstructed_temporally_applicable_context",
            ],
            "execution_enabled": True,
            "model": None,
            "model_version": None,
            "experiment_id": "test",
        }
        with self.assertRaises(ValueError):
            build_llm_evaluation_plan(scenarios, release, baseline, config, {})

    def test_reproducible_non_neural_baselines_and_metrics(self) -> None:
        majority = MajorityBaseline().fit(["High", "High", "Low"])
        priors = ClassPriorBaseline().fit(["High", "High", "Low"])
        operation = OperationPriorBaseline().fit(
            ["insertion", "insertion", "omission"], ["High", "High", "Low"]
        )

        self.assertEqual(majority.predict(2), ["High", "High"])
        self.assertEqual(priors.predict(1), ["High"])
        self.assertEqual(operation.predict(["insertion", "unknown"]), ["High", "High"])
        metrics = classification_metrics(
            ["High", "Medium", "Low", "None"],
            ["Low", "Medium", "Low", "None"],
            LABELS,
        )
        self.assertEqual(metrics["high_materiality_false_negative_rate"], 1.0)
        brier = multiclass_brier_score(["High"], priors.predict_proba(1), LABELS)
        self.assertGreaterEqual(brier["multiclass_brier_score"], 0)

    def test_false_stability_and_false_instability_are_exact(self) -> None:
        compliant = {
            "conclusion": "compliant",
            "cited_version_id": "v1",
            "citations": ["e1"],
            "explanation": "Evidence-linked explanation",
            "uncertainty": None,
        }
        non_compliant = {
            **compliant,
            "conclusion": "non_compliant",
            "cited_version_id": "v2",
        }
        metrics = score_paired_assertions(
            [
                {
                    "expected_change": 1,
                    "pre_assertion": compliant,
                    "post_assertion": compliant,
                    "expected_pre_conclusion": "compliant",
                    "expected_post_conclusion": "non_compliant",
                    "expected_pre_version_id": "v1",
                    "expected_post_version_id": "v2",
                    "expected_pre_citations": ["e1"],
                    "expected_post_citations": ["e2"],
                },
                {
                    "expected_change": 0,
                    "pre_assertion": compliant,
                    "post_assertion": non_compliant,
                },
            ]
        )
        self.assertEqual(metrics["false_stability_rate"], 1.0)
        self.assertEqual(metrics["false_instability_rate"], 1.0)
        self.assertEqual(metrics["compliance_outcome_accuracy"], 0.5)
        self.assertEqual(metrics["version_accuracy"], 0.5)
        self.assertEqual(metrics["citation_precision"], 0.5)
        self.assertEqual(metrics["citation_recall"], 0.5)
        with self.assertRaises(ValueError):
            normalize_structured_assertion({**compliant, "unexpected": True})

    def test_correct_conclusion_with_stale_version_is_explanation_drift(self) -> None:
        explanation = {
            "legal_instrument": "Act",
            "provision_path": "section:1",
            "applicable_date": "2020-01-01",
            "version_id": "stale-version",
            "before_evidence_id": "before",
            "after_evidence_id": "after",
            "amendment_operation": "substitution",
            "materiality_dimensions": ["obligation"],
            "materiality_level": "High",
            "compliance_consequence": "non-compliant",
            "citations": ["after"],
            "confidence": 0.9,
            "uncertainty_or_escalation": "version check required",
        }
        result = evaluate_explanation_support(
            explanation,
            {
                "version_id": "current-version",
                "applicable_date": "2020-01-01",
                "compliance_consequence": "non-compliant",
            },
            {"before", "after"},
            tuple(explanation),
        )
        self.assertTrue(result["explanation_drift"])
        self.assertFalse(result["version_alignment"])
        self.assertIsNone(result["legal_correctness"])
        self.assertTrue(result["expert_evaluation_required"])


if __name__ == "__main__":
    unittest.main()
