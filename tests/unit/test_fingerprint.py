"""Legal Change Fingerprint acceptance tests (legal-change-fingerprint-v1).

Real-corpus cases use graph-v4 transitions and India Code footnotes across several Acts. Cases marked
SYNTHETIC build evidence directly to test an edge the corpus lacks; they make no claim about real law.
"""

from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path

from temporal_legal_drift.rag import fingerprint as fp
from temporal_legal_drift.rag.metrics import calculate_drift_metrics
from temporal_legal_drift.rag.rag_pipeline import RagPipeline

ROOT = Path(__file__).resolve().parents[2]
RULE_WEIGHTS = {k: v["weight"] for k, v in json.loads((ROOT / "configs/metrics/rule_drift.v1.2.json").read_text())["fields"].items()}
CPC = "What is the maximum fine a court can impose under section 32 of the Code of Civil Procedure after the 1999 amendment?"
SRA = "Is specific performance of a contract still discretionary under section 11 of the Specific Relief Act after the 2018 amendment?"
MV181 = "What was the penalty under section 181 of the Motor Vehicles Act before and after the 2019 amendment?"
ARB8 = "Compare section 8 of the Arbitration and Conciliation Act before and after the Arbitration and Conciliation (Amendment) Act, 2015."
ARB23 = "Can a respondent submit a counterclaim in the statement of defence under section 23 of the Arbitration and Conciliation Act after the 2015 amendment?"
DM31 = "How often must the district disaster management plan be reviewed under section 31 of the Disaster Management Act after the 2025 amendment?"


def synthetic(before_words: str, after_words: str, clause: str, *, reliability: str = "NO_KNOWN_EXTRACTION_RISK") -> dict:
    """SYNTHETIC graph-style evidence: E4 is today's clause with this amendment's words marked 1[...]."""
    item = lambda eid, role, text: {"evidence_id": eid, "role": role, "text": text, "text_reliability": reliability, "entry_id": "synthetic"}  # noqa: E731
    return {"support_class": "GRAPH_TRANSITION_FRAGMENTS", "reason": "", "evidence": [
        item("E1", "amendment_instruction", f"In section 7, for the words “{before_words}”, the words “{after_words}” shall be substituted."),
        item("E2", "before_fragment", before_words), item("E3", "after_fragment", after_words), item("E4", "current_consolidated_text", clause)],
        "before": {"evidence_id": "E2", "text": before_words}, "after": {"evidence_id": "E3", "text": after_words}}


DEADLINE = synthetic("within ten days", "within fifteen days",
                     "7. Filing of returns.—(1) Every company shall file the return 1[within fifteen days] of the end of the quarter. "
                     "1. Subs. by Act 1 of 2020, s. 2, for “within ten days” (w.e.f. 1-1-2021).")


class FingerprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._env = {k: os.environ.get(k) for k in ("TLD_LIVE_INDIA_CODE", "TLD_RAG_PROVIDER", "TLD_RAG_API_KEY", "OPENAI_API_KEY", "TLD_RULE_DELTA_LLM")}
        os.environ.update({"TLD_LIVE_INDIA_CODE": "0", "TLD_RAG_PROVIDER": "openai_compatible", "TLD_RAG_API_KEY": "", "OPENAI_API_KEY": "", "TLD_RULE_DELTA_LLM": "0"})
        cls.pipeline = RagPipeline(ROOT)
        cls.embed = staticmethod(cls.pipeline.retriever.embed_text)

    @classmethod
    def tearDownClass(cls) -> None:
        for name, value in cls._env.items():
            os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value)

    def build(self, versions: dict, facts: dict | None = None, proposer=None) -> dict:
        return fp.build_fingerprint(versions, {"facts": facts} if facts is not None else None, self.embed, None, None, proposer=proposer)

    def ask(self, query: str, mode: str = "specific", scenario: dict | None = None) -> dict:
        return self.pipeline.answer(query, mode, scenario=scenario)

    def test_tlds_sits_beside_the_three_measures(self) -> None:
        # Real corpus: CPC s.32, "five hundred" -> "five thousand" rupees. Legal effect stays visible although the composite is Low.
        result = self.ask(CPC)
        f, t = result["fingerprint"], result["fingerprint"]["tlds"]
        self.assertEqual((t["version"], t["state"], t["components"]["legal_effect"]["value"]), ("tlds-v1", "COMPLETE", 0.5))
        self.assertEqual(f["rule_drift"]["value"], 15.0)  # the v1.2 measures are unchanged
        self.assertEqual(t["components"]["textual"]["details"]["edit_distance"], 1)
        general = self.ask("What does the Consumer Protection Act say about mediation?")["fingerprint"]["tlds"]
        self.assertEqual((general["state"], general["value"]), ("NOT_APPLICABLE", None))

    # ---------- wording drift ----------
    def test_identical_text_is_zero_everywhere(self) -> None:
        # SYNTHETIC
        f = self.build(synthetic("within ten days", "within ten days", "7. Returns.—Every company shall file 1[within ten days]."))
        self.assertEqual((f["wording_drift"]["value"], f["wording_drift"]["details"]["flag"]), (0.0, "IDENTICAL"))
        self.assertEqual(f["rule_drift"]["value"], 0.0)

    def test_spelling_only_change_is_formatting_not_drift(self) -> None:
        # SYNTHETIC: -ise/-ize spelling and punctuation only
        f = self.build(synthetic("authorised organisation", "authorized organization,",
                                 "7. Returns.—Every 1[authorized organization,] shall file the return."))
        self.assertEqual((f["wording_drift"]["value"], f["wording_drift"]["details"]["flag"]), (0.0, "FORMATTING_ONLY"))
        self.assertEqual(f["rule_drift"]["value"], 0.0)

    def test_large_non_operative_rewording_has_wording_but_no_rule_drift(self) -> None:
        # SYNTHETIC: a long Explanation is reworded; no duty, power, period, amount or penalty is touched
        before = "In this section the words have the meaning given in the Schedule to this Act"
        after = "For the purposes of this section, expressions used here carry the meanings assigned to them in the Schedule"
        f = self.build(synthetic(before, after, f"7. Returns.—(1) Every company shall file the return. Explanation.—1[{after}]."))
        self.assertGreater(f["wording_drift"]["value"], 20)
        # v1.2: no supported field changed, but the clause did; that is "Not scored", never a 0 claiming no rule change
        self.assertEqual((f["rule_drift"]["state"], f["rule_drift"]["value"]), ("INSUFFICIENT_EVIDENCE", None))
        self.assertTrue(any(r["kind"] == "disagreement" and "no supported rule field" in r["text"] for r in f["reading"]))

    def test_spans_and_citations_point_to_the_scored_text(self) -> None:
        result = self.ask(CPC)
        wording = result["fingerprint"]["wording_drift"]
        before, after = wording["details"]["before_clause"], wording["details"]["after_clause"]
        for span in wording["details"]["spans"]:
            self.assertEqual(before[slice(*span["before_offsets"])], span["before_text"])
            self.assertEqual(after[slice(*span["after_offsets"])], span["after_text"])
        self.assertEqual([(s["before_text"], s["after_text"]) for s in wording["details"]["spans"]], [("hundred", "thousand")])
        evidence = {e["evidence_id"]: e for e in result["evidence"]}
        self.assertTrue(set(wording["evidence_ids"]) <= set(evidence))
        consolidated = next(e for e in result["evidence"] if e["role"] == "current_consolidated_text")
        self.assertIn(after, fp.clean_clause(consolidated["text"]))  # the scored after clause is the cited verbatim text
        self.assertTrue(consolidated["page"] and consolidated["pdf_url"])

    def test_wording_drift_reproduces_from_the_api_response(self) -> None:
        wording = self.ask(SRA)["fingerprint"]["wording_drift"]
        d = wording["details"]
        recomputed = calculate_drift_metrics(fp._normalise(d["before_clause"]), fp._normalise(d["after_clause"]),
                                             pre_vector=self.embed(fp._normalise(d["before_clause"])),
                                             post_vector=self.embed(fp._normalise(d["after_clause"])))
        self.assertEqual(d["inputs"], {"lexical_drift_percent": recomputed["lexical_drift_percent"],
                                       "feature_vector_drift_percent": recomputed["semantic_drift_percent"]})
        self.assertAlmostEqual(wording["value"], 0.5 * d["inputs"]["lexical_drift_percent"] + 0.5 * d["inputs"]["feature_vector_drift_percent"], delta=0.06)

    # ---------- rule drift ----------
    def test_rule_drift_reproduces_from_its_fields_and_versioned_weights(self) -> None:
        for query in (CPC, SRA, MV181, ARB8, DM31):
            with self.subTest(query=query[:40]):
                rule = self.ask(query)["fingerprint"]["rule_drift"]
                rows = rule["details"]["fields"]
                self.assertEqual(rule["value"], sum(RULE_WEIGHTS[r["field"]] for r in rows if r["operation"] in {"ADDED", "REMOVED", "CHANGED"}))
                for row in rows:
                    if row["operation"] != "ABSENT":
                        self.assertTrue(row["before_spans"] or row["after_spans"])

    def test_rule_fields_across_acts_and_operations(self) -> None:
        changed = lambda q: {r["field"]: r["operation"] for r in self.ask(q)["fingerprint"]["rule_drift"]["details"]["fields"] if r["contribution"]}  # noqa: E731
        self.assertEqual(changed(SRA), {"modality": "CHANGED"})                                   # discretion -> duty (substitution)
        self.assertEqual(changed(CPC), {"penalty": "CHANGED"})                                    # fine 500 -> 5000, counted once as penalty
        self.assertEqual(changed(DM31), {"deadline": "CHANGED"})                                   # annually -> every two years
        self.assertEqual(changed(ARB8)["exception"], "ADDED")                                      # proviso inserted (insertion)
        self.assertEqual(changed(MV181), {"penalty": "CHANGED"})                                  # the fine amount is not counted twice
        self.assertEqual(changed("What amount must be deposited under section 173 of the Motor Vehicles Act after the 2019 amendment?"),
                         {"threshold": "CHANGED"})                                                  # ten thousand -> one lakh (number words)
        self.assertEqual(changed("How many nominees can a depositor make under section 45ZC of the Banking Regulation Act after the 2025 amendment?"),
                         {"threshold": "ADDED"})                                                    # count limit: not exceeding four

    def test_a_change_outside_the_supported_fields_is_not_scored_with_a_specific_reason(self) -> None:
        # rule-drift-v1.2: never 0 for a real change; the reason names the changed words
        cases = {"Compare section 170 of the Motor Vehicles Act before and after the Motor Vehicles (Amendment) Act, 2019.": "CROSS_REFERENCE_ONLY",
                 "Compare Section 19 before and after the IT Amendment Act, 2008.": "TERM_SUBSTITUTED",
                 "Compare section 40 of the Motor Vehicles Act before and after the Motor Vehicles (Amendment) Act, 2019.": "UNSUPPORTED_RULE_FIELD"}
        for query, code in cases.items():
            with self.subTest(code=code):
                rule = self.ask(query)["fingerprint"]["rule_drift"]
                self.assertEqual((rule["state"], rule["label"], rule["value"], rule["details"]["unscored_reason"]), ("INSUFFICIENT_EVIDENCE", "Not scored", None, code))
                self.assertEqual(rule["limit"]["kind"], "method")
                self.assertIn("“", rule["reason"])  # the changed words are quoted

    def test_structure_changes_are_scope_not_new_duties(self) -> None:
        # an inserted list item in a rule-making power is scope (v1.1 counted its "may" as a new permission)
        rule = self.ask("Compare section 240 of the Insolvency Bankruptcy Code before and after the Insolvency And Bankruptcy Code (Amendment) Act, 2020.")["fingerprint"]["rule_drift"]
        self.assertEqual({r["field"] for r in rule["details"]["fields"] if r["contribution"]}, {"scope"})
        self.assertTrue(rule["details"]["structural_changes"][0]["value"].startswith("list item:"))

    def test_a_small_edit_to_a_key_field_is_explained_not_averaged(self) -> None:
        # real corpus: IBC s.99 "ten days" -> "twenty-one days", reconstructed from India Code's footnote (Act 6 of 2026)
        f = self.ask("Compare section 99 of the Insolvency and Bankruptcy Code before and after the 2026 amendment.")["fingerprint"]
        self.assertLess(f["wording_drift"]["value"], 2)
        self.assertEqual(f["rule_drift"]["value"], 15.0)
        self.assertEqual([r["field"] for r in f["rule_drift"]["details"]["fields"] if r["contribution"]], ["deadline"])
        disagreement = [r for r in f["reading"] if r["kind"] == "disagreement"]
        self.assertEqual(len(disagreement), 1)
        self.assertIn("deadline or period", disagreement[0]["text"])

    def test_conflicting_signals_are_shown_side_by_side_never_averaged(self) -> None:
        f = self.ask(SRA)["fingerprint"]
        self.assertLess(f["wording_drift"]["value"], 10)   # few words changed...
        self.assertEqual(f["rule_drift"]["value"], 25.0)   # ...but the duty flipped
        self.assertNotIn("overall", f)
        self.assertIn("never averaged", f["note"])

    # ---------- LLM proposals ----------
    def test_model_timeout_keeps_the_deterministic_rule_delta(self) -> None:
        def timeout(pair):
            raise TimeoutError("timed out")
        plain, with_model = self.build(DEADLINE), self.build(DEADLINE, proposer=timeout)
        self.assertEqual(with_model["rule_drift"]["value"], plain["rule_drift"]["value"])
        self.assertEqual(with_model["rule_drift"]["details"]["llm_proposal"]["status"], "FAILED_DETERMINISTIC_RESULT_USED")

    def test_llm_proposals_are_kept_only_when_verbatim_and_schema_valid(self) -> None:
        pair = fp.clause_pair(DEADLINE)
        self.assertEqual(fp.validate_proposal({"fields": [{"field": "scope", "before": "the return", "after": "invented words"}]}, pair), [])
        self.assertEqual(fp.validate_proposal({"fields": [{"field": "not_a_field", "before": "the return", "after": "the return"}]}, pair), [])
        self.assertEqual(len(fp.validate_proposal({"fields": [{"field": "scope", "before": "the return", "after": "the return"}]}, pair)), 1)

    # ---------- outcome drift ----------
    def test_ten_to_fifteen_day_deadline_flips_only_for_day_twelve(self) -> None:
        # SYNTHETIC: 10 -> 15 days; filing on day 5 is on time under both, on day 12 only under the new rule
        day5 = self.build(DEADLINE, {"elapsed_days": 5})["outcome_drift"]
        day12 = self.build(DEADLINE, {"elapsed_days": 12})["outcome_drift"]
        self.assertEqual((day5["label"], day5["value"]), ("Unchanged", 0.0))
        self.assertEqual((day12["label"], day12["value"]), ("Changed", 100.0))
        self.assertIn("outside the time limit → within the time limit", day12["summary"])
        controlled = day12["details"]["controlled_scenarios"]
        # 11, 14 and 15 are late under ten days but on time under fifteen: 3 flips of 6 boundary scenarios.
        self.assertEqual((controlled["values_tested"], controlled["flips"], controlled["evaluated"], controlled["percent"]), ([9, 10, 11, 14, 15, 16], 3, 6, 50.0))

    def test_missing_scenario_facts_ask_for_exactly_what_is_needed(self) -> None:
        outcome = self.ask(DM31)["fingerprint"]["outcome_drift"]
        self.assertEqual((outcome["state"], outcome["label"]), ("NEEDS_FACTS", "Cannot determine"))
        self.assertEqual([n["key"] for n in outcome["needs"]], ["facts.elapsed_months"])
        self.assertIsNone(outcome["value"])  # missing is never 0

    def test_added_exception_changes_the_outcome_when_its_conditions_are_met(self) -> None:
        met = self.ask(ARB8, scenario={"facts": {"exception_conditions_met": True, "within_scope": True}})["fingerprint"]["outcome_drift"]
        self.assertEqual(met["label"], "Changed")
        self.assertTrue(any(r["field"] == "exception" and r["changed"] for r in met["details"]["evaluated"]))

    def test_penalty_change_with_and_without_contravention(self) -> None:
        breach = self.ask(MV181, scenario={"facts": {"contravention": True, "amount": 1000}})["fingerprint"]["outcome_drift"]
        self.assertEqual(breach["label"], "Changed")
        none = self.ask(MV181, scenario={"facts": {"contravention": False, "amount": 100}})["fingerprint"]["outcome_drift"]
        self.assertEqual(none["label"], "Unchanged")

    def test_wrong_date_reports_the_wording_for_that_date_separately(self) -> None:
        result = self.ask(ARB23, scenario={"reference_date": "2014-01-01", "facts": {"within_scope": True}})
        timing = result["determinations"]["applicability"]
        self.assertEqual((timing["state"], timing["label"]), ("CONDITIONAL", "Before-amendment wording"))
        self.assertEqual(timing["details"]["publication"]["status"], "NOT_IN_THIS_EVIDENCE")  # separate from commencement
        self.assertEqual(timing["details"]["commencement"]["date"], "2015-10-23")
        self.assertIn("before-amendment answer would apply", result["fingerprint"]["outcome_drift"]["summary"])

    # ---------- gates ----------
    def test_wrong_provision_or_wrong_act_is_never_scored(self) -> None:
        for query in ("Compare section 2 of the Factories Act before and after the 2016 amendment.",
                      "Compare section 46 of the Companies Act before and after the Competition (Amendment) Act, 2023."):
            with self.subTest(query=query[:40]):
                f = self.ask(query)["fingerprint"]
                self.assertEqual({c["state"] for c in (f["wording_drift"], f["rule_drift"], f["outcome_drift"])}, {"INSUFFICIENT_EVIDENCE"})
                self.assertIsNone(f["wording_drift"]["value"])
                self.assertTrue(f["wording_drift"]["next_action"])

    def test_incomplete_before_text_abstains(self) -> None:
        # SYNTHETIC: the consolidated clause does not contain the amended words, so the earlier clause cannot be rebuilt
        f = self.build(synthetic("within ten days", "within fifteen days", "7. Returns.—Every company shall file the return…"))
        self.assertEqual(f["wording_drift"]["state"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("could not be located", f["wording_drift"]["reason"])

    def test_ocr_corruption_is_not_scored_as_law(self) -> None:
        # SYNTHETIC: garbled OCR text in the clause, and separately a source with a known unreliable text layer
        garbled = self.build(synthetic("~fficer lnak~ng", "officer making", "7. Returns.—The 1[officer making] the return shall sign it."))
        self.assertEqual(garbled["wording_drift"]["state"], "INSUFFICIENT_EVIDENCE")
        unreliable = self.build(synthetic("within ten days", "within fifteen days", DEADLINE["evidence"][3]["text"], reliability="UNRELIABLE_TEXT_LAYER"))
        self.assertIn("unreliable text layer", unreliable["rule_drift"]["reason"])

    # ---------- integration ----------
    def test_modes_share_evidence_and_calculations(self) -> None:
        specific, generic = self.ask(DM31, "specific"), self.ask(DM31, "generic")
        self.assertEqual(specific["fingerprint"], generic["fingerprint"])

    def test_legacy_overall_is_kept_and_labelled_and_risk_is_independent(self) -> None:
        result = self.ask(SRA)
        self.assertIn("overall_drift_percent", result["metrics"]["legacy_diagnostic"]["fields"])
        self.assertIsNotNone(result["metrics"]["overall_drift_percent"])
        self.assertEqual(result["determinations"]["risk"]["state"], "OUT_OF_SCOPE")  # no registry rule; drift never sets risk
        self.assertEqual(result["determinations"]["textual_drift"]["details"]["use"], "fingerprint.wording_drift")


if __name__ == "__main__":
    unittest.main()
