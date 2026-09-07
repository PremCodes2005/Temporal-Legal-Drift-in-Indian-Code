from __future__ import annotations

import unittest
from hashlib import sha256

from temporal_legal_drift.versioning.builder import _dedupe_by_number
from temporal_legal_drift.versioning.extract import ExtractedProvision, extract_provisions
from temporal_legal_drift.versioning.models import (
    AmendmentEvent,
    EvidenceReference,
    LegalInstrument,
    ProvisionLineage,
    ProvisionVersion,
    VersionGraph,
    VersionTransition,
)


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

    def test_builder_dedupes_repeated_clause_numbers_instead_of_crashing(self) -> None:
        # The amending-clause fallback can yield two provisions with the same
        # number; the builder must collapse them (longest text wins) and escalate
        # the rest so the graph's lineage-id uniqueness invariant still holds.
        provisions = (
            ExtractedProvision("1", "Short title", "1. Short title.", "blk_1", "pdf:page:1:line:1"),
            ExtractedProvision("2", "Amendment of section 4", "2. Longer amending clause text.", "blk_1", "pdf:page:1:line:5"),
            ExtractedProvision("1", "Short title", "1. Short title. This Act may be called ...", "blk_2", "pdf:page:3:line:2"),
        )
        deduped, collisions = _dedupe_by_number(provisions)
        self.assertEqual([item.number for item in deduped], ["1", "2"])
        self.assertIn("This Act may be called", deduped[0].exact_text)
        self.assertEqual(collisions[0]["reason_code"], "duplicate_section_candidates")
        self.assertEqual(collisions[0]["provision_number"], "1")

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


if __name__ == "__main__":
    unittest.main()
