from __future__ import annotations

import unittest

from temporal_legal_drift.comparison import analyze_legal_drift


class LegalDriftComparisonTests(unittest.TestCase):
    def test_deadline_change_is_material_even_when_obligation_is_stable(self) -> None:
        result = analyze_legal_drift(
            "A company shall submit the document within 10 days.",
            "A company shall submit the document within 15 days.",
            "Is a filing submitted on day 12 compliant?",
            "The company submitted the document on day 12.",
        )
        self.assertEqual(result["classification"]["materiality"], "Medium")
        self.assertTrue(result["classification"]["legal_rule_changed"])
        self.assertTrue(result["classification"]["obligation_type_stable"])
        self.assertEqual(result["compliance"]["pre_answer"], "non_compliant")
        self.assertEqual(result["compliance"]["post_answer"], "compliant")
        self.assertTrue(result["compliance"]["outcome_changed"])

    def test_wording_only_change_does_not_become_material_rule_change(self) -> None:
        result = analyze_legal_drift(
            "The company shall submit the form promptly.",
            "The company shall promptly submit the form.",
            "Must the company submit the form?",
        )
        self.assertTrue(result["classification"]["text_changed"])
        self.assertFalse(result["classification"]["legal_rule_changed"])
        self.assertEqual(result["classification"]["materiality"], "Low")
        self.assertIsNone(result["compliance"]["outcome_changed"])

    def test_identical_text_has_no_drift(self) -> None:
        result = analyze_legal_drift(
            "A company shall file the return.",
            "A company shall file the return.",
            "Must the company file the return?",
        )
        self.assertFalse(result["classification"]["text_changed"])
        self.assertEqual(result["classification"]["materiality"], "None")
        self.assertEqual(result["metrics"]["drift_score"], 0)

    def test_section_19_signature_scope_change_updates_compliance_answer(self) -> None:
        consolidated = (
            "THE INFORMATION TECHNOLOGY ACT, 2000 ARRANGEMENT OF SECTIONS. "
            "19. Recognition of foreign Certifying Authorities. "
            "(2) Where any Certifying Authority is recognised under sub-section (1), "
            "the 2[electronic signature] Certificate issued by such Certifying Authority "
            "shall be valid for the purposes of this Act. "
            "2. Subs. by s. 2, ibid., for ―Digital Signature‖ (w.e.f. 27-10-2009)."
        )
        amendment = (
            "INFORMATION TECHNOLOGY (AMENDMENT) ACT, 2008. AMENDMENTS TO THE "
            "INFORMATION TECHNOLOGY ACT, 2000. For the words \"digital signature\", "
            "the words \"electronic signature\" shall be substituted in section 19."
        )
        result = analyze_legal_drift(
            consolidated,
            amendment,
            "Under section 19(2), is the electronic signature Certificate valid?",
            "The recognised foreign Certifying Authority issued a certificate using a "
            "legally recognised electronic-signature technique that is not a digital-signature technique.",
        )
        self.assertTrue(result["temporal_interpretation"]["evidence_order_corrected"])
        self.assertEqual(result["compliance"]["pre_answer"], "non_compliant")
        self.assertEqual(result["compliance"]["post_answer"], "compliant")
        self.assertTrue(result["compliance"]["outcome_changed"])
        self.assertIn("Digital Signature", result["evidence"]["before"][0])
        self.assertIn("electronic signature", result["evidence"]["after"][0])


if __name__ == "__main__":
    unittest.main()
