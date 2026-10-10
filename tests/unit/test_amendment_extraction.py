from __future__ import annotations

import unittest
from pathlib import Path

from temporal_legal_drift.amendment_extraction import (
    AmendmentExtractionPipeline,
    GeneralisedAmendmentExtractor,
    build_silver_label,
    silver_metrics,
)
from temporal_legal_drift.amendment_extraction.models import UNRESOLVED_REASONS


ROOT = Path(__file__).resolve().parents[2]


class GeneralisedAmendmentExtractionTests(unittest.TestCase):
    def test_supported_operations_extract_wording_and_evidence(self) -> None:
        document = {"blocks": [{
            "block_id": "fixture",
            "source_anchor": "pdf:page:1",
            "normalized_text": """An Act to amend the Fixture Act, 2020.
1. This Act shall be deemed to have come into force on the 4th day of April, 2021.
2. In the Fixture Act, 2020, in section 5, for the words "ten days", the words "fifteen days" shall be substituted.
3. In section 6 of the principal Act, after the words "form", the words "electronic form" shall be inserted.
4. In section 7 of the principal Act, the words "obsolete text" shall be omitted.
5. In the principal Act, section 8 shall be renumbered as section 9.
""",
        }]}
        events, unresolved = GeneralisedAmendmentExtractor().extract(
            document,
            source_document="fixture-amendment-act",
            source_sha256="a" * 64,
            amending_act="Fixture Amendment Act",
        )
        by_target = {item.target_provision: item for item in events}
        self.assertEqual(set(by_target), {"section:5", "section:6", "section:7", "section:8"})
        self.assertEqual(by_target["section:5"].operation, "SUBSTITUTE")
        self.assertEqual(by_target["section:5"].old_text, "ten days")
        self.assertEqual(by_target["section:5"].new_text, "fifteen days")
        self.assertEqual(by_target["section:8"].operation, "RENUMBER")
        self.assertTrue(all(item.source_page == 1 and item.evidence_text for item in events))
        self.assertFalse(any(item.reason_code == "parsing_failure" for item in unresolved))

    def test_new_section_insert_extracts_outer_single_curly_payload_and_target(self) -> None:
        instruction = """An Act to amend the Fixture Act, 2020.
1. After section 31 of the principal Act, the following new section shall be inserted,
namely:—
‘31A. The Court shall determine the amount of “costs” payable.’."""
        events, unresolved = GeneralisedAmendmentExtractor().extract(
            {"blocks": [{"block_id": "x", "source_anchor": "pdf:page:1", "normalized_text": instruction}]},
            source_document="new-section-fixture", source_sha256="e" * 64, amending_act="Fixture Amendment Act",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].target_provision, "section:31A")
        self.assertEqual(events[0].operation, "INSERT")
        self.assertTrue(events[0].new_text.startswith("31A. The Court shall determine"))
        self.assertIn("“costs”", events[0].new_text)
        self.assertGreater(len(events[0].new_text), len("costs"))
        self.assertFalse(unresolved)

    def test_inserted_wording_across_pdf_line_break_selects_new_operand(self) -> None:
        instruction = """1. In the Fixture Act, 2020, in section 21, after the words "convertible into equity shares", the words
"or completion of such transactions as may be prescribed," shall be inserted."""
        events, unresolved = GeneralisedAmendmentExtractor().extract(
            {"blocks": [{"block_id": "x", "source_anchor": "pdf:page:1", "normalized_text": instruction}]},
            source_document="line-wrap-fixture", source_sha256="f" * 64, amending_act="Fixture Amendment Act",
        )
        self.assertEqual(events[0].new_text, "or completion of such transactions as may be prescribed,")
        self.assertFalse(unresolved)

    def test_compound_same_operation_clause_abstains_instead_of_selecting_one_operand(self) -> None:
        instruction = """1. In section 74,—
(i) the following proviso shall be inserted, namely: “first insertion”;
(ii) the following clause shall be inserted, namely: “second insertion.”"""
        events, unresolved = GeneralisedAmendmentExtractor().extract(
            {"blocks": [{"block_id": "x", "source_anchor": "pdf:page:1", "normalized_text": instruction}]},
            source_document="compound-fixture", source_sha256="1" * 64, amending_act="Fixture Amendment Act",
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].operation, "UNKNOWN")
        self.assertIsNone(events[0].new_text)
        self.assertTrue(any(item.reason_code == "unclear_operation" for item in unresolved))

    def test_inserted_new_section_with_alphabetic_number_targets_created_section(self) -> None:
        instruction = "An Act to amend the Fixture Act, 2020.\n1. After section 6, the following section shall be inserted, namely:— ‘6A. No shall apply.’"
        events, unresolved = GeneralisedAmendmentExtractor().extract(
            {"blocks": [{"block_id": "x", "source_anchor": "pdf:page:1", "normalized_text": instruction}]},
            source_document="section-a-fixture", source_sha256="2" * 64, amending_act="Fixture Amendment Act",
        )
        self.assertEqual(events[0].target_provision, "section:6A")
        self.assertEqual(events[0].new_text, "6A. No shall apply.")
        self.assertFalse(unresolved)

    def test_ascii_single_quote_new_section_does_not_select_inner_definition_quote(self) -> None:
        instruction = "An Act to amend the Fixture Act, 2020.\n1. After section 6, the following section shall be inserted, namely:— '6A. An open offer shall be filed.'"
        events, _ = GeneralisedAmendmentExtractor().extract(
            {"blocks": [{"block_id": "x", "source_anchor": "pdf:page:1", "normalized_text": instruction}]},
            source_document="ascii-quote-fixture", source_sha256="3" * 64, amending_act="Fixture Amendment Act",
        )
        self.assertEqual(events[0].target_provision, "section:6A")
        self.assertEqual(events[0].new_text, "6A. An open offer shall be filed.")

    def test_unresolved_records_use_only_canonical_reason_codes(self) -> None:
        document = {"blocks": [{
            "block_id": "ambiguous",
            "source_anchor": "pdf:page:4",
            "normalized_text": "2. Amendment of section 2 and section 3 shall be made.",
        }]}
        events, unresolved = GeneralisedAmendmentExtractor().extract(
            document,
            source_document="ambiguous-act",
            source_sha256="b" * 64,
            amending_act="Ambiguous Act",
        )
        self.assertEqual(len(events), 1)
        self.assertTrue(unresolved)
        self.assertTrue({item.reason_code for item in unresolved} <= UNRESOLVED_REASONS)
        self.assertTrue(all(item.evidence_text and item.review_status == "HUMAN_REVIEW_REQUIRED" for item in unresolved))

    def test_all_configured_amending_acts_are_accounted_for_without_fake_accuracy(self) -> None:
        result = AmendmentExtractionPipeline(ROOT).run()
        self.assertEqual(result["configured_amending_act_count"], 37)
        self.assertEqual(result["processed_amending_act_count"], 37)
        self.assertTrue(result["all_events_traceable"])
        self.assertTrue(result["every_document_accounted_for"])
        self.assertTrue(all(
            value is None
            for key, value in result["metrics"]["real_corpus_accuracy"].items()
            if key.endswith("_accuracy")
        ))

    def test_silver_labeller_accepts_only_independently_supported_fields(self) -> None:
        text = """An Act to amend the Fixture Act, 2020.
1. This Act shall be deemed to have come into force on the 4th day of April, 2021.
2. In the Fixture Act, 2020, in section 5, for the words "ten days", the words "fifteen days" shall be substituted.
"""
        document = {"blocks": [{
            "block_id": "silver-fixture",
            "source_anchor": "pdf:page:1",
            "normalized_text": text,
        }]}
        events, _ = GeneralisedAmendmentExtractor().extract(
            document,
            source_document="silver-fixture",
            source_sha256="c" * 64,
            amending_act="Fixture Amendment Act",
        )
        label = build_silver_label(events[0].to_dict(), text)
        self.assertEqual(label.label_status, "AUTO_ACCEPTED")
        self.assertEqual(label.confidence_tier, "HIGH")
        self.assertEqual(label.agreement_score, 1.0)
        self.assertTrue(all(label.validator_checks.values()))

    def test_silver_labeller_abstains_on_unsupported_operation(self) -> None:
        event = {
            "amendment_id": "amendment_fixture",
            "source_document": "fixture",
            "principal_act": "Fixture Act, 2020",
            "target_provision": "section:5",
            "operation": "INSERT",
            "old_text": None,
            "new_text": "invented text",
            "effective_date": None,
            "source_sha256": "d" * 64,
            "evidence_text": "2. In section 5, the provision shall be omitted.",
        }
        label = build_silver_label(event, "Fixture Act, 2020. " + event["evidence_text"])
        self.assertEqual(label.label_status, "ABSTAIN")
        self.assertEqual(label.confidence_tier, "ABSTAIN")
        self.assertIn("operation_rule_disagreement", label.abstention_reasons)
        metrics = silver_metrics([label.to_dict()])
        self.assertEqual(metrics["auto_label_coverage"]["percent"], 0.0)
        self.assertEqual(metrics["abstention_rate"]["percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
