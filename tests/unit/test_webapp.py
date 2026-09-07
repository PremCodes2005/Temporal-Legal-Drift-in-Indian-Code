from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from temporal_legal_drift.webapp.service import DashboardService


ROOT = Path(__file__).resolve().parents[2]

# The single-prompt RAG endpoint needs the local hybrid retrieval index, which is
# built from the git-ignored normalized RAG corpus. Build it with:
#   tldrift rehydrate-raw-store --manifest configs/corpus/rag_corpus.v1.json
#   tldrift normalize-corpus    --manifest configs/corpus/rag_corpus.v1.json
_RAG_INDEX_AVAILABLE = any((ROOT / "data" / "normalized").glob("*.json"))
_RAG_SKIP_REASON = (
    "RAG retrieval index not built (no data/normalized/*.json); "
    "run rehydrate-raw-store + normalize-corpus for configs/corpus/rag_corpus.v1.json"
)


class DashboardServiceTests(unittest.TestCase):
    def test_dashboard_reads_connected_project_artifacts(self) -> None:
        service = DashboardService(ROOT)
        overview = service.overview()
        corpus = service.corpus()
        demo = service.demo()
        self.assertEqual(overview["metrics"]["corpus_documents"], 14)
        self.assertEqual(overview["metrics"]["controlled_llm_runs"], 78)
        self.assertEqual(corpus["entry_count"], 14)
        self.assertTrue(all(item["pdf_available"] for item in corpus["entries"]))
        self.assertEqual(demo["results"]["metrics"]["false_stability_rate"], 0)

    def test_scenario_submission_is_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = DashboardService(Path(directory))
            result = service.submit_scenario(
                {
                    "title": "Controlled test",
                    "legal_question": "Does the applicable provision change the answer?",
                    "facts": "Fact one\nFact two",
                    "pre_reference_date": "2020-01-01",
                    "post_reference_date": "2021-01-01",
                    "expected_change": "unknown",
                    "evidence_ids": [],
                }
            )
            self.assertEqual(result["status"], "submitted_for_human_review_not_gold")
            files = list((Path(directory) / "data/submissions/scenarios").glob("*.json"))
            self.assertEqual(len(files), 1)

    def test_pdf_upload_is_hashed_and_not_added_to_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = DashboardService(Path(directory))
            payload = b"%PDF-1.4\ncontrolled fixture"
            result = service.upload_evidence(
                {
                    "filename": "fixture.pdf",
                    "content_base64": base64.b64encode(payload).decode("ascii"),
                    "category": "legal_instrument",
                    "authoritative_confirmation": False,
                }
            )
            self.assertEqual(result["status"], "evidence_review_queue_not_corpus")
            self.assertEqual(result["byte_length"], len(payload))

    @unittest.skipUnless(_RAG_INDEX_AVAILABLE, _RAG_SKIP_REASON)
    def test_single_prompt_rag_api_contract(self) -> None:
        service = DashboardService(ROOT)
        result = service.query_rag(
            {
                "query": "Compare Section 19 before and after the IT Amendment Act, 2008.",
                "mode": "specific",
            }
        )
        self.assertEqual(result["mode"], "specific")
        self.assertIn("semantic_drift_percent", result["metrics"])
        self.assertIn("source_guidance", result)


if __name__ == "__main__":
    unittest.main()
