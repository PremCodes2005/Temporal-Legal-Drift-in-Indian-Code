from __future__ import annotations

import unittest
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.benchmark import build_technical_release
from temporal_legal_drift.jsonio import load_json
from temporal_legal_drift.materiality import build_annotation_workload
from temporal_legal_drift.scenarios import build_scenario_scaffolds
from temporal_legal_drift.versioning.models import (
    AmendmentEvent,
    EvidenceReference,
    LegalInstrument,
    ProvisionLineage,
    ProvisionVersion,
    VersionGraph,
)


ROOT = Path(__file__).resolve().parents[2]


class PhaseFiveToSevenTests(unittest.TestCase):
    def _foundation(self):  # type: ignore[no-untyped-def]
        instruction = "In section 3, for old words, new words shall be substituted."
        after = "3. Test.—New words. Subs. by Act 10 of 2009 (w.e.f. 27-10-2009)."
        instruction_hash = sha256(instruction.encode()).hexdigest()
        after_hash = sha256(after.encode()).hexdigest()
        amendment_evidence = EvidenceReference(
            "artifact-a", "a" * 64, "doc-a", "block-a", "page:1", instruction_hash
        )
        after_evidence = EvidenceReference(
            "artifact-b", "b" * 64, "doc-b", "block-b", "page:2", after_hash
        )
        graph = VersionGraph(
            instruments=(
                LegalInstrument("ins-a", "amendment", "Act:10/2009", "amending_act", "A", "artifact-a"),
                LegalInstrument("ins-b", "target", "Act:21/2000", "central_act", "B", "artifact-b"),
            ),
            lineages=(
                ProvisionLineage("lin-a", "ins-a", "section:1", "1", "Amending clause"),
                ProvisionLineage("lin-b", "ins-b", "section:3", "3", "Test"),
            ),
            versions=(
                ProvisionVersion(
                    "ver-a", "lin-a", "source", instruction, instruction_hash, amendment_evidence
                ),
                ProvisionVersion("ver-b", "lin-b", "source", after, after_hash, after_evidence),
            ),
            amendment_events=(
                AmendmentEvent(
                    "amd-a",
                    "ins-a",
                    "lin-b",
                    "section:3",
                    "substitution",
                    amendment_evidence,
                    "candidate_target_linked_transition_unresolved",
                ),
            ),
        )
        cross = {
            "results": [
                {
                    "validation_id": "xval-a",
                    "amendment_event_id": "amd-a",
                    "status": "corroborated",
                    "evidence": {
                        "expected_effective_date": "2009-10-27",
                        "target_version_id": "ver-b",
                    },
                }
            ]
        }
        return graph, cross

    def test_non_gold_pipeline_preserves_missing_research_fields(self) -> None:
        graph, cross = self._foundation()
        taxonomy = load_json(ROOT / "configs" / "annotation" / "materiality_taxonomy.v1.json")
        coverage = load_json(ROOT / "configs" / "scenarios" / "coverage_requirements.v1.json")
        release_config = load_json(ROOT / "configs" / "benchmark" / "release.v1.json")

        workload = build_annotation_workload(graph, cross, taxonomy, pilot_size=1)
        scenarios = build_scenario_scaffolds(workload, cross, coverage)
        release = build_technical_release(workload, scenarios, graph, release_config)

        task = workload["tasks"][0]
        self.assertIsNone(task["before_text"])
        self.assertIsNone(task["materiality"]["label"])
        self.assertEqual(task["annotations"], [])
        scenario = scenarios["scenarios"][0]
        self.assertIsNone(scenario["legal_question"])
        self.assertIsNone(scenario["expected_change"])
        self.assertFalse(release["benchmark_frozen"])
        self.assertEqual(release["object_counts"]["gold_materiality_labels"], 0)
        self.assertEqual(len(release["split_strategies"]), 6)


if __name__ == "__main__":
    unittest.main()
