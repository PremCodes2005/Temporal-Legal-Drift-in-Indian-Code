"""Question routing (question-route-v1) and the Act-scope citation gate, on the real corpus, offline (no live India Code, no model).

Each case is a failure seen before routing existed (2026-10-26 reproduction, docs/adr/0024). These check software behaviour:
which Act is used and which documents are cited. They are not legal-accuracy checks.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from temporal_legal_drift.rag import rag_pipeline
from temporal_legal_drift.rag.audit import offline_extractive
from temporal_legal_drift.rag.indiacode import LiveSearchResult
from temporal_legal_drift.rag.rag_pipeline import RagPipeline, _latest_summary
from temporal_legal_drift.rag.routing import latest_records, record_kind

ROOT = Path(__file__).resolve().parents[2]


def cited(result: dict) -> set[str]:
    return {str(item.get("entry_id")) for key in ("citations", "evidence") for item in result.get(key) or []}


class RoutingTests(unittest.TestCase):
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

    def ask(self, query: str, **kwargs) -> dict:
        return self.pipeline.answer(query, "specific", **kwargs)

    def route(self, result: dict) -> tuple[str, str]:
        return result["routing"]["route"], result["routing"]["reason_code"]

    # ---------- a named Act is never answered from another Act ----------
    def test_a_named_act_is_answered_only_from_that_act(self) -> None:
        result = self.ask("What does the IT Act say about data protection?")
        self.assertEqual(self.route(result), ("act_identified", "ACT_NAMED_IN_QUESTION"))
        self.assertEqual([a["entry_id"] for a in result["routing"]["interpreted_acts"]], ["it-act-2000-consolidated"])
        self.assertTrue(cited(result) and cited(result) <= set(result["routing"]["allowed_entry_ids"]))
        self.assertTrue(result["routing"]["citation_check"]["passed"])
        # The trace names what an unrestricted search would have used instead.
        self.assertIn("digital-personal-data-protection-act-2023", {r["entry_id"] for r in result["routing"]["rejected_candidates"]})

    def test_a_lowercase_unknown_act_name_is_not_answered_from_another_act(self) -> None:
        # Before: "sir act" was not seen as an Act name and the Repealing and Amending Act 2001 answered it.
        for query in ("what is the sir act?", "What is the SIR Act?"):
            with self.subTest(query=query):
                result = self.ask(query)
                self.assertEqual(self.route(result), ("act_not_found", "ACT_NOT_IN_CORPUS"))
                self.assertEqual(cited(result), set())

    # ---------- an Act that is not in the corpus ----------
    def test_an_absent_act_is_reported_with_what_was_checked_and_where_to_look(self) -> None:
        result = self.ask("What does the Fictional Widgets Regulation Act 2031 say about licences?")
        self.assertEqual(self.route(result), ("act_not_found", "ACT_NOT_IN_CORPUS"))
        text = result["answer"]["direct_answer"]
        self.assertIn("I could not find “Fictional Widgets Regulation Act”", text)
        self.assertIn("does not mean no such Act exists", text)
        self.assertNotRegex(text.casefold(), r"does not exist\b|doesn't exist")
        self.assertEqual({link["label"] for link in result["routing"]["links"]}, {"Search India Code", "Search the e-Gazette"})
        self.assertEqual((cited(result), result["routing"]["choices"]), (set(), []))
        self.assertEqual(result["routing"]["live_discoveries"], [])  # live lookup is off: nothing is claimed

    def test_a_live_record_for_an_absent_act_is_listed_as_found_not_summarised(self) -> None:
        live = LiveSearchResult(({"metadata": {"act_name": "The Fictional Widgets Regulation Act, 2031", "date": "2031",
                                                             "source_url": "https://indiacode.gov.in/items/x"}, "text": "Section 1 text"},))
        with patch.dict(os.environ, {"TLD_LIVE_INDIA_CODE": "1"}), patch.object(self.pipeline.live_repository, "search_sections", return_value=live):
            result = self.ask("What does the Fictional Widgets Regulation Act say about licences?")
        self.assertEqual(result["routing"]["live_discoveries"][0]["ingested"], False)
        self.assertIn("reported as found, not summarised", result["answer"]["direct_answer"])
        self.assertNotIn("Section 1 text", result["answer"]["direct_answer"])
        self.assertEqual(cited(result), set())

    # ---------- short forms, aliases, misspellings, shared names ----------
    def test_short_forms_and_aliases_resolve_to_one_act(self) -> None:
        # Before: "Money Laundering Act" was reported as not in the corpus.
        for query, entry in (("What does the Money Laundering Act say?", "prevention-of-money-laundering-act-2002"),
                             ("What does PMLA say about attachment of property?", "prevention-of-money-laundering-act-2002"),
                             ("What does the Information Technology Act cover?", "it-act-2000-consolidated"),
                             ("What does the mv act say about helmets?", "motor-vehicles-act-1988")):
            with self.subTest(query=query):
                result = self.ask(query)
                self.assertEqual([a["entry_id"] for a in result["routing"]["interpreted_acts"]], [entry])
                self.assertLessEqual(cited(result), set(result["routing"]["allowed_entry_ids"]))

    def test_a_misspelt_name_is_offered_as_a_choice_not_answered(self) -> None:
        result = self.ask("What does the Compnies Act say about directors?")
        self.assertEqual(self.route(result), ("act_not_found", "ACT_NOT_IN_CORPUS"))
        self.assertEqual([c["entry_id"] for c in result["routing"]["choices"]], ["companies-act-2013"])
        self.assertEqual(cited(result), set())

    def test_a_name_shared_by_two_acts_asks_the_user_to_choose(self) -> None:
        result = self.ask("What does the Representation of the People Act say about disqualification?")
        self.assertEqual(self.route(result), ("act_ambiguous", "SEVERAL_ACTS_SHARE_THE_NAME"))
        self.assertEqual({c["entry_id"] for c in result["routing"]["choices"]},
                         {"representation-of-the-people-act-1950", "representation-of-the-people-act-1951"})
        self.assertEqual(cited(result), set())
        dated = self.ask("What does the Representation of the People Act 1951 say about disqualification?")
        self.assertEqual([a["entry_id"] for a in dated["routing"]["interpreted_acts"]], ["representation-of-the-people-act-1951"])

    def test_the_users_choice_of_act_is_used_and_recorded(self) -> None:
        query = "What does the Representation of the People Act say about disqualification?"
        result = self.ask(query, act="representation-of-the-people-act-1951")
        self.assertEqual(self.route(result), ("act_identified", "USER_SELECTED_ACT"))
        self.assertEqual(result["selection"]["act_entry_id"], "representation-of-the-people-act-1951")
        self.assertTrue(cited(result) and cited(result) <= {"representation-of-the-people-act-1951"} | set(result["routing"]["allowed_entry_ids"]))
        self.assertNotEqual(result["analysis_id"], self.ask(query)["analysis_id"])
        with self.assertRaisesRegex(ValueError, "entry id of an Act"):
            self.ask(query, act="no-such-act-1999")

    # ---------- several Acts ----------
    def test_a_requested_comparison_uses_both_acts_and_scores_nothing(self) -> None:
        # Before: recorded as an ambiguity and answered from the IT Act alone.
        result = self.ask("Compare the Aadhaar Act and the IT Act on data protection.")
        self.assertEqual(self.route(result), ("act_comparison", "COMPARISON_REQUESTED"))
        self.assertEqual(cited(result), {"aadhaar-act-2016", "it-act-2000-consolidated"})
        self.assertIsNone(result["metrics"])
        self.assertIn("no drift score", result["answer"]["direct_answer"])

    def test_two_acts_without_a_comparison_ask_for_a_choice(self) -> None:
        result = self.ask("What does the Aadhaar Act say about the IT Act?")
        self.assertEqual(self.route(result), ("several_acts", "SEVERAL_ACTS_NAMED"))
        self.assertEqual(cited(result), set())

    def test_an_amending_act_paired_with_the_wrong_act_is_not_answered(self) -> None:
        # Before: the first gave the Motor Vehicles Act cover page; the second missed the amending Act altogether.
        for query in ("What did the Jan Vishwas Act change in the Motor Vehicles Act?",
                      "What changed in the Aadhaar Act by the Information Technology (Amendment) Act 2008?"):
            with self.subTest(query=query):
                result = self.ask(query)
                self.assertEqual(self.route(result), ("amendment_mismatch", "AMENDMENT_NOT_RECORDED_FOR_ACT"))
                self.assertIn("not recorded as amending", result["answer"]["direct_answer"])
                self.assertEqual(cited(result), set())
                self.assertIsNone(result["metrics"])

    # ---------- general questions ----------
    def test_a_general_question_about_a_known_act_gets_a_cited_overview_without_a_score(self) -> None:
        # Before: answered from section 115 (restricting the use of vehicles).
        result = self.ask("What does the Motor Vehicles Act generally cover?")
        self.assertEqual(self.route(result), ("act_identified", "ACT_NAMED_IN_QUESTION"))
        self.assertTrue(result["routing"]["overview"])
        self.assertIn("“An Act to consolidate and amend the law relating to motor vehicles.”", result["answer"]["direct_answer"])
        self.assertIn("Licensing of drivers of motor vehicles", result["answer"]["sections"][0]["text"])
        self.assertEqual(cited(result), {"motor-vehicles-act-1988"})
        self.assertIsNone(result["metrics"])
        self.assertIsNone(result["fingerprint"]["wording_drift"]["value"])

    def test_an_act_only_change_question_offers_sections_not_a_whole_act_score(self) -> None:
        result = self.ask("What changed in the Motor Vehicles Act?")
        self.assertEqual(result["answer"]["answer_type"], "version_abstention")
        self.assertGreater(len(result["version_evidence"]["section_candidates"]["candidates"]), 0)
        self.assertIsNone(result["metrics"])

    def test_a_legal_question_without_an_act_offers_acts_and_answers_from_none(self) -> None:
        # Before: answered from the IT Act.
        result = self.ask("What is the punishment for theft?")
        self.assertEqual(self.route(result), ("general_no_act", "NO_ACT_NAMED"))
        self.assertEqual(cited(result), set())
        self.assertTrue(1 <= len(result["routing"]["choices"]) <= 3)

    def test_a_question_outside_the_legal_domain_gets_scope_guidance(self) -> None:
        # Before: answered from the Companies Act.
        result = self.ask("What is the capital of France?")
        self.assertEqual(self.route(result), ("outside_domain", "OUTSIDE_LEGAL_SCOPE"))
        self.assertEqual((cited(result), result["routing"]["choices"]), (set(), []))

    # ---------- latest records ----------
    def test_latest_questions_read_the_monitoring_ledger_for_the_named_source_only(self) -> None:
        # Before: "India Code" was treated as an Act name, and the e-Gazette question was answered from the Civil Procedure Code.
        def no_network(*args, **kwargs):
            raise AssertionError("a question must never trigger a source check")
        cases = (("What are the latest changes in India Code?", ["india_code"]), ("What has appeared recently in the e-Gazette?", ["egazette"]),
                 ("What changed recently in Indian law?", ["india_code", "egazette"]))
        with patch.object(rag_pipeline.IndiaCodeLiveRepository, "search_sections", no_network), \
                patch("temporal_legal_drift.monitoring.service.MonitoringService.run_due", no_network):
            for query, sources in cases:
                with self.subTest(query=query):
                    result = self.ask(query)
                    self.assertEqual(self.route(result), ("latest_records", "LATEST_FROM_MONITORING"))
                    feed = result["latest_records"]
                    self.assertEqual(feed["sources_asked"], sources)
                    self.assertFalse(feed["fetched_for_this_question"])
                    self.assertLessEqual({item["source_key"] for item in feed["items"]}, set(sources))
                    self.assertLessEqual({s["source_key"] for s in feed["sources"]}, set(sources))
                    self.assertEqual(cited(result), set())


class LatestRecordTests(unittest.TestCase):
    FEED = {"generated_at": "2026-10-26T12:00:00Z", "scope": "monitored", "note": "not law",
            "items": [{"title": "Appointment of the date 15th October 2026 for MSMED Amendment Act 2026", "source_key": "egazette", "source": "e-Gazette of India",
                       "category": "NEW_DOCUMENT", "status": "AWAITING_REVIEW", "official_url": "https://egazette.gov.in/a.pdf", "published": None,
                       "discovered_at": "2026-10-12T16:43:10Z"},
                      {"title": "The Example (Amendment) Ordinance, 2026", "source_key": "india_code", "source": "India Code", "category": "POSSIBLE_AMENDMENT",
                       "status": "CANDIDATE_UNVERIFIED", "official_url": None, "published": "2026-10-01", "discovered_at": "2026-10-12T14:21:00Z"},
                      {"title": "Notification on fees", "source_key": "egazette", "source": "e-Gazette of India", "category": "NEW_DOCUMENT",
                       "status": "AWAITING_REVIEW", "official_url": None, "published": None, "discovered_at": "2026-10-13T00:00:00Z"},
                      {"title": "Verified amendment", "source_key": "india_code", "source": "India Code", "category": "VERIFIED_AMENDMENT",
                       "status": "REVIEW_ACKNOWLEDGED", "official_url": None, "published": None, "discovered_at": "2026-10-13T00:00:00Z"}],
            "sources": [{"source_key": "egazette", "source": "e-Gazette of India", "state": "STALE", "detail": "No successful check for 307 hours.",
                         "last_success_at": "2026-10-13T17:17:13Z"},
                        {"source_key": "india_code", "source": "India Code", "state": "FAILED", "detail": "The last check failed.",
                         "last_success_at": "2026-10-12T14:21:16Z"}]}

    def test_records_are_classified_without_claiming_more_than_the_ledger_shows(self) -> None:
        self.assertEqual([record_kind(item) for item in self.FEED["items"]],
                         ["commencement_notification", "unverified_candidate", "other_notice", "act_amendment"])

    def test_the_named_source_limits_records_and_health(self) -> None:
        feed = latest_records(self.FEED, ["egazette"])
        self.assertEqual({item["source_key"] for item in feed["items"]}, {"egazette"})
        self.assertEqual([s["state"] for s in feed["sources"]], ["STALE"])
        self.assertTrue(all(item["record_kind_label"] for item in feed["items"]))

    def test_stale_or_failed_sources_and_no_records_are_said_plainly(self) -> None:
        direct, sections = _latest_summary(latest_records(self.FEED, ["india_code"]))
        self.assertIn("last successful check 2026-10-12 14:21 UTC (failed)", direct)
        self.assertIn("nothing was fetched for this question", direct)
        self.assertIn("The last check failed.", sections[0]["text"])
        empty = latest_records({**self.FEED, "items": []}, ["egazette"])
        direct, _ = _latest_summary(empty)
        self.assertTrue(direct.startswith("No records have been observed in e-Gazette of India within the monitored scope"))
        self.assertIn("(stale)", direct)

    def test_a_missing_ledger_gives_an_empty_feed_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            pipeline = RagPipeline.__new__(RagPipeline)
            pipeline.root = Path(folder)
            feed = pipeline._latest_records(["india_code", "egazette"])
        self.assertEqual(feed["items"], [])
        self.assertFalse(feed["fetched_for_this_question"])


class CitationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._offline = offline_extractive()
        cls._offline.__enter__()
        cls.pipeline = RagPipeline(ROOT)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._offline.__exit__(None, None, None)

    def test_a_citation_from_an_act_the_route_did_not_allow_withdraws_the_answer(self) -> None:
        original = RagPipeline._legacy_answer

        def leaking(pipeline, query, mode, **kwargs):  # a generation step that cites another Act
            response = original(pipeline, query, mode, **kwargs)
            response["citations"].append({"label": "model_context", "chunk_id": "x", "entry_id": "copyright-act-1957", "source_anchor": "pdf:page:3"})
            return response

        with patch.dict(os.environ, {"TLD_LIVE_INDIA_CODE": "0"}), patch.object(RagPipeline, "_legacy_answer", leaking):
            result = self.pipeline.answer("What does the Companies Act say about directors?", "specific")
        self.assertEqual(result["routing"]["reason_code"], "CITATION_OUTSIDE_ALLOWED_ACTS")
        self.assertEqual(result["routing"]["citation_check"], {"passed": False, "outside_entry_ids": ["copyright-act-1957"]})
        self.assertEqual((result["citations"], result["evidence"]), ([], []))
        self.assertIn("withdrawn", result["answer"]["direct_answer"])
        self.assertFalse(result["verification"]["passed"])


if __name__ == "__main__":
    unittest.main()


class RoutingEvalTests(unittest.TestCase):
    def test_the_versioned_question_set_routes_every_case_and_cites_no_other_act(self) -> None:
        from temporal_legal_drift.rag.routing_eval import run_routing_eval

        report = run_routing_eval(ROOT, ROOT / "configs/routing_eval/questions.v1.json")
        metrics = {name: item["value"] for name, item in report["metrics"].items()}
        missed = [row["case_id"] for row in report["cases"] if not row["resolved_correctly"]]
        self.assertEqual(missed, [])
        self.assertEqual(metrics["cross_act_contamination"], 0)
        self.assertEqual(metrics["citation_validity"], 1.0)
        self.assertEqual(metrics["helpful_abstention"], 1.0)
