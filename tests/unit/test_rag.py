from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from temporal_legal_drift.rag import RagPipeline
from temporal_legal_drift.rag import rag_pipeline
from temporal_legal_drift.rag.rag_pipeline import _extractive_generate
from temporal_legal_drift.rag.indiacode import INDIA_CODE_HOME, is_india_code_url
from temporal_legal_drift.rag.metrics import _aggregate_drift, _drift_level, calculate_drift_metrics
from temporal_legal_drift.rag.retriever import RetrievedChunk


ROOT = Path(__file__).resolve().parents[2]


class RagPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = RagPipeline(ROOT)

    def test_repository_is_automatically_indexed_with_required_metadata(self) -> None:
        status = self.pipeline.status()
        self.assertTrue(status["ready"])
        self.assertEqual(status["document_count"], 100)
        self.assertGreater(status["chunk_count"], 100)
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

    def test_general_act_question_returns_an_opening_page_summary(self) -> None:
        result = self.pipeline.answer("What happened in the Jan Vishwas Act?", "generic")
        self.assertEqual(result["answer"]["answer_type"], "single_document_summary")
        self.assertIn("decriminalising and rationalising offences", result["answer"]["short_answer"])
        self.assertTrue(any("ten per cent" in item.lower() for item in result["answer"]["key_differences"]))
        self.assertEqual(result["citations"][0]["source_anchor"], "pdf:page:1")
        self.assertIsNone(result["metrics"])

    def test_invalid_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "specific or generic"):
            self.pipeline.answer("What changed?", "verbose")

    def test_specific_and_generic_modes_have_distinct_response_contracts(self) -> None:
        pre = RetrievedChunk(
            "amendment", "In section 19, digital signature shall be substituted.",
            0.9, 0.9, 0.9,
            {"document_type": "amending_act", "source_anchor": "pdf:page:2"},
        )
        post = RetrievedChunk(
            "consolidated",
            "Section 19. The Certifying Authority shall validate the 1[electronic signature] Certificate. "
            "1. Subs. for digital signature (w.e.f. 27-10-2009).",
            0.9, 0.9, 0.9,
            {"document_type": "principal_act", "version": "consolidated", "source_anchor": "pdf:page:13"},
        )
        query = "Compare Section 19 before and after the amendment."
        specific = _extractive_generate(query, "specific", pre, post)
        generic = _extractive_generate(query, "generic", pre, post)

        self.assertNotEqual(specific.pre_baseline, generic.pre_baseline)
        self.assertIn("Reconstructed baseline", specific.pre_baseline)
        self.assertIn("At a high level", generic.differences[1])
        self.assertEqual(generic.method, "extractive_fallback_generic")

    def test_drift_metrics_keep_drift_and_alignment_separate(self) -> None:
        metrics = calculate_drift_metrics(
            "A company shall file within ten days.",
            "A company shall file within fifteen days.",
            retrieval_scores=(0.8, 0.8),
            metadata_coverage=1.0,
        )
        self.assertGreater(metrics["lexical_drift_percent"], 0)
        self.assertEqual(metrics["alignment_accuracy_percent"], 90.0)
        self.assertIn(metrics["levels"]["lexical"], {"Low", "Medium", "High"})
        self.assertEqual(
            metrics["level_thresholds"],
            {"Low": "0.0-33.3", "Medium": "33.4-66.6", "High": "66.7-100.0"},
        )

    def test_drift_level_boundaries_are_explicit(self) -> None:
        self.assertEqual(_drift_level(33.3), "Low")
        self.assertEqual(_drift_level(33.4), "Medium")
        self.assertEqual(_drift_level(66.6), "Medium")
        self.assertEqual(_drift_level(66.7), "High")

    def test_opposing_component_scores_do_not_average_to_fifty(self) -> None:
        score = _aggregate_drift(
            {"semantic": 0.0, "conceptual": 100.0},
            {"semantic": 0.5, "conceptual": 0.5},
        )
        self.assertAlmostEqual(score, 70.710678, places=5)
        self.assertNotEqual(round(score, 1), 50.0)

    def test_metric_output_flags_large_component_disagreement(self) -> None:
        metrics = calculate_drift_metrics(
            "The company may file.",
            "The company may file.",
            conceptual_override=100.0,
        )
        self.assertEqual(metrics["aggregation_method"], "weighted_root_mean_square")
        self.assertTrue(metrics["component_disagreement"])
        self.assertEqual(metrics["component_spread_percent"], 100.0)

    def test_legacy_and_current_india_code_hosts_are_recognised(self) -> None:
        self.assertTrue(is_india_code_url("https://indiacode.gov.in/"))
        self.assertTrue(is_india_code_url("https://www.indiacode.nic.in/indiacode/"))
        self.assertFalse(is_india_code_url("https://example.com/"))

    def test_ollama_uses_native_non_thinking_json_request(self) -> None:
        captured: dict[str, object] = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps({"message": {"content": '{"ok": true}'}}).encode()

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode())
            captured["timeout"] = timeout
            return Response()

        environment = {
            "TLD_RAG_PROVIDER": "ollama",
            "TLD_RAG_API_URL": "http://127.0.0.1:11434/v1/chat/completions",
            "TLD_RAG_TIMEOUT_SECONDS": "240",
            "TLD_OLLAMA_CONTEXT_TOKENS": "8192",
        }
        with patch.dict(os.environ, environment, clear=False), patch.object(
            rag_pipeline, "urlopen", fake_urlopen
        ):
            content = rag_pipeline._chat_completion(
                [{"role": "user", "content": "Return JSON."}]
            )

        self.assertEqual(content, '{"ok": true}')
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/chat")
        self.assertEqual(captured["timeout"], 240)
        body = captured["body"]
        self.assertIs(body["think"], False)
        self.assertIs(body["stream"], False)
        self.assertEqual(body["format"], "json")
        self.assertEqual(body["options"]["temperature"], 0.0)
        self.assertEqual(body["options"]["num_ctx"], 8192)


if __name__ == "__main__":
    unittest.main()
