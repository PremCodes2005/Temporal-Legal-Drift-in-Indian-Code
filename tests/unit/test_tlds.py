"""Hybrid Temporal Legal Drift Score (tlds-v1): software-correctness tests.

All clauses are SYNTHETIC and deterministic; they test the calculation, not legal accuracy. There are no
expert-reviewed legal labels, so these tests do not validate the legal-effect rubric empirically.
"""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from temporal_legal_drift.rag import fingerprint as fp
from temporal_legal_drift.rag.retriever import HybridRetriever

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "configs/metrics/tlds.v1.json").read_text())
EMBED = HybridRetriever.embed_text


def score(before: str, after: str, embed=EMBED, weights=None) -> dict:
    pair = {"before": before, "after": after, "before_evidence": ["E1"], "after_evidence": ["E2"]}
    return fp.tlds(pair, fp.rule_drift(pair, fp.changed_spans(before, after)), embed, weights=weights)


def values(result: dict) -> dict:
    return {name: c["value"] for name, c in result["components"].items()}


DUTY = "The employer shall disclose the report to the Board."


class TldsTests(unittest.TestCase):
    def test_identical_and_formatting_only_are_zero(self) -> None:
        for after in (DUTY, "the  employer SHALL disclose the report, to the Board"):
            result = score(DUTY, after)
            self.assertEqual((result["state"], result["value"], result["band"]), ("COMPLETE", 0.0, "Very low"))
            self.assertEqual(set(values(result).values()), {0.0})

    def test_single_word_substitution(self) -> None:
        result = score(DUTY, DUTY.replace("Board", "Commissioner"))
        self.assertAlmostEqual(values(result)["textual"], 1 / 9)
        self.assertEqual(values(result)["legal_effect"], 0.5)  # the person or body changed
        self.assertEqual(result["state"], "COMPLETE")

    def test_negation_is_a_reversal(self) -> None:
        result = score(DUTY, DUTY.replace("shall", "shall not"))
        self.assertAlmostEqual(values(result)["textual"], 1 / 10)
        self.assertEqual(values(result)["legal_effect"], 1.0)
        self.assertIn("reversal", result["components"]["legal_effect"]["reason"])
        # A one-word edit with a reversed duty is not hidden: L is exposed, and the composite exceeds a changed deadline's.
        deadline = score("Every company shall file the return within ten days.", "Every company shall file the return within fifteen days.")
        self.assertGreater(result["value"], deadline["value"])

    def test_numbers_dates_and_deadlines_keep_their_spans(self) -> None:
        cases = [("Every company shall file the return within ten days.", "Every company shall file the return within fifteen days.", "deadline"),
                 ("The fee shall not exceed five hundred rupees.", "The fee shall not exceed five thousand rupees.", "threshold"),
                 ("The return shall be filed before 1 April 2020.", "The return shall be filed before 1 April 2021.", None)]
        for before, after, field in cases:
            result = score(before, after)
            self.assertGreater(values(result)["textual"], 0)
            if field:
                change = result["components"]["legal_effect"]["details"]["changes"][0]
                self.assertEqual((change["field"], change["score"]), (field, 0.5))
                self.assertTrue(change["before_spans"] and change["after_spans"])
                self.assertIn(after[change["after_spans"][0][0]:change["after_spans"][0][1]], after)
            else:  # a changed date is outside the supported fields: legal effect is missing, never 0
                self.assertIsNone(values(result)["legal_effect"])
                self.assertEqual(result["state"], "INCOMPLETE")

    def test_inserted_and_deleted_obligations(self) -> None:
        base = "The employer may disclose the report."
        added = base + " The employer shall publish the report within thirty days."
        for before, after in ((base, added), (added, base)):
            result = score(before, after)
            self.assertEqual(values(result)["legal_effect"], 0.75)
            self.assertGreater(values(result)["rule_structure"], 0)

    def test_added_and_removed_exceptions(self) -> None:
        with_proviso = DUTY + " Provided that a small employer need not disclose it."
        for before, after in ((DUTY, with_proviso), (with_proviso, DUTY)):
            changes = score(before, after)["components"]["legal_effect"]["details"]["changes"]
            self.assertIn("exception", {c["field"] for c in changes})

    def test_rewording_with_the_same_effect_keeps_legal_effect_low(self) -> None:
        result = score("The company shall file the return within thirty days.", "Within thirty days, the return shall be filed by the company.")
        # shortcut: "file" vs "be filed" still reads as an action change (L = 0.25); see the methodology's known limits.
        self.assertGreater(values(result)["textual"], 0.5)
        self.assertLessEqual(values(result)["legal_effect"], 0.25)

    def test_complete_replacement_and_empty_inputs(self) -> None:
        self.assertEqual(fp.textual_component("alpha beta gamma", "delta epsilon")["value"], 1.0)
        self.assertEqual(fp.textual_component("", "alpha beta")["value"], 1.0)
        self.assertIsNone(fp.textual_component("", " ;, ")["value"])  # nothing to compare is missing, not 0
        self.assertIsNone(fp.semantic_component("", "", EMBED, "m")["value"])  # zero vectors: cosine undefined

    def test_invalid_embeddings_are_missing(self) -> None:
        def boom(_: str):
            raise TimeoutError

        lengths = iter([2, 3])
        for embed in (lambda _: None, lambda _: [], lambda _: [math.nan, 1.0], lambda _: [1.0] * next(lengths), lambda _: ["1", "0"], boom):
            result = score(DUTY, DUTY.replace("shall", "may"), embed=embed)
            self.assertIsNone(values(result)["semantic"])
            self.assertEqual((result["state"], result["value"], result["missing_components"]), ("INCOMPLETE", None, ["semantic"]))

    def test_partial_score_is_separate_and_renormalised(self) -> None:
        result = fp.composite({"textual": 0.5, "semantic": None, "legal_effect": 1.0, "rule_structure": 0.0})
        self.assertIsNone(result["value"])
        self.assertAlmostEqual(result["partial_value"], 100 * (0.2 * 0.5 + 0.4 * 1.0) / 0.7)
        self.assertIn("not comparable", result["partial_label"])
        nothing = fp.composite(dict.fromkeys(fp.TLDS_COMPONENTS))
        self.assertEqual((nothing["state"], nothing["partial_value"]), ("INCOMPLETE", None))
        unavailable = fp.tlds(None, None, None, unavailable="no pair")
        self.assertEqual(unavailable["missing_components"], list(fp.TLDS_COMPONENTS))

    def test_bounds_and_weight_validation(self) -> None:
        self.assertEqual(fp.composite(dict.fromkeys(fp.TLDS_COMPONENTS, 1.0))["value"], 100.0)
        self.assertEqual(fp.composite(dict.fromkeys(fp.TLDS_COMPONENTS, 0.0))["value"], 0.0)
        for bad in (1.2, -0.1, True):
            with self.assertRaises(ValueError):
                fp.composite({**dict.fromkeys(fp.TLDS_COMPONENTS, 0.5), "textual": bad})
        good = CONFIG["weights"]
        for weights in ({**good, "textual": 0.3}, {**good, "textual": -0.2, "semantic": 0.7}, {k: good[k] for k in list(good)[:3]},
                        {**good, "textual": math.nan}, {**good, "extra": 0.0}):
            with self.assertRaises(ValueError):
                fp.composite(dict.fromkeys(fp.TLDS_COMPONENTS, 0.5), weights)
        self.assertAlmostEqual(sum(good.values()), 1.0)

    def test_bands_use_the_displayed_value(self) -> None:
        bands = CONFIG["bands"]
        self.assertEqual([fp._band(v, bands) for v in (0, 9.94, 9.96, 29.9, 30, 49.9, 50, 74.9, 75, 100)],
                         ["Very low", "Very low", "Low", "Low", "Moderate", "Moderate", "High", "High", "Very high", "Very high"])

    def test_reproducible_and_alternative_weights(self) -> None:
        before, after = DUTY, DUTY.replace("shall", "shall not")
        first, second = score(before, after), score(before, after)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        equal = dict.fromkeys(fp.TLDS_COMPONENTS, 0.25)
        alt = score(before, after, weights=equal)
        self.assertEqual(alt["weights"], equal)
        self.assertAlmostEqual(alt["value"], 25 * sum(values(alt).values()))
        self.assertNotEqual(alt["value"], first["value"])

    def test_composite_matches_components_internally(self) -> None:
        result = score("Every company shall file the return within ten days.", "Every company shall file the return within fifteen days.")
        expected = 100 * sum(CONFIG["weights"][n] * v for n, v in values(result).items())
        self.assertEqual(result["value"], expected)  # stored unrounded; only the label rounds
        self.assertEqual(result["tldp_percent"], result["value"])
        self.assertTrue(result["label"].startswith(f"{expected:.1f}/100"))


    # ---------- tlds-v1.1: contributions, disagreement, unchanged values ----------
    def test_contributions_add_up_to_the_score_and_missing_ones_stay_empty(self) -> None:
        result = score("Every company shall file the return within ten days.", "Every company shall file the return within fifteen days.")
        self.assertAlmostEqual(sum(result["contributions"].values()), result["value"])
        for name, points in result["contributions"].items():
            self.assertAlmostEqual(points, 100 * CONFIG["weights"][name] * values(result)[name])
        partial = fp.composite({"textual": 0.5, "semantic": None, "legal_effect": 1.0, "rule_structure": 0.0})
        self.assertIsNone(partial["contributions"]["semantic"])  # never 0
        self.assertEqual(partial["contributions"]["legal_effect"], 40.0)

    def test_one_component_at_0_and_another_at_100_is_flagged_not_hidden(self) -> None:
        legal_only = fp.composite({"textual": 0.0, "semantic": 0.0, "legal_effect": 1.0, "rule_structure": 0.0})
        self.assertEqual((legal_only["value"], legal_only["band"]), (40.0, "Moderate"))
        self.assertEqual((legal_only["disagreement"]["strong"], legal_only["disagreement"]["highest"]), (True, "legal_effect"))
        wording_only = fp.composite({"textual": 1.0, "semantic": 1.0, "legal_effect": 0.0, "rule_structure": 0.0})
        self.assertEqual((wording_only["value"], wording_only["disagreement"]["lowest"]), (50.0, "legal_effect"))
        agree = fp.composite(dict.fromkeys(fp.TLDS_COMPONENTS, 0.5))
        self.assertEqual((agree["disagreement"]["spread"], agree["disagreement"]["strong"]), (0.0, False))
        self.assertIsNone(fp.composite(dict.fromkeys(fp.TLDS_COMPONENTS))["disagreement"])

    def test_v1_1_reproduces_every_held_out_v1_score(self) -> None:
        report = json.loads((ROOT / "reports/fingerprint/tlds_heldout.v1.json").read_text())
        complete = [row for row in report["rows"] if row["state"] == "COMPLETE"]
        self.assertEqual(len(complete), 59)
        for row in complete:
            self.assertAlmostEqual(fp.composite(row["components"])["value"], row["by_weighting"]["default"], places=9)

    def test_every_weight_has_a_stated_rationale_and_honest_status(self) -> None:
        self.assertEqual(set(CONFIG["component_rationale"]), set(fp.TLDS_COMPONENTS))
        for name, text in CONFIG["component_rationale"].items():
            self.assertTrue(text["why_this_weight"].startswith(f"{CONFIG['weights'][name]:.2f}"), name)
        self.assertRegex(CONFIG["weights_status"], r"not learned from data, not optimised and not legally validated")


if __name__ == "__main__":
    unittest.main()
