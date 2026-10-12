"""Frozen technical scoring fixtures: formula reproduction, bounds and abstention (not legal labels)."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from temporal_legal_drift.rag.metrics import DRIFT_DISAGREEMENT_THRESHOLD, DRIFT_WEIGHTS, calculate_drift_metrics
from temporal_legal_drift.rag.retriever import HybridRetriever

FIXTURES = json.loads((Path(__file__).resolve().parents[1] / "fixtures/drift_scoring/fixtures.v2.json").read_text())


def score(case: dict) -> dict:
    return calculate_drift_metrics(
        case["pre"], case["post"],
        pre_vector=HybridRetriever.embed_text(case["pre"]), post_vector=HybridRetriever.embed_text(case["post"]),
        conceptual_override=case.get("conceptual_override"),
        conceptual_method="fixture_override" if "conceptual_override" in case else "legal_cue_proxy",
        retrieval_scores=(0.8, 0.8), metadata_coverage=1.0,
    )


class DriftScoringFixtureTests(unittest.TestCase):
    def test_machine_readable_methodology_matches_the_code(self) -> None:
        from temporal_legal_drift.rag.metrics import DRIFT_LEVEL_THRESHOLDS, METRICS_CONTRACT_VERSION

        config = json.loads((Path(__file__).resolve().parents[2] / "configs/metrics/drift_score.v3.json").read_text())
        self.assertEqual(config["contract_version"], METRICS_CONTRACT_VERSION)
        self.assertEqual({name: spec["weight"] for name, spec in config["components"].items()},
                         {"vector": DRIFT_WEIGHTS["semantic"], "lexical": DRIFT_WEIGHTS["lexical"], "conceptual": DRIFT_WEIGHTS["conceptual"]})
        self.assertEqual(config["disagreement_threshold"], DRIFT_DISAGREEMENT_THRESHOLD)
        self.assertEqual(config["bands"], DRIFT_LEVEL_THRESHOLDS)

    def test_fixture_set_is_labelled_synthetic(self) -> None:
        self.assertEqual(FIXTURES["status"], "SYNTHETIC_ENGINEERING_FIXTURES_NOT_LEGAL_LABELS")

    def test_every_case_is_deterministic_bounded_and_recomputable(self) -> None:
        for case in FIXTURES["cases"]:
            with self.subTest(case=case["id"]):
                first, second = score(case), score(case)
                self.assertEqual(first, second)
                expect = case["expect"]
                components = {name: first[f"{name}_drift_percent"] for name in DRIFT_WEIGHTS}
                if not expect["all_available"]:
                    self.assertIsNone(first["overall_drift_percent"])
                    self.assertIn(expect["unavailable_reason"], first["unavailable_reasons"])
                    continue
                for value in (*components.values(), first["overall_drift_percent"]):
                    self.assertTrue(0.0 <= value <= 100.0)
                # The displayed overall score recomputes from the returned components and weights.
                recomputed = math.sqrt(sum(DRIFT_WEIGHTS[n] * v * v for n, v in components.items()) / sum(DRIFT_WEIGHTS.values()))
                self.assertAlmostEqual(first["overall_drift_percent"], recomputed, delta=0.1)
                spread = max(components.values()) - min(components.values())
                self.assertEqual(first["component_disagreement"], spread >= DRIFT_DISAGREEMENT_THRESHOLD)
                for name in ("lexical", "semantic", "conceptual"):
                    if name in expect:
                        self.assertEqual(components[name], expect[name])
                    if f"{name}_below" in expect:
                        self.assertLess(components[name], expect[f"{name}_below"])
                    if f"{name}_at_least" in expect:
                        self.assertGreaterEqual(components[name], expect[f"{name}_at_least"])
                if "disagreement" in expect:
                    self.assertEqual(first["component_disagreement"], expect["disagreement"])
                self.assertEqual(len(first["compared_text_sha256"]["pre"]), 64)

    def test_unchanged_text_yields_no_changed_spans_and_edits_are_listed(self) -> None:
        cases = {case["id"]: case for case in FIXTURES["cases"]}
        self.assertEqual(score(cases["exact_equality"])["changed_spans"], [])
        self.assertIn({"operation": "replace", "before": "10", "after": "15"}, score(cases["deadline_change"])["changed_spans"])


if __name__ == "__main__":
    unittest.main()
