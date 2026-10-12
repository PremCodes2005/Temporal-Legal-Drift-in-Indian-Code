from __future__ import annotations

import unittest
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.versioning.extract import extract_amending_clauses, extract_provisions
from temporal_legal_drift.versioning.models import (
    AmendmentEvent,
    EvidenceReference,
    LegalInstrument,
    ProvisionLineage,
    ProvisionVersion,
    VersionGraph,
    VersionTransition,
)
from temporal_legal_drift.jsonio import load_json
from temporal_legal_drift.versioning.temporal_graph import TemporalGraph, TemporalGraphBuilder, _target_path_detail


ROOT = Path(__file__).resolve().parents[2]


class VersioningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = EvidenceReference(
            "src_fixture", "0" * 64, "doc_fixture", "blk_fixture", "fixture:1", "1" * 64
        )

    def test_section_extraction_is_stable_and_reports_duplicate_candidates(self) -> None:
        document = {
            "blocks": [
                {
                    "block_id": "blk_1",
                    "source_anchor": "pdf:page:1",
                    "normalized_text": "1. Scope.—Short.\n2. Duty.—A person shall comply.",
                },
                {
                    "block_id": "blk_2",
                    "source_anchor": "pdf:page:2",
                    "normalized_text": "1. Scope.—A longer duplicate candidate for review.",
                },
            ]
        }
        provisions, unresolved = extract_provisions(document)
        self.assertEqual([item.number for item in provisions], ["1", "2"])
        self.assertIn("longer duplicate", provisions[0].exact_text)
        self.assertEqual(unresolved[0]["reason_code"], "duplicate_section_candidates")

    def test_target_detail_does_not_parse_plural_clauses_as_clause_s(self) -> None:
        text = "31. In section 50, in sub-section (1), in clauses (a) and (c), after the words x, y shall be inserted."
        self.assertEqual(_target_path_detail(text), "section:50/sub-section:1")
        plural = "26. In section 4, after sub-section (2), the following sub-sections shall be inserted, in sub-sections (3) and (4)."
        self.assertEqual(_target_path_detail(plural), "section:4")

    def test_graph_reconstructs_exact_version_and_rejects_cycles(self) -> None:
        before_text = "1. Duty.—Before."
        after_text = "1. Duty.—After."
        before = ProvisionVersion(
            "ver_before", "lin_1", "before", before_text, sha256(before_text.encode()).hexdigest(), self.evidence
        )
        after = ProvisionVersion(
            "ver_after", "lin_1", "after", after_text, sha256(after_text.encode()).hexdigest(), self.evidence
        )
        instrument = LegalInstrument("ins_1", "fixture", "fixture", "fixture", "Fixture", "src_fixture")
        lineage = ProvisionLineage("lin_1", "ins_1", "section:1", "1", "Duty")
        event = AmendmentEvent("amd_1", "ins_1", "lin_1", "section:1", "substitution", self.evidence, "fixture")
        forward = VersionTransition("trn_1", "ver_before", "ver_after", "amd_1", "substitution", self.evidence)
        graph = VersionGraph((instrument,), (lineage,), (before, after), (event,), (forward,))
        self.assertEqual(graph.validate(), ())
        self.assertEqual(graph.reconstruct("ver_before").exact_text, before_text)
        backward = VersionTransition("trn_2", "ver_after", "ver_before", "amd_1", "substitution", self.evidence)
        cyclic = VersionGraph((instrument,), (lineage,), (before, after), (event,), (forward, backward))
        self.assertIn("version graph contains a cycle", cyclic.validate())

    def test_duplicate_amending_clauses_do_not_create_duplicate_lineages(self) -> None:
        document = {
            "blocks": [
                {
                    "block_id": "blk_1",
                    "source_anchor": "pdf:page:1",
                    "normalized_text": "2. In the principal Act, short amendment.",
                },
                {
                    "block_id": "blk_2",
                    "source_anchor": "pdf:page:2",
                    "normalized_text": "2. In the principal Act, a longer amendment instruction shall be substituted.",
                },
            ]
        }
        provisions = extract_amending_clauses(document)
        self.assertEqual(len(provisions), 1)
        self.assertIn("longer amendment", provisions[0].exact_text)


class TemporalKnowledgeGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = TemporalGraphBuilder().build(ROOT)

    def test_all_sources_events_and_entity_relationships_are_accounted_for(self) -> None:
        self.assertEqual(len(self.graph.legal_sources), 100)
        self.assertEqual(len(self.graph.amendment_acts), 37)
        self.assertEqual(len(self.graph.amendment_events), 864)
        self.assertEqual(len(self.graph.commencement_events), 864)
        self.assertGreaterEqual(len(self.graph.transitions), 20)
        self.assertTrue(self.graph.unresolved_transitions)
        self.assertEqual(self.graph.validate(), ())

    def test_point_in_time_query_selects_before_and_after_fragment(self) -> None:
        before = self.graph.get_provision_version(
            "arbitration-and-conciliation-act-1996", "7", "2015-01-01"
        )
        after = self.graph.get_provision_version(
            "arbitration-and-conciliation-act-1996", "7", "2016-01-01"
        )
        self.assertEqual(before["status"], "RESOLVED_FRAGMENT")
        self.assertEqual(before["version"]["text"], "")
        self.assertEqual(
            after["version"]["text"], "including communication through electronic means"
        )
        self.assertEqual(after["transition"]["effective_date"], "2015-10-23")
        self.assertEqual(
            after["temporal_basis"],
            "ACT_WIDE_COMMENCEMENT_NOT_SCENARIO_APPLICABILITY",
        )
        self.assertGreaterEqual(len(after["sources"]), 2)
        self.assertTrue(after["corroborating_consolidated_versions"])
        self.assertIn("not a complete historical consolidation", after["scope_warning"])

    def test_v3_never_reconstructs_unreliable_or_page_furniture_wording(self) -> None:
        graph = TemporalGraphBuilder().build(ROOT, "v3")
        self.assertEqual(graph.validate(), ())
        flagged = {
            item["amendment_event_id"]: item["source_fidelity_flags"]
            for item in graph.amendment_events if item["source_fidelity_flags"]
        }
        self.assertEqual(len(flagged), 49)  # 35 IT 2008 + 14 page-furniture operands
        self.assertFalse({item["amendment_event_id"] for item in graph.transitions} & set(flagged))
        for item in graph.unresolved_transitions:
            if item["amendment_event_id"] in flagged:
                self.assertTrue(set(flagged[item["amendment_event_id"]]) <= set(item["reason_codes"]))
        # Graph v2 answered this with the defective "costs" fragment (v1 extraction defect).
        result = graph.get_provision_version("arbitration-and-conciliation-act-1996", "31", "2016-01-01")
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertTrue(all(item["source_evidence"]["exact_text"] for item in result["unresolved_transitions"]))
        kept = graph.get_provision_version("arbitration-and-conciliation-act-1996", "7", "2016-01-01")
        self.assertEqual(kept["status"], "RESOLVED_FRAGMENT")
        self.assertEqual(kept["version"]["text_scope"], "AMENDMENT_CONTROLLED_FRAGMENT")

    def test_v4_short_fragment_policy_and_layout_cleaned_corroboration(self) -> None:
        from temporal_legal_drift.versioning.temporal_graph import _short_fragment_specific

        # Mere presence of "ten years" (old wording still present) is not specific corroboration.
        self.assertFalse(_short_fragment_specific("SUBSTITUTE", "three years", "ten years", "", ["three years or ten years"]))
        self.assertTrue(_short_fragment_specific("SUBSTITUTE", "three years", "ten years", "", ["for ten years"]))
        self.assertFalse(_short_fragment_specific("SUBSTITUTE", "x", "ten years", "", ["ten years and ten years"]))
        self.assertTrue(_short_fragment_specific(
            "INSERT", "", "or culture", 'after the words "art", the words "or culture" shall be inserted', ["art or culture"]))
        graph = TemporalGraph.from_dict(load_json(ROOT / "data/interim/temporal_legal_knowledge_graph.v4.json"))
        self.assertEqual(graph.validate(), ())
        events = {item["amendment_event_id"]: item for item in graph.amendment_events}
        for item in graph.transitions:
            event = events[item["amendment_event_id"]]
            self.assertFalse(event.get("source_fidelity_flags"))
            if event.get("layout_cleaning"):
                self.assertTrue(item["validation_checks"]["after_fragment_matches_consolidated_principal_act"])
            if item["validation_checks"].get("after_fragment_corroboration_specific") is False:
                self.assertEqual(item["validation_status"], "MACHINE_SHORT_FRAGMENT_MATCH_ONLY")

    def test_graph_consumer_contract_labels_scope_and_abstains(self) -> None:
        from temporal_legal_drift.versioning.consumer import GraphConsumer, IncompatibleGraphError

        consumer = GraphConsumer(ROOT, "v4")
        supported = consumer.provision_at("arbitration-and-conciliation-act-1996", "7", "2016-01-01")
        self.assertEqual(supported["status"], "FRAGMENT_SUPPORTED")
        self.assertEqual(supported["version_scope"], "AMENDMENT_CONTROLLED_FRAGMENT")
        self.assertFalse(supported["is_complete_consolidated_text"])
        self.assertEqual(supported["applicability_status"], "NOT_DETERMINED_REQUIRES_SCENARIO_FACTS_AND_REVIEW")
        self.assertEqual(supported["legal_validation"], "UNVERIFIED")
        self.assertTrue(supported["source_evidence"][0]["exact_text"] and supported["source_evidence"][0]["source_url"])
        unresolved = consumer.provision_at("arbitration-and-conciliation-act-1996", "31", "2016-01-01")
        self.assertEqual((unresolved["status"], unresolved["text"]), ("UNRESOLVED", None))
        self.assertTrue(unresolved["abstention_reasons"])
        missing = consumer.provision_at("arbitration-and-conciliation-act-1996", "9999", "2016-01-01")
        self.assertEqual(missing["status"], "UNRESOLVED")
        with self.assertRaises(IncompatibleGraphError):
            GraphConsumer(ROOT, "v2")

    def test_point_in_time_query_abstains_without_effective_date(self) -> None:
        result = self.graph.get_provision_version(
            "it-act-2000-consolidated", "19", "2010-01-01"
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertIn("effective date", result["reason"])


if __name__ == "__main__":
    unittest.main()
