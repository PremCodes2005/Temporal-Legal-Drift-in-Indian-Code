from __future__ import annotations

import unittest
from datetime import date
from hashlib import sha256

from temporal_legal_drift.applicability.cross_validation import (
    validate_cross_source_consistency,
)
from temporal_legal_drift.applicability.models import TemporalFact
from temporal_legal_drift.versioning.models import (
    AmendmentEvent,
    EvidenceReference,
    LegalInstrument,
    ProvisionLineage,
    ProvisionVersion,
    VersionGraph,
)


class CrossSourceValidationTests(unittest.TestCase):
    def test_distinct_amendment_target_and_date_evidence_are_corroborated(self) -> None:
        amendment_evidence = EvidenceReference("artifact-amendment", "a" * 64, "doc-a", "b1", "p1", "c" * 64)
        target_text = "3. Test.—Current text. Subs. by Act 10 of 2009 (w.e.f. 27-10-2009)."
        target_evidence = EvidenceReference(
            "artifact-target",
            "d" * 64,
            "doc-b",
            "b2",
            "p2",
            sha256(target_text.encode()).hexdigest(),
        )
        graph = VersionGraph(
            instruments=(
                LegalInstrument("ins-a", "amending", "A", "amending_act", "A", "artifact-amendment"),
                LegalInstrument("ins-b", "target", "B", "central_act", "B", "artifact-target"),
            ),
            lineages=(ProvisionLineage("lin-3", "ins-b", "section:3", "3", "Test"),),
            versions=(
                ProvisionVersion(
                    "ver-3",
                    "lin-3",
                    "consolidated_source_snapshot",
                    target_text,
                    sha256(target_text.encode()).hexdigest(),
                    target_evidence,
                ),
            ),
            amendment_events=(
                AmendmentEvent(
                    "amd-1",
                    "ins-a",
                    "lin-3",
                    "section:3",
                    "substitution",
                    amendment_evidence,
                    "candidate_target_linked_transition_unresolved",
                ),
            ),
        )
        facts = (
            TemporalFact(
                "fact-1",
                "commencement",
                "ver-3",
                "27-10-2009",
                date(2009, 10, 27),
                "artifact-target",
                "p2:line:1",
                "unreviewed",
            ),
        )
        config = {
            "relations": [
                {
                    "relation_id": "relation-1",
                    "amending_entry_id": "amending",
                    "target_entry_id": "target",
                    "amending_act_citation_regex": r"(?:Act\s+)?10\s+of\s+2009",
                    "effective_date": "2009-10-27",
                    "effective_date_text_regex": "27-10-2009",
                    "operation_cues": {"substitution": r"\bSubs\."},
                    "minimum_corroborated_events_for_technical_gate": 1,
                }
            ]
        }

        result = validate_cross_source_consistency(graph, facts, config)

        self.assertEqual(result["results"][0]["status"], "corroborated")
        self.assertTrue(result["relation_summaries"][0]["technical_threshold_passed"])
        self.assertEqual(facts[0].review_status, "unreviewed")


if __name__ == "__main__":
    unittest.main()
