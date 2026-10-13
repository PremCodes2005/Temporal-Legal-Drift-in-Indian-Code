from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from temporal_legal_drift.rag import RagPipeline
from temporal_legal_drift.rag import rag_pipeline
from temporal_legal_drift.rag.rag_pipeline import _extractive_generate
from temporal_legal_drift.rag.indiacode import INDIA_CODE_HOME, is_india_code_url
from temporal_legal_drift.rag.metrics import _aggregate_drift, _drift_level, calculate_drift_metrics
from temporal_legal_drift.rag.retriever import HybridRetriever, RetrievedChunk


ROOT = Path(__file__).resolve().parents[2]


class RagPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._environment = {
            name: os.environ.get(name)
            for name in ("TLD_LIVE_INDIA_CODE", "TLD_RAG_PROVIDER", "TLD_RAG_API_KEY", "OPENAI_API_KEY")
        }
        os.environ.update({
            "TLD_LIVE_INDIA_CODE": "0",
            "TLD_RAG_PROVIDER": "openai_compatible",
            "TLD_RAG_API_KEY": "",
            "OPENAI_API_KEY": "",
        })
        cls.pipeline = RagPipeline(ROOT)

    @classmethod
    def tearDownClass(cls) -> None:
        for name, value in cls._environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_repository_is_automatically_indexed_with_required_metadata(self) -> None:
        status = self.pipeline.status()
        self.assertTrue(status["ready"])
        self.assertEqual(status["document_count"], 100)
        self.assertGreater(status["chunk_count"], 100)
        self.assertEqual(status["dataset_version"], "v0.1")
        self.assertEqual(status["graph_version"], "v0.1")
        self.assertEqual(status["rag_index_version"], "v0.1")
        self.assertEqual(len(status["graph_fingerprint"]), 64)
        self.assertEqual(len(status["index_identity"]), 64)
        self.assertEqual(
            status["metadata_fields"],
            ["document_type", "version", "act_name", "date"],
        )
        incompatible = HybridRetriever(ROOT)
        incompatible._version = {**incompatible._version, "graph_fingerprint": "0" * 64}
        with self.assertRaisesRegex(ValueError, "changed without a new registered artifact version"):
            incompatible.ensure_index()
        with tempfile.TemporaryDirectory() as directory:
            clean_root = Path(directory)
            for relative in (
                "data/corpus/index.json",
                "data/interim/version_graph.v1.json",
                "data/manifests/artifact_versions.json",
                "data/manifests/artifacts/v0.1/rag_index.v0.1.json.gz",
            ):
                destination = clean_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            restored = HybridRetriever(clean_root).status()
            self.assertEqual(restored["index_identity"], status["index_identity"])

    def test_unaligned_instruction_and_consolidated_text_get_no_drift_scores(self) -> None:
        # Regression: an IT 2008 instruction excerpt and an unrelated consolidated passage
        # were labelled pre/post and scored. They are not versions of one provision.
        result = self.pipeline.answer(
            "What changed in the IT Act amendment regarding data privacy?",
            "specific",
        )
        # rag-answer-v2: no section is named, so nothing is paired; the answer asks for one and suggests sections.
        self.assertEqual(result["retrieval"]["pair_status"], "no_supported_version")
        self.assertEqual(result["version_evidence"]["reason_code"], "SECTION_NOT_IDENTIFIED")
        self.assertIsNone(result["metrics"])
        candidates = result["version_evidence"]["section_candidates"]["candidates"]
        privacy = next(row for row in candidates if row["section"] == "66E")
        self.assertEqual((privacy["topic_match"], privacy["status"]), (True, "NO_RECORDED_CHANGE"))  # suggested for the topic, not as comparable
        self.assertEqual(result["determinations"]["textual_drift"]["state"], "INSUFFICIENT_EVIDENCE")
        paired = next(item for item in result["verification"]["checks"] if item["id"] == "paired_context")
        self.assertFalse(paired["passed"])
        self.assertEqual([item["entry_id"] for item in result["source_fidelity_warnings"]], ["it-amendment-act-2008"])
        self.assertEqual(result["source_guidance"]["url"].split("?")[0], INDIA_CODE_HOME)

    def test_comparison_record_states_support_roles_and_abstention_codes(self) -> None:
        unaligned = self.pipeline.answer("What changed in the IT Act amendment regarding data privacy?", "specific")["comparison"]
        self.assertEqual(unaligned["contract_version"], "comparison-record-v2")
        self.assertEqual(unaligned["support_class"], "NO_SUPPORTED_VERSION")
        self.assertIsNone(unaligned["before"])  # unaligned excerpts are never presented as a version
        self.assertTrue({"SECTION_NOT_IDENTIFIED", "SOURCE_TEXT_UNRELIABLE"} <= set(unaligned["abstention_reasons"]))
        reconstructed = self.pipeline.answer("Compare Section 19 before and after the IT Amendment Act, 2008.", "specific")["comparison"]
        self.assertEqual(reconstructed["support_class"], "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION")
        self.assertEqual(reconstructed["before"]["role"], "reconstructed_earlier_wording")
        self.assertTrue(reconstructed["changed_spans"])
        self.assertEqual(reconstructed["scoring_contract_version"], "drift-metrics-v3")
        self.assertIn("unavailable", reconstructed["before"]["page_region_highlight"])
        self.assertEqual(reconstructed["applicability_status"], "NOT_DETERMINED_REQUIRES_SCENARIO_FACTS_AND_REVIEW")
        lookup = self.pipeline.answer("What does the Consumer Protection Act say about mediation?", "generic")["comparison"]
        self.assertEqual((lookup["support_class"], lookup["before"]), ("NOT_A_COMPARISON", None))

    def test_footnote_reconstruction_only_for_the_requested_section(self) -> None:
        pre = RetrievedChunk("amendment", "In section 20, for digital signature, electronic signature shall be substituted.", 0.9, 0.9, 0.9,
                             {"document_type": "amending_act"})
        post = RetrievedChunk("consolidated", "20. Controller to act as repository.—The 1[electronic signature] Certificate. "
                              "1. Subs. by Act 10 of 2009, s. 9, for \"digital signature\" (w.e.f. 27-10-2009).", 0.9, 0.9, 0.9,
                              {"document_type": "consolidated_act"})
        from temporal_legal_drift.rag.rag_pipeline import _reconstructed_comparison
        self.assertEqual(_reconstructed_comparison(pre, post, "Compare section 19 before and after")[0], None)
        self.assertIsNotNone(_reconstructed_comparison(pre, post, "Compare section 20 before and after")[0])

    def test_clause_evidence_is_anchored_attributed_and_date_constrained(self) -> None:
        comparison = self.pipeline.answer(
            "Compare Section 19 before and after the IT Amendment Act, 2008 as of 1 January 2010.", "specific")["comparison"]
        after, before = comparison["after"], comparison["before"]
        self.assertEqual(after["span_basis"], "exact_source_span")
        chunk = next(c for c in self.pipeline.retriever.ensure_index()["chunks"]
                     if c["metadata"].get("entry_id") == after["entry_id"] and c["metadata"].get("source_anchor") == after["source_anchor"])
        self.assertIn(" ".join(after["compared_text"].split()), " ".join(chunk["text"].split()))  # verbatim span of the cited chunk
        self.assertEqual(len(after["text_sha256"]), 64)
        self.assertTrue(after["local_pdf_url"].endswith(f"#page={after['page']}"))
        # The reconstructed wording is derived from the consolidated footnote and cites that source, not the amending Act.
        self.assertEqual(before["span_basis"], "derived_text_not_a_verbatim_source_span")
        self.assertEqual(before["entry_id"], after["entry_id"])
        self.assertEqual((comparison["operation"], comparison["provision_path"]), ("SUBSTITUTE", "section:19"))
        self.assertEqual(comparison["requested_date"], {"value": "2010-01-01", "precision": "day"})

    def test_ambiguous_graph_alignment_keeps_competitors_and_abstains(self) -> None:
        # Real data: IBC section 239 has two corroborated insertions ((fa) and (fd)); neither is chosen.
        result = self.pipeline.answer("What changed in section 239 of the Insolvency and Bankruptcy Code after the amendment?", "specific")
        comparison = result["comparison"]
        self.assertEqual(comparison["support_class"], "AMBIGUOUS_CANDIDATES")
        self.assertEqual(len(comparison["competing_transition_ids"]), 2)
        self.assertIn("SEVERAL_CORROBORATED_CHANGES", comparison["abstention_reasons"])
        self.assertIsNone(result["metrics"])
        self.assertIsNone(comparison["before"])

    def test_score_carries_separate_reliability_and_question_relevance(self) -> None:
        metrics = self.pipeline.answer("Compare Section 19 before and after the IT Amendment Act, 2008.", "specific")["metrics"]
        self.assertEqual(metrics["metrics_contract_version"], "drift-metrics-v3")
        self.assertEqual(metrics["reliability"]["pairing"], "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION")
        self.assertEqual(metrics["reliability"]["temporal_certainty"]["status"], "FOOTNOTE_STATED_DATE_UNVERIFIED")
        self.assertEqual(metrics["question_relevance"]["status"], "MATCHES_REQUESTED_SECTION")
        self.assertFalse(metrics["question_relevance"]["answers_scenario_question"])
        # Reliability is not folded into drift: the overall score recomputes from the three components alone.
        components = [metrics["semantic_drift_percent"], metrics["lexical_drift_percent"], metrics["conceptual_drift_percent"]]
        recomputed = (0.4 * components[0] ** 2 + 0.3 * components[1] ** 2 + 0.3 * components[2] ** 2) ** 0.5
        self.assertAlmostEqual(metrics["overall_drift_percent"], recomputed, delta=0.1)

    def test_unrelated_amendment_is_not_paired_when_its_act_was_not_retrieved(self) -> None:
        result = self.pipeline.answer(
            "What changed in the Arbitration and Conciliation Act section 7 regarding electronic communication?",
            "specific",
        )
        # The amending Act that actually amends section 7 is cited with the principal Act; nothing from the IT Act.
        self.assertEqual({item.get("entry_id") for item in result["citations"]},
                         {"arbitration-and-conciliation-act-1996", "arbitration-and-conciliation-amendment-act-2015"})
        self.assertIsNone(result["metrics"])  # an insertion has no earlier wording to score

    def test_display_mode_does_not_change_prompt_selected_score_basis(self) -> None:
        query = "Compare Section 19 before and after the IT Amendment Act, 2008."
        with patch.object(rag_pipeline, "_llm_configured", return_value=False):
            specific = self.pipeline.answer(query, "specific")
            generic = self.pipeline.answer(query, "generic")
        self.assertEqual(specific["metrics"]["score_basis"], generic["metrics"]["score_basis"])
        self.assertEqual(specific["metrics"]["overall_drift_percent"], generic["metrics"]["overall_drift_percent"])

    def test_section_substitution_reconstructs_a_narrow_baseline(self) -> None:
        result = self.pipeline.answer(
            "Compare Section 19 before and after the IT Amendment Act, 2008.",
            "specific",
        )
        self.assertEqual(result["retrieval"]["pair_status"], "consolidated_footnote_reconstruction")
        self.assertIn("Digital Signature Certificate", result["answer"]["pre_amendment_baseline"])
        self.assertIn("electronic signature", result["answer"]["post_amendment_revision"])
        # v2 removed the hard-coded signature-term score (formerly 65); the proxy now reports
        # only general cue, number and polarity changes, and the changed span is returned.
        self.assertEqual(result["metrics"]["conceptual_drift_percent"], 0.0)
        self.assertTrue(any(span["before"] == "digital" and "electronic" in span["after"]
                            for span in result["metrics"]["changed_spans"]))

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

    def test_model_timeout_or_provider_error_yields_labelled_extractive_fallback(self) -> None:
        # General questions still use the model when configured; a failure falls back to a labelled extract.
        for error in (TimeoutError("timed out"), ValueError("bad provider payload")):
            with self.subTest(error=type(error).__name__), \
                    patch.object(rag_pipeline, "_llm_configured", return_value=True), \
                    patch.object(rag_pipeline, "_llm_single_document_generate", side_effect=error):
                result = self.pipeline.answer("What does the Consumer Protection Act say about mediation?", "specific")
            self.assertEqual(result["answer"]["generation_method"], "extractive_fallback")
            self.assertIn("unavailable", result["answer"]["generation_warning"])
            self.assertIn("Section 37", result["answer"]["direct_answer"])  # the fallback still answers from the cited section

    def test_version_comparisons_never_depend_on_the_model(self) -> None:
        query = "Compare Section 19 before and after the IT Amendment Act, 2008."
        with patch.object(rag_pipeline, "_llm_configured", return_value=True), \
                patch.object(rag_pipeline, "_chat_completion", side_effect=TimeoutError("timed out")) as model:
            result = self.pipeline.answer(query, "specific")
        model.assert_not_called()
        self.assertEqual(result["answer"]["generation_method"], "grounded_composition")
        self.assertEqual(result["metrics"]["conceptual_method"], "legal_cue_proxy")  # no model judgment claimed

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
        self.assertEqual(metrics["evidence_alignment_quality_percent"], 90.0)
        self.assertIn("alignment_accuracy_percent", metrics["deprecated_fields"])
        # Without feature vectors the vector component and the overall score are unavailable, not substituted.
        self.assertIsNone(metrics["semantic_drift_percent"])
        self.assertIsNone(metrics["overall_drift_percent"])
        self.assertIn("semantic", metrics["unavailable_reasons"])
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
        trace = metrics["calculation_trace"]
        self.assertEqual(trace["overall"]["formula"], "sqrt(0.40 × semantic² + 0.30 × lexical² + 0.30 × conceptual²)")
        self.assertIn("jaccard_similarity_percent", trace["lexical"])
        self.assertIn("pre_legal_cues", trace["conceptual"])

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
