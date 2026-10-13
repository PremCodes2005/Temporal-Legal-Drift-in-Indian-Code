"""Act-only questions, section choice, wrong-amendment rejection and the FAQ (version-evidence-v2, answer-composition-v3).

Real corpus, offline (no live India Code, no model). These check software behaviour, not legal accuracy.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from temporal_legal_drift.rag.audit import offline_extractive
from temporal_legal_drift.rag.question import parse_question
from temporal_legal_drift.rag.rag_pipeline import RagPipeline, _evidence_gate
from temporal_legal_drift.rag.versions import VERSION_CLAIMS

ROOT = Path(__file__).resolve().parents[2]
FAQ = json.loads((ROOT / "frontend/src/faq.json").read_text(encoding="utf-8"))
MV = "What changed in the Motor Vehicles Act?"
IBC99 = "Compare section 99 of the Insolvency and Bankruptcy Code before and after the {} amendment."


class ActDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._env = {k: os.environ.get(k) for k in ("TLD_LIVE_INDIA_CODE", "TLD_RULE_DELTA_LLM")}
        os.environ.update({"TLD_LIVE_INDIA_CODE": "0", "TLD_RULE_DELTA_LLM": "0"})
        cls._offline = offline_extractive()
        cls._offline.__enter__()
        cls.pipeline = RagPipeline(ROOT)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._offline.__exit__(None, None, None)
        for name, value in cls._env.items():
            os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value)

    def ask(self, query: str, section: str | None = None) -> dict:
        return self.pipeline.answer(query, "specific", section=section)

    # ---------- Act-only questions ----------
    def test_act_only_question_lists_ranked_sections_and_never_scores_the_whole_act(self) -> None:
        result = self.ask(MV)
        found = result["version_evidence"]["section_candidates"]
        self.assertEqual(result["version_evidence"]["reason_code"], "SECTION_NOT_IDENTIFIED")
        self.assertGreaterEqual(found["counts"]["SUPPORTED"], 5)
        self.assertLessEqual(len(found["candidates"]), 8)
        self.assertEqual(found["candidates"][0]["status"], "SUPPORTED")
        for row in found["candidates"]:
            self.assertTrue(row["section"] and row["why"] and row["source"]["pdf_url"])
        self.assertIn("not the Act's complete amendment history", found["note"])
        self.assertIsNone(result["metrics"])
        self.assertTrue(all(result["fingerprint"][name]["value"] is None for name in ("wording_drift", "rule_drift")))
        self.assertIsNone(result["fingerprint"]["tlds"]["value"])
        self.assertIn("Choose a section below", result["answer"]["direct_answer"])

    def test_a_named_amendment_limits_the_sections_to_that_amendment(self) -> None:
        found = self.ask("What changed in the Disaster Management Act after the 2025 amendment?")["version_evidence"]["section_candidates"]
        supported = [row for row in found["candidates"] if row["status"] == "SUPPORTED"]
        self.assertTrue(supported)
        self.assertEqual({row["amendment_year"] for row in supported}, {"2025"})
        self.assertNotIn("OTHER_AMENDMENT", {row["status"] for row in found["candidates"]})  # counted, not offered

    def test_topic_words_rank_matching_sections_first_with_their_honest_status(self) -> None:
        found = self.ask("What changed in the IT Act amendment regarding data privacy?")["version_evidence"]["section_candidates"]
        first = found["candidates"][0]
        self.assertEqual((first["section"], first["status"]), ("66E", "NO_RECORDED_CHANGE"))
        self.assertIn("heading names your topic", first["why"])

    def test_every_suggested_section_passes_the_same_gates_as_a_typed_one(self) -> None:
        catalog, selector = self.pipeline._components()
        frame = parse_question(MV, catalog)
        rows = selector.discover(frame, _evidence_gate, limit=100)["candidates"]
        statuses = {row["status"] for row in rows}
        self.assertIn("TEXT_UNRELIABLE", statuses)
        for row in rows:
            typed = self.ask(f"What changed in section {row['section']} of the Motor Vehicles Act?")
            supported = typed["comparison"]["support_class"] in VERSION_CLAIMS and typed["fingerprint"]["wording_drift"]["value"] is not None
            self.assertEqual(supported, row["status"] == "SUPPORTED", row["section"])

    # ---------- choosing a section ----------
    def test_choosing_a_section_keeps_the_question_and_records_the_choice(self) -> None:
        chosen = self.ask(MV, section="194")
        self.assertEqual(chosen["query"], MV)
        self.assertEqual(chosen["selection"], {"act_entry_id": "motor-vehicles-act-1988", "act_name": "Motor Vehicles Act 1988", "section": "194",
                                               "chosen_from": "section_candidates"})
        self.assertIn(chosen["comparison"]["support_class"], VERSION_CLAIMS)
        self.assertIsNotNone(chosen["fingerprint"]["rule_drift"]["value"])
        self.assertNotEqual(chosen["analysis_id"], self.ask(MV)["analysis_id"])
        self.assertIsNone(self.ask(MV)["selection"])

    def test_invalid_section_choices_are_rejected(self) -> None:
        for query, section, message in ((MV, "99; drop", "section number"), (MV, "", "section number"),
                                        ("What changed in the law?", "99", "names an Act"),
                                        ("Compare section 99 of the Insolvency and Bankruptcy Code.", "100", "different section")):
            with self.subTest(section=section), self.assertRaisesRegex(ValueError, message):
                self.ask(query, section=section)

    # ---------- version correctness ----------
    def test_a_footnote_from_a_different_amendment_is_never_scored(self) -> None:
        for year in ("2025", "2019"):
            with self.subTest(year=year):
                result = self.ask(IBC99.format(year))
                self.assertEqual(result["version_evidence"]["reason_code"], "FOOTNOTE_FROM_OTHER_AMENDMENT")
                self.assertIn("Act 6 of 2026", result["answer"]["direct_answer"])
                self.assertIsNone(result["metrics"])
                self.assertIsNone(result["fingerprint"]["rule_drift"]["value"])
        matched = self.ask(IBC99.format("2026"))
        self.assertEqual(matched["comparison"]["support_class"], "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION")

    def test_an_amending_act_numbered_in_the_next_year_still_matches_its_footnote(self) -> None:
        # The IT (Amendment) Act, 2008 is Act 10 of 2009; its own text carries that number.
        result = self.ask("Compare Section 19 before and after the IT Amendment Act, 2008.")
        self.assertEqual(result["comparison"]["support_class"], "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION")
        self.assertEqual(result["version_evidence"]["relation_verification"], "ACT_NUMBER_TEXT_VERIFIED")

    def test_no_supported_section_for_the_named_amendment_is_explained(self) -> None:
        result = self.ask("What changed in the Insolvency and Bankruptcy Code after the 2025 amendment?")
        found = result["version_evidence"]["section_candidates"]
        self.assertEqual(found["candidates"], [])
        self.assertGreater(found["counts"]["OTHER_AMENDMENT"], 0)
        self.assertRegex(result["answer"]["direct_answer"], r"No recorded change made by a 2025 amendment .* come from other amendments\. Check the official text on India Code\.")

    def test_an_act_outside_the_corpus_gets_an_explanation_and_the_official_source(self) -> None:
        result = self.ask("What changed in the Banking Laws (Amendment) Act, 2025?")
        self.assertEqual(result["version_evidence"]["reason_code"], "ACT_NOT_IDENTIFIED")
        self.assertIn("No Act in this corpus matches the name used", result["answer"]["direct_answer"])
        self.assertIn("indiacode", result["source_guidance"]["url"])

    # ---------- FAQ ----------
    def test_every_faq_question_leads_to_a_section_choice_or_a_supported_comparison(self) -> None:
        self.assertNotIn("recent", json.dumps(FAQ["questions"]).casefold())
        for item in FAQ["questions"]:
            with self.subTest(question=item["question"]):
                result = self.ask(item["question"])
                if item["kind"] == "act":
                    self.assertGreaterEqual(result["version_evidence"]["section_candidates"]["counts"].get("SUPPORTED", 0), 1)
                else:
                    self.assertIn(result["comparison"]["support_class"], VERSION_CLAIMS)
                    self.assertIsNotNone(result["fingerprint"]["wording_drift"]["value"])

    def test_every_starter_question_has_a_supported_comparison_or_section_choice(self) -> None:
        for question in FAQ["starters"]:
            with self.subTest(question=question):
                result = self.ask(question)
                found = result["version_evidence"].get("section_candidates") or {}
                self.assertTrue(result["comparison"]["support_class"] in VERSION_CLAIMS or found.get("counts", {}).get("SUPPORTED"))


if __name__ == "__main__":
    unittest.main()
