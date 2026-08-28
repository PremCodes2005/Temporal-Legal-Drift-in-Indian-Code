from __future__ import annotations

import unittest
from datetime import date
from hashlib import sha256

from temporal_legal_drift.applicability import ApplicabilityQuery, ApplicabilityResolver, TemporalFact
from temporal_legal_drift.applicability.candidates import extract_temporal_candidates
from temporal_legal_drift.versioning.models import (
    AmendmentEvent,
    EvidenceReference,
    LegalInstrument,
    ProvisionLineage,
    ProvisionVersion,
    VersionGraph,
    VersionTransition,
)


class ApplicabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        evidence = EvidenceReference("src_1", "0" * 64, "doc_1", "blk_1", "page:1", "1" * 64)
        instrument = LegalInstrument("ins_1", "fixture", "fixture", "fixture", "Fixture", "src_1")
        lineage = ProvisionLineage("lin_1", "ins_1", "section:1", "1", "Duty")
        old_text, new_text = "1. Duty.—Old.", "1. Duty.—New."
        old = ProvisionVersion("ver_old", "lin_1", "old", old_text, sha256(old_text.encode()).hexdigest(), evidence)
        new = ProvisionVersion("ver_new", "lin_1", "new", new_text, sha256(new_text.encode()).hexdigest(), evidence)
        event = AmendmentEvent("amd_1", "ins_1", "lin_1", "section:1", "substitution", evidence, "fixture")
        transition = VersionTransition("trn_1", "ver_old", "ver_new", "amd_1", "substitution", evidence)
        self.graph = VersionGraph((instrument,), (lineage,), (old, new), (event,), (transition,))

    def fact(self, fact_id: str, fact_type: str, version: str, when: date | None, **kwargs):  # type: ignore[no-untyped-def]
        return TemporalFact(
            fact_id, fact_type, version, str(when), when, "src_1", f"page:{fact_id}", "approved", **kwargs
        )

    def test_resolver_selects_version_only_from_effective_evidence_and_transition(self) -> None:
        resolver = ApplicabilityResolver(
            self.graph,
            (
                self.fact("tmp_old", "commencement", "ver_old", date(2020, 1, 1)),
                self.fact("tmp_new", "commencement", "ver_new", date(2021, 1, 1)),
            ),
        )
        self.assertEqual(
            resolver.resolve(ApplicabilityQuery("s1", "lin_1", date(2020, 6, 1))).governing_version_id,
            "ver_old",
        )
        self.assertEqual(
            resolver.resolve(ApplicabilityQuery("s2", "lin_1", date(2021, 6, 1))).governing_version_id,
            "ver_new",
        )

    def test_publication_only_and_unreviewed_facts_remain_unresolved(self) -> None:
        publication = self.fact("tmp_pub", "publication", "ver_old", date(2020, 1, 1))
        result = ApplicabilityResolver(self.graph, (publication,)).resolve(
            ApplicabilityQuery("s1", "lin_1", date(2020, 6, 1))
        )
        self.assertEqual(result.status, "unresolved_escalate")
        unreviewed = TemporalFact(
            "tmp_unreviewed", "commencement", "ver_old", "2020-01-01", date(2020, 1, 1),
            "src_1", "page:1", "unreviewed"
        )
        self.assertEqual(
            ApplicabilityResolver(self.graph, (unreviewed,)).resolve(
                ApplicabilityQuery("s2", "lin_1", date(2020, 6, 1))
            ).status,
            "unresolved_escalate",
        )

    def test_partial_commencement_requires_scenario_attributes(self) -> None:
        partial = self.fact(
            "tmp_partial",
            "partial_commencement",
            "ver_old",
            date(2020, 1, 1),
            conditions={"territory": "X"},
        )
        resolver = ApplicabilityResolver(self.graph, (partial,))
        missing = resolver.resolve(ApplicabilityQuery("s1", "lin_1", date(2020, 6, 1)))
        matched = resolver.resolve(
            ApplicabilityQuery("s2", "lin_1", date(2020, 6, 1), {"territory": "X"})
        )
        self.assertEqual(missing.status, "unresolved_escalate")
        self.assertEqual(matched.governing_version_id, "ver_old")

    def test_conflicting_or_uncertain_approved_evidence_escalates(self) -> None:
        conflicting = ApplicabilityResolver(
            self.graph,
            (
                self.fact("tmp_one", "commencement", "ver_old", date(2020, 1, 1)),
                self.fact("tmp_two", "legal_effect", "ver_old", date(2020, 2, 1)),
            ),
        ).resolve(ApplicabilityQuery("s1", "lin_1", date(2020, 6, 1)))
        uncertain = self.fact(
            "tmp_uncertain",
            "commencement",
            "ver_old",
            date(2020, 1, 1),
            uncertainty="source conflict requires review",
        )
        uncertain_result = ApplicabilityResolver(self.graph, (uncertain,)).resolve(
            ApplicabilityQuery("s2", "lin_1", date(2020, 6, 1))
        )
        self.assertEqual(conflicting.status, "unresolved_escalate")
        self.assertEqual(uncertain_result.status, "unresolved_escalate")

    def test_real_corpus_candidate_extractor_never_auto_approves(self) -> None:
        old = self.graph.reconstruct("ver_old")
        dated_text = "1. Duty.—It shall come into force on 1 January 2020."
        dated = ProvisionVersion(
            old.version_id,
            old.lineage_id,
            old.version_label,
            dated_text,
            sha256(dated_text.encode()).hexdigest(),
            old.evidence,
        )
        graph = VersionGraph(
            self.graph.instruments,
            self.graph.lineages,
            (dated, self.graph.reconstruct("ver_new")),
            self.graph.amendment_events,
            self.graph.transitions,
        )
        candidates = extract_temporal_candidates(graph)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].fact_type, "commencement")
        self.assertEqual(candidates[0].review_status, "unreviewed")
        self.assertTrue(candidates[0].uncertainty)


if __name__ == "__main__":
    unittest.main()
