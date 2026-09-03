from __future__ import annotations

import unittest
from pathlib import Path

from temporal_legal_drift.rag import RagPipeline
from temporal_legal_drift.rag.indiacode import INDIA_CODE_HOME, is_india_code_url
from temporal_legal_drift.rag.metrics import calculate_drift_metrics


ROOT = Path(__file__).resolve().parents[2]


class RagPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = RagPipeline(ROOT)

    def test_repository_is_automatically_indexed_with_required_metadata(self) -> None:
        status = self.pipeline.status()
        self.assertTrue(status["ready"])
        self.assertEqual(status["document_count"], 14)
        self.assertGreater(status["chunk_count"], 14)
        self.assertEqual(
            status["metadata_fields"],
            ["document_type", "version", "act_name", "date"],
        )

    def test_it_act_query_retrieves_an_amendment_pair_and_metrics(self) -> None:
        result = self.pipeline.answer(
            "What changed in the IT Act amendment regarding data privacy?",
            "specific",
        )
        self.assertEqual(result["intent"], "diff_analysis")
        self.assertEqual(
            result["retrieval"]["pair_status"],
            "paired_amendment_instruction_and_consolidated_version",
        )
        self.assertEqual(len(result["citations"]), 2)
        for name, value in result["metrics"].items():
            if name.endswith("_percent"):
                self.assertGreaterEqual(value, 0, name)
                self.assertLessEqual(value, 100, name)
        self.assertEqual(result["source_guidance"]["url"].split("?")[0], INDIA_CODE_HOME)

    def test_section_substitution_reconstructs_a_narrow_baseline(self) -> None:
        result = self.pipeline.answer(
            "Compare Section 19 before and after the IT Amendment Act, 2008.",
            "specific",
        )
        self.assertIn("Digital Signature Certificate", result["answer"]["pre_amendment_baseline"])
        self.assertIn("electronic signature", result["answer"]["post_amendment_revision"])
        self.assertEqual(result["metrics"]["conceptual_drift_percent"], 65)

    def test_single_document_lookup_does_not_report_fake_pair_drift(self) -> None:
        result = self.pipeline.answer(
            "What does the Consumer Protection Act say about mediation?",
            "generic",
        )
        self.assertEqual(result["retrieval"]["pair_status"], "single_relevant_document_no_version_pair")
        self.assertIsNone(result["metrics"])
        self.assertFalse(result["verification"]["passed"])

    def test_invalid_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "specific or generic"):
            self.pipeline.answer("What changed?", "verbose")

    def test_drift_metrics_keep_drift_and_alignment_separate(self) -> None:
        metrics = calculate_drift_metrics(
            "A company shall file within ten days.",
            "A company shall file within fifteen days.",
            retrieval_scores=(0.8, 0.8),
            metadata_coverage=1.0,
        )
        self.assertGreater(metrics["lexical_drift_percent"], 0)
        self.assertEqual(metrics["alignment_accuracy_percent"], 90.0)

    def test_legacy_and_current_india_code_hosts_are_recognised(self) -> None:
        self.assertTrue(is_india_code_url("https://indiacode.gov.in/"))
        self.assertTrue(is_india_code_url("https://www.indiacode.nic.in/indiacode/"))
        self.assertFalse(is_india_code_url("https://example.com/"))


if __name__ == "__main__":
    unittest.main()
