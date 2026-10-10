from __future__ import annotations

import unittest
import json
from pathlib import Path

from temporal_legal_drift.jsonio import load_json
from temporal_legal_drift.amendment_extraction.pipeline import AmendmentExtractionPipeline
from temporal_legal_drift.materiality import (
    ExperimentalMaterialityModel,
    AssessmentValidationError,
    assess_materiality_with_llm,
    build_disagreement_audit_v2,
    build_materiality_round,
    build_materiality_silver,
    build_materiality_ensemble,
    compute_annotation_agreement,
    freeze_materiality_gold,
    validate_llm_assessment,
)
from temporal_legal_drift.materiality.silver import (
    _cue_transition_annotator,
    _operation_delta_annotator,
)


ROOT = Path(__file__).resolve().parents[2]


class MaterialityWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = load_json(ROOT / "configs/annotation/materiality_taxonomy.v1.json")
        cls.graph = load_json(ROOT / "data/interim/temporal_legal_knowledge_graph.v2.json")
        cls.round = build_materiality_round(cls.graph, cls.taxonomy)
        cls.rubric = load_json(ROOT / "configs/annotation/proposed_materiality_rubric.v1.json")
        cls.silver = load_json(ROOT / "data/silver/materiality_silver_labels.v1.json")

    def test_materiality_round_contains_50_corroborated_unlabelled_cases(self) -> None:
        self.assertEqual(len(self.round["tasks"]), 50)
        self.assertEqual(len({task["pair_id"] for task in self.round["tasks"]}), 50)
        self.assertEqual(self.round["status"], "annotation_round_open_not_gold")
        self.assertTrue(all(task["gold_status"] == "NOT_GOLD" for task in self.round["tasks"]))
        self.assertTrue(all(task["materiality"]["label"] is None for task in self.round["tasks"]))
        self.assertTrue(all(len(task["source_evidence"]) >= 2 for task in self.round["tasks"]))

    def test_agreement_reports_undefined_without_human_annotations(self) -> None:
        agreement = compute_annotation_agreement(self.round, {"annotations": []})
        self.assertEqual(agreement["complete_double_annotated_pair_count"], 0)
        self.assertIsNone(agreement["raw_agreement"])
        self.assertIsNone(agreement["cohens_kappa"])
        self.assertEqual(agreement["gold_labels_created"], 0)

    def test_automated_silver_is_explicitly_non_gold_with_method_agreement_metrics(self) -> None:
        silver = build_materiality_silver(self.round)
        self.assertEqual(silver["case_count"], 50)
        self.assertEqual(silver["provisional_label_count"] + silver["unresolved_disagreement_count"], 50)
        self.assertFalse(silver["is_gold"])
        self.assertFalse(silver["legal_correctness_claimed"])
        self.assertTrue(silver["agreement"]["not_human_inter_annotator_agreement"])
        self.assertEqual(silver["agreement"]["item_count"], 50)
        self.assertIsNotNone(silver["agreement"]["cohens_kappa_between_automated_methods"])
        self.assertEqual(
            silver["agreement"]["classification_metrics_method_a_against_method_b"]["interpretation"],
            "Inter-method agreement only; method A is not human-verified ground truth.",
        )
        self.assertTrue(all(row["gold_status"] == "NOT_GOLD" for row in silver["rows"]))
        self.assertTrue(all(row["annotator_a"]["confidence"] is None for row in silver["rows"]))

    def test_silver_labeler_refuses_missing_evidence(self) -> None:
        invalid = {**self.round, "tasks": [dict(task) for task in self.round["tasks"]]}
        invalid["tasks"][0] = {**invalid["tasks"][0], "source_evidence": []}
        with self.assertRaisesRegex(ValueError, "two source anchors"):
            build_materiality_silver(invalid)

    def test_deadline_numeric_change_maps_to_time_not_threshold(self) -> None:
        task = {
            "before_text": "Submit the form within 10 days.",
            "after_text": "Submit the form within 15 days.",
            "amendment_instruction_text": "the words 10 days are substituted by 15 days",
            "operation": "SUBSTITUTE",
        }
        for annotator in (_cue_transition_annotator, _operation_delta_annotator):
            result = annotator(task)
            self.assertEqual(result["label"], "Medium")
            self.assertIn("time", result["dimensions"])

    def test_rule_outputs_are_deterministic_and_frozen_data_remains_unchanged(self) -> None:
        self.assertEqual(build_materiality_silver(self.round), self.silver)
        self.assertTrue(all(row["annotator_a"] and row["annotator_b"] for row in self.silver["rows"]))
        self.assertTrue(all(row["automated_adjudication"] for row in self.silver["rows"]))

    def test_none_category_search_does_not_turn_text_identity_into_none_gold(self) -> None:
        from temporal_legal_drift.materiality import search_potential_none_cases

        result = search_potential_none_cases(self.graph)
        self.assertEqual(result["status"], "none_category_unevaluated")
        self.assertGreaterEqual(result["transition_count_scanned"], 50)
        self.assertEqual(result["none_gold_labels_created"], 0)
        self.assertTrue(all(item["label"] is None for item in result["results"]))

    def _mock_assessor(self, *, insufficient: bool = False, bad_citation: bool = False):
        def request(messages: list[dict[str, str]]) -> str:
            payload = json.loads(messages[1]["content"])
            source = payload["sources"][0]
            quote = "not in the cited source" if bad_citation else source["text"][:60]
            response = {
                "schema_version": "1.0.0",
                "pair_id": payload["pair_id"],
                "rubric_version": payload["rubric_version"],
                "label": None if insufficient else "Medium",
                "evidence": [] if insufficient else [{"source_id": source["source_id"], "quote": quote}],
                "rationale": "Mocked schema/provenance contract check; not a legal determination.",
                "uncertainty": "Synthetic test response only.",
                "insufficient_evidence": insufficient,
            }
            return json.dumps(response)
        return request

    def test_llm_assessment_schema_provenance_and_review_status(self) -> None:
        result = assess_materiality_with_llm(
            self.silver, self.round, self.graph, self.rubric,
            request_model=self._mock_assessor(),
        )
        self.assertEqual(result["case_count"], 50)
        self.assertEqual(result["schema_valid_count"], 50)
        self.assertEqual(result["review_required_count"], 50)
        self.assertFalse(result["legal_correctness_claimed"])
        self.assertTrue(all(row["workflow_status"] == "REVIEW_REQUIRED" for row in result["rows"]))
        self.assertTrue(all(row["citation_integrity"] == "ALL_QUOTES_FOUND_IN_SUPPLIED_SOURCE_TEXT" for row in result["rows"]))
        self.assertEqual(result["silver_label_agreement_only"]["llm"]["eligible_pair_count"], 50)
        self.assertTrue(result["silver_label_agreement_only"]["llm"]["reference_is_rule_derived_silver_not_gold"])

    def test_structured_assessment_validator_rejects_unknown_source_and_bad_shape(self) -> None:
        task = self.round["tasks"][0]
        source = task["source_evidence"][0]
        valid = {
            "schema_version": "1.0.0",
            "pair_id": task["pair_id"],
            "rubric_version": self.rubric["version"],
            "label": "Low",
            "evidence": [{"source_id": source["source_id"], "quote": source["evidence_text"][:30]}],
            "rationale": "A schema-only test response.",
            "uncertainty": "Not a legal determination.",
            "insufficient_evidence": False,
        }
        validate_llm_assessment(valid, task["pair_id"], self.rubric, task["source_evidence"])
        invalid = {**valid, "evidence": [{"source_id": "not-a-source", "quote": "invented quote"}]}
        with self.assertRaisesRegex(AssessmentValidationError, "not found"):
            validate_llm_assessment(invalid, task["pair_id"], self.rubric, task["source_evidence"])
        with self.assertRaisesRegex(AssessmentValidationError, "exactly match"):
            validate_llm_assessment({**valid, "extra_field": True}, task["pair_id"], self.rubric, task["source_evidence"])

    def test_llm_insufficient_evidence_is_workflow_status_not_materiality_class(self) -> None:
        result = assess_materiality_with_llm(
            self.silver, self.round, self.graph, self.rubric,
            request_model=self._mock_assessor(insufficient=True),
        )
        self.assertEqual(result["insufficient_evidence_count"], 50)
        self.assertTrue(all(row["workflow_status"] == "INSUFFICIENT_EVIDENCE" for row in result["rows"]))
        self.assertTrue(all(row["materiality_label"] is None for row in result["rows"]))

    def test_llm_schema_repair_is_bounded_and_revalidated(self) -> None:
        calls = 0

        def request(messages: list[dict[str, str]]) -> str:
            nonlocal calls
            calls += 1
            payload = json.loads(messages[1]["content"])
            if calls % 2:
                return json.dumps({"echoed_input": True})
            source = payload["sources"][0]
            return json.dumps({
                "schema_version": "1.0.0",
                "pair_id": payload["pair_id"],
                "rubric_version": payload["rubric_version"],
                "label": "Medium",
                "evidence": [{"source_id": source["source_id"], "quote": source["text"][:60]}],
                "rationale": "Synthetic test response only.",
                "uncertainty": "Test fixture.",
                "insufficient_evidence": False,
            })

        result = assess_materiality_with_llm(
            self.silver, self.round, self.graph, self.rubric, request_model=request
        )
        self.assertEqual(calls, 100)
        self.assertEqual(result["schema_valid_count"], 50)
        self.assertTrue(all(len(row["raw_response_attempts"]) == 2 for row in result["rows"]))

    def test_invalid_llm_citation_is_retained_as_review_required_failure(self) -> None:
        result = assess_materiality_with_llm(
            self.silver, self.round, self.graph, self.rubric,
            request_model=self._mock_assessor(bad_citation=True),
        )
        self.assertEqual(result["failed_count"], 50)
        self.assertTrue(all(row["workflow_status"] == "REVIEW_REQUIRED" for row in result["rows"]))
        self.assertTrue(all(row["citation_integrity"] == "NOT_ESTABLISHED" for row in result["rows"]))
        self.assertTrue(all(row["materiality_label"] is None for row in result["rows"]))

    def test_optional_ensemble_is_reproducible_and_preserves_every_vote(self) -> None:
        assessments = assess_materiality_with_llm(
            self.silver, self.round, self.graph, self.rubric,
            request_model=self._mock_assessor(),
        )
        first = build_materiality_ensemble(self.silver, assessments)
        second = build_materiality_ensemble(self.silver, assessments)
        self.assertEqual(first, second)
        self.assertEqual(first["case_count"], 50)
        self.assertTrue(all(row["gold_status"] == "NOT_GOLD" for row in first["rows"]))
        for original, combined in zip(self.silver["rows"], first["rows"]):
            self.assertEqual(combined["rule_a_prediction"], original["annotator_a"]["label"])
            self.assertEqual(combined["rule_b_prediction"], original["annotator_b"]["label"])
            self.assertEqual(combined["rule_tiebreak_prediction"], original["automated_adjudication"]["label"])

    def test_disagreement_report_contains_every_existing_disagreement_without_resolution(self) -> None:
        from temporal_legal_drift.materiality import build_disagreement_report

        report = build_disagreement_report(self.silver, self.round)
        self.assertEqual(report.count("## "), len(self.silver["agreement"]["disagreement_pair_ids"]))
        self.assertIn("does not resolve any case", report)
        self.assertIn("REVIEW_REQUIRED", report)
        for pair_id in self.silver["agreement"]["disagreement_pair_ids"]:
            self.assertIn(pair_id, report)

    def test_reextraction_audit_preserves_v1_and_abstains_on_size_only(self) -> None:
        events = AmendmentExtractionPipeline(ROOT).run()["events"]
        audit = build_disagreement_audit_v2(self.silver, self.round, self.graph, events)
        by_id = {row["pair_id"]: row for row in audit["rows"]}
        self.assertEqual(audit["case_count"], 19)
        self.assertEqual(audit["confirmed_alignment_defect_count"], 5)
        self.assertEqual(audit["review_required_count"], 4)
        self.assertEqual(audit["reextracted_aligned_count"], 10)
        self.assertEqual(audit["v2_rule_b_labelled_count"], 2)
        self.assertEqual(audit["v2_rule_b_review_held_label_count"], 2)
        self.assertEqual(audit["v2_rule_b_abstention_count"], 17)
        self.assertEqual(audit["cross_source_revalidation_required_count"], 2)
        self.assertEqual(audit["v2_comparable_count"], 0)
        self.assertEqual(audit["v2_rule_agreement_count"], 0)
        self.assertEqual(audit["v2_low_medium_disagreement_count"], 0)
        self.assertEqual(
            by_id["mat_08031e98498c98fa32a2e951"]["extraction_v2"]["new_text"],
            "or completion of such transactions as may be prescribed,",
        )
        self.assertEqual(
            by_id["mat_390c72d9d6d3e4ca87e8b0d2"]["extraction_v2"]["target_provision"],
            "section:31A",
        )
        self.assertEqual(
            by_id["mat_da9a0c78b92e51330bd0b0f1"]["extraction_v2"]["target_provision"],
            "section:6A",
        )
        self.assertTrue(all(row["gold_status"] == "NOT_GOLD" for row in audit["rows"]))
        self.assertFalse(audit["rows"][0]["v2"]["labels_are_legal_truth"])
        self.assertEqual(load_json(ROOT / "data/silver/materiality_silver_labels.v1.json"), self.silver)

    def test_agreement_calculates_raw_and_cohen_kappa(self) -> None:
        small_round = {
            **self.round,
            "tasks": [{"pair_id": "p1"}, {"pair_id": "p2"}, {"pair_id": "p3"}, {"pair_id": "p4"}],
        }
        annotations = []
        for pair_id, label_a, label_b in (
            ("p1", "High", "High"),
            ("p2", "Medium", "Medium"),
            ("p3", "Low", "None"),
            ("p4", "None", "None"),
        ):
            for annotator, label in (("A", label_a), ("B", label_b)):
                annotations.append({
                    "pair_id": pair_id,
                    "annotation_id": f"{pair_id}-{annotator}",
                    "annotator_id": annotator,
                    "submitted_at": "2026-10-10T10:00:00Z",
                    "label": label,
                    "rationale": "Evidence-backed example rationale.",
                    "guideline_version": self.round["guideline_version"],
                    "dimensions": [],
                    "confidence": 0.8,
                    "evidence_spans": [{
                        "source_id": "s",
                        "text": self.round["tasks"][0]["source_evidence"][0]["evidence_text"][:10],
                    }],
                })
        # Use one known valid task so evidence validation is exercised rather than bypassed.
        small_round["tasks"] = [
            {**self.round["tasks"][0], "pair_id": f"p{index}"} for index in range(1, 5)
        ]
        annotations = [
            {**row, "evidence_spans": [{
                "source_id": self.round["tasks"][0]["source_evidence"][0]["source_id"],
                "text": self.round["tasks"][0]["source_evidence"][0]["evidence_text"][:10],
            }]}
            for row in annotations
        ]
        agreement = compute_annotation_agreement(small_round, {"annotations": annotations})
        self.assertEqual(agreement["complete_double_annotated_pair_count"], 4)
        self.assertEqual(agreement["raw_agreement"], 0.75)
        self.assertIsNotNone(agreement["cohens_kappa"])
        self.assertEqual(
            sum(
                count
                for row in agreement["confusion_matrix_annotator_1_rows_annotator_2_columns"].values()
                for count in row.values()
            ),
            4,
        )

    def test_gold_freeze_and_classifier_fail_closed_without_adjudicated_rows(self) -> None:
        with self.assertRaisesRegex(ValueError, "taxonomy and guideline"):
            freeze_materiality_gold(self.round, {"annotations": []}, {"adjudications": []}, self.taxonomy)
        model = ExperimentalMaterialityModel()
        with self.assertRaisesRegex(ValueError, "adjudicated gold"):
            model.fit(self.round["tasks"])

    def test_experimental_model_requires_disjoint_act_holdout(self) -> None:
        train = [
            {"pair_id": "a1", "act_id": "Act A", "operation": "SUBSTITUTE", "before_text": "shall file",
             "after_text": "shall not file", "materiality": {"label": "High"}, "gold_status": "ADJUDICATED_GOLD"},
            {"pair_id": "a2", "act_id": "Act A", "operation": "INSERT", "before_text": "",
             "after_text": "within 15 days", "materiality": {"label": "Medium"}, "gold_status": "ADJUDICATED_GOLD"},
        ]
        test = [
            {"pair_id": "b1", "act_id": "Act B", "operation": "OMIT", "before_text": "penalty",
             "after_text": "", "materiality": {"label": "High"}, "gold_status": "ADJUDICATED_GOLD"},
        ]
        model = ExperimentalMaterialityModel(epochs=5)
        result = model.evaluate(train, test)
        self.assertEqual(result["status"], "held_out_group_evaluation")
        self.assertEqual(result["metrics"]["item_count"], 1)
        with self.assertRaisesRegex(ValueError, "leakage"):
            ExperimentalMaterialityModel(epochs=1).evaluate(train, [dict(test[0], act_id="Act A")])


if __name__ == "__main__":
    unittest.main()
