"""rag-answer-v2: question frame, version evidence, the four determinations and the composed answer.

Real-corpus cases use graph v4, the silver materiality set and the risk registry. Cases marked SYNTHETIC
construct evidence directly to test an edge the corpus does not contain; they never claim legal truth.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from temporal_legal_drift.rag import determinations as det
from temporal_legal_drift.rag.question import QuestionFrame
from temporal_legal_drift.rag.rag_pipeline import RagPipeline

ROOT = Path(__file__).resolve().parents[2]
IT19 = "Compare Section 19 before and after the IT Amendment Act, 2008."
IT19_FACTS = {"reference_date": "2009-10-27", "organization_type": "foreign_certifying_authority", "industry": "trust_services",
              "jurisdiction": "IN", "activity": "certificate_recognition",
              "facts": {"gazette_notification": True, "government_approval": True, "recognition_in_force": True,
                        "regulatory_conditions_met": True, "is_digital_signature": True, "is_notified_electronic_signature": False}}


class RagV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._env = {k: os.environ.get(k) for k in ("TLD_LIVE_INDIA_CODE", "TLD_RAG_PROVIDER", "TLD_RAG_API_KEY", "OPENAI_API_KEY")}
        os.environ.update({"TLD_LIVE_INDIA_CODE": "0", "TLD_RAG_PROVIDER": "openai_compatible", "TLD_RAG_API_KEY": "", "OPENAI_API_KEY": ""})
        cls.pipeline = RagPipeline(ROOT)

    @classmethod
    def tearDownClass(cls) -> None:
        for name, value in cls._env.items():
            os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value)

    def ask(self, query: str, mode: str = "specific", scenario: dict | None = None) -> dict:
        return self.pipeline.answer(query, mode, scenario=scenario)

    # ---------- evidence and pairing ----------
    def test_named_act_and_section_select_the_corroborated_transition(self) -> None:
        result = self.ask("What amount must be deposited under section 173 of the Motor Vehicles Act after the 2019 amendment?")
        self.assertEqual(result["contract_version"], "rag-answer-v5")
        self.assertEqual(result["comparison"]["support_class"], "GRAPH_TRANSITION_FRAGMENTS")
        self.assertEqual({e["entry_id"] for e in result["evidence"]}, {"motor-vehicles-act-1988", "motor-vehicles-amendment-act-2019"})
        instruction = next(e for e in result["evidence"] if e["role"] == "amendment_instruction")
        self.assertTrue(instruction["verbatim"] and instruction["page"] and instruction["pdf_url"].endswith(f"#page={instruction['page']}"))
        self.assertIn("“ten thousand” was replaced by “one lakh”", result["answer"]["direct_answer"])

    def test_wrong_amending_act_is_rejected_not_paired(self) -> None:
        result = self.ask("Compare section 46 of the Companies Act before and after the Competition (Amendment) Act, 2023.")
        self.assertEqual(result["comparison"]["support_class"], "RELATION_MISMATCH")
        self.assertEqual(result["evidence"], [])
        self.assertIsNone(result["metrics"])
        self.assertIn("not recorded as amending", result["answer"]["direct_answer"])

    def test_footnote_reconstruction_cites_its_own_footnote_and_verified_act_number(self) -> None:
        version = self.ask(IT19)["version_evidence"]
        self.assertEqual(version["support_class"], "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION")
        self.assertEqual(version["footnote_act"], {"number": "10", "year": "2009", "section": "2"})  # "s. 2, ibid." resolved
        self.assertEqual(version["relation_verification"], "ACT_NUMBER_TEXT_VERIFIED")
        self.assertEqual(version["substitution"], {"old": "Digital Signature", "new": "electronic signature"})

    def test_uncorroborated_transition_is_not_presented_as_a_version(self) -> None:
        result = self.ask("What was omitted from section 11 of the Wild Life (Protection) Act by the 2022 amendment?")
        self.assertEqual(result["comparison"]["support_class"], "WEAK_TRANSITION_ONLY")
        self.assertIsNone(result["comparison"]["before"])
        self.assertEqual({d["state"] for k, d in result["determinations"].items() if k != "version" and k != "risk"}, {"INSUFFICIENT_EVIDENCE"})

    def test_unknown_act_is_out_of_scope_and_answers_from_nothing_else(self) -> None:
        result = self.ask("What does section 5 of the Shops and Commercial Establishments Act require?")
        self.assertEqual(result["answer"]["answer_type"], "out_of_scope")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["determinations"]["risk"]["state"], "OUT_OF_SCOPE")

    # ---------- materiality ----------
    def test_supported_materiality_is_provisional_machine_triage_with_provenance(self) -> None:
        result = self.ask("How did section 7 of the Arbitration and Conciliation Act change after the 2015 amendment regarding electronic communication?")
        materiality = result["determinations"]["materiality"]
        self.assertEqual(materiality["state"], "PROVISIONAL")
        self.assertEqual(materiality["details"]["pair_id"], "mat_1037bf61be63655a13f6f7af")
        self.assertFalse(materiality["details"]["is_gold"])
        self.assertIn(materiality["label"], {"High", "Medium", "Low", "None"} | {None}) if "/" not in str(materiality["label"]) else None
        self.assertNotIn("gold", (materiality["summary"] + materiality["reason"]).lower())
        self.assertEqual(materiality["review_status"], "NOT_REVIEWED_BY_QUALIFIED_EXPERT")

    def test_unmatched_amendment_gets_machine_triage_marked_as_computed_now(self) -> None:
        materiality = self.ask("What is the maximum fine a court can impose under section 32 of the Code of Civil Procedure after the 1999 amendment?")["determinations"]["materiality"]
        self.assertEqual(materiality["state"], "PROVISIONAL")
        self.assertEqual((materiality["details"]["source"], materiality["details"]["frozen_silver_match"], materiality["details"]["is_gold"]),
                         ("ON_THE_FLY_MACHINE_TRIAGE", False, False))
        self.assertIn("No frozen silver assessment", materiality["reason"])
        # Without supported versions there is nothing to triage.
        self.assertEqual(self.ask("Compare section 46 of the Companies Act before and after the Competition (Amendment) Act, 2023.")
                         ["determinations"]["materiality"]["limit"]["kind"], "evidence")

    # ---------- answer change ----------
    def test_answer_changes_for_a_numeric_question(self) -> None:
        change = self.ask("What is the maximum fine a court can impose under section 32 of the Code of Civil Procedure after the 1999 amendment?")["determinations"]["answer_change"]
        self.assertEqual((change["state"], change["label"]), ("DETERMINED", "Changes"))
        self.assertEqual([q["value"] for q in change["details"]["before"]], [500])
        self.assertEqual([q["value"] for q in change["details"]["after"]], [5000])

    def test_same_amount_but_different_sanction_is_reported_precisely(self) -> None:
        change = self.ask("What penalty applies under section 105 of the Companies Act after the amendment?")["determinations"]["answer_change"]
        self.assertEqual(change["label"], "Changes")
        self.assertIn("the figure is the same", change["summary"].lower())
        self.assertIn("from fine to penalty", change["summary"])
        self.assertIn("from an upper limit to a fixed amount", change["summary"])

    def test_modal_change_from_discretion_to_duty(self) -> None:
        change = self.ask("Is specific performance of a contract still discretionary under section 11 of the Specific Relief Act after the 2018 amendment?")["determinations"]["answer_change"]
        self.assertEqual((change["state"], change["label"]), ("DETERMINED", "Changes"))
        self.assertEqual((change["details"]["before"], change["details"]["after"]), (["discretion", "may"], ["shall"]))

    def test_what_changed_question_asks_for_a_situation_instead_of_inventing_one(self) -> None:
        # A deadline change can be decided by a fact, so that fact is asked for; nothing is assumed.
        change = self.ask("Compare section 31 of the Disaster Management Act before and after the Disaster Management (Amendment) Act, 2025.")["determinations"]["answer_change"]
        self.assertEqual((change["state"], change["label"]), ("NEEDS_FACTS", None))
        self.assertTrue(change["needs"])
        # Who may sign (Companies s.46) cannot be decided by a user fact: no facts are requested and no answer is invented.
        change = self.ask("Compare section 46 of the Companies Act before and after the Companies (Amendment) Act, 2015.")["determinations"]["answer_change"]
        self.assertEqual((change["state"], change["label"], change["needs"], change["limit"]["kind"]), ("INSUFFICIENT_EVIDENCE", None, [], "method"))

    def test_unsupported_applicability_makes_the_answer_conditional(self) -> None:
        # Act-wide commencement exists (2015-10-23) but scenario applicability is not established.
        change = self.ask("Can a respondent submit a counterclaim in the statement of defence under section 23 of the Arbitration and Conciliation Act after the 2015 amendment?",
                          scenario={"reference_date": "2016-01-01"})["determinations"]["answer_change"]
        self.assertEqual(change["state"], "CONDITIONAL")
        self.assertIn("not shown", change["reason"])

    def test_synthetic_stable_answer_despite_a_material_edit(self) -> None:
        # SYNTHETIC: wording changes (fine -> penalty, new discretion) but the period asked about does not.
        frame = QuestionFrame(query="How many days does a person have to pay?", question_type="quantity", asks_about_versions=True)
        versions = {"support_class": "GRAPH_TRANSITION_FRAGMENTS", "reason": "", "evidence": [], "date_basis": None,
                    "before": {"evidence_id": "E2", "text": "shall pay the fine within thirty days"},
                    "after": {"evidence_id": "E3", "text": "shall pay the fine within thirty days, and the Board may waive interest"}}
        change = det.answer_change(frame, versions, None, None)
        self.assertEqual((change["state"], change["label"]), ("DETERMINED", "Does not change"))

    def test_synthetic_small_numeric_edit_changes_the_answer(self) -> None:
        # SYNTHETIC: one word differs and it is the figure asked about.
        frame = QuestionFrame(query="How many days does a person have to pay?", question_type="quantity", asks_about_versions=True)
        versions = {"support_class": "GRAPH_TRANSITION_FRAGMENTS", "reason": "", "evidence": [], "date_basis": None,
                    "before": {"evidence_id": "E2", "text": "within thirty days"}, "after": {"evidence_id": "E3", "text": "within thirty-one days"}}
        self.assertEqual(det.answer_change(frame, versions, None, None)["label"], "Changes")

    # ---------- risk ----------
    def test_risk_rule_match_is_conditional_and_compares_both_versions(self) -> None:
        result = self.ask(IT19, scenario=IT19_FACTS)
        risk, change = result["determinations"]["risk"], result["determinations"]["answer_change"]
        self.assertEqual((risk["state"], risk["label"]), ("CONDITIONAL", "Medium"))
        self.assertEqual(risk["details"]["rule_id"], "it19-post-conditional-v1")
        self.assertEqual((change["state"], change["label"]), ("CONDITIONAL", "Changes"))
        self.assertIn("meets the modelled rule", change["summary"])

    def test_risk_rule_date_mismatch_abstains_and_never_reads_as_no_risk(self) -> None:
        risk = self.ask(IT19, scenario={**IT19_FACTS, "reference_date": "2015-06-01"})["determinations"]["risk"]
        self.assertEqual((risk["state"], risk["label"]), ("INSUFFICIENT_EVIDENCE", None))
        self.assertIn("no rule covers your reference date", risk["reason"])
        self.assertIn("not 'no risk'", risk["reason"])

    def test_risk_needs_facts_without_a_scenario_and_is_out_of_scope_without_a_rule(self) -> None:
        self.assertEqual(self.ask(IT19)["determinations"]["risk"]["state"], "NEEDS_FACTS")
        self.assertEqual(self.ask("What amount must be deposited under section 173 of the Motor Vehicles Act after the 2019 amendment?")
                         ["determinations"]["risk"]["state"], "OUT_OF_SCOPE")

    def test_risk_ignores_drift_and_materiality(self) -> None:
        import inspect

        self.assertEqual(list(inspect.signature(det.risk).parameters), ["root", "frame", "versions", "scenario"])
        result = self.ask(IT19, scenario=IT19_FACTS)
        result_again = self.ask(IT19 + " Is it material?", scenario=IT19_FACTS)
        self.assertEqual(result["determinations"]["risk"]["label"], result_again["determinations"]["risk"]["label"])

    def test_scenario_is_validated_at_the_boundary(self) -> None:
        for bad in ({"unknown": 1}, {"reference_date": "13/10/2026"}, {"facts": {"Bad Key": True}}, {"facts": {"x": [1]}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.ask(IT19, scenario=bad)

    # ---------- answer form ----------
    def test_machine_triage_reads_number_words(self) -> None:
        # CPC s.32 "five hundred" -> "five thousand": the frozen rules see digits only, so triage-input-v2 converts number words first
        mat = self.ask("What is the maximum fine a court can impose under section 32 of the Code of Civil Procedure after the 1999 amendment?")["determinations"]["materiality"]
        self.assertEqual(mat["details"]["source"], "ON_THE_FLY_MACHINE_TRIAGE")
        self.assertEqual((mat["details"]["scored_operands"]["before_text"].strip(), mat["details"]["scored_operands"]["after_text"].strip()), ("not exceeding 500 rupees", "not exceeding 5000 rupees"))
        self.assertNotIn("Low", mat["label"])

    def test_specific_and_generic_use_the_same_evidence(self) -> None:
        specific, generic = self.ask(IT19, "specific"), self.ask(IT19, "generic")
        self.assertEqual(specific["evidence"], generic["evidence"])
        self.assertEqual(specific["metrics"]["overall_drift_percent"], generic["metrics"]["overall_drift_percent"])
        # Same sources and scores in both modes; only the explanation detail differs.
        for name in ("wording_drift", "rule_drift", "outcome_drift"):
            self.assertEqual({k: specific["fingerprint"][name][k] for k in ("state", "value", "label", "evidence_ids")},
                             {k: generic["fingerprint"][name][k] for k in ("state", "value", "label", "evidence_ids")})
        self.assertEqual(specific["fingerprint"]["reading"], generic["fingerprint"]["reading"])
        # composition v2: no "effect" section until facts are applied
        self.assertEqual([s["id"] for s in specific["answer"]["sections"]], ["before", "after", "what_changed"])
        self.assertEqual([s["id"] for s in generic["answer"]["sections"]], ["what_changed"])

    def test_every_answer_section_with_a_claim_cites_evidence(self) -> None:
        result = self.ask(IT19)
        known = {e["evidence_id"] for e in result["evidence"]}
        for section in result["answer"]["sections"]:
            self.assertTrue(section["evidence_ids"], section["id"])
            self.assertLessEqual(set(section["evidence_ids"]), known)
        labels = " ".join(s.get("label") or "" for s in result["answer"]["sections"])
        self.assertIn("reconstructed from the India Code footnote", labels)
        self.assertIn("current consolidated text", labels)

    def test_general_question_answers_from_the_matching_section(self) -> None:
        result = self.ask("What is the punishment for removal of human organs without authority under the Transplantation of Human Organs Act?", "generic")
        self.assertTrue(result["answer"]["direct_answer"].startswith("Section 18 (Punishment for removal of human organ without authority)"))
        self.assertEqual({d["state"] for k, d in result["determinations"].items() if k != "version"}, {"OUT_OF_SCOPE"})
        self.assertTrue(all(d["reason"] for k, d in result["determinations"].items() if k != "version"))


if __name__ == "__main__":
    unittest.main()
