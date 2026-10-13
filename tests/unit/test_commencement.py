"""Commencement-notification policy: publication, commencement and applicability stay separate and unreviewed."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from temporal_legal_drift.applicability.models import ApplicabilityQuery, TemporalFact
from temporal_legal_drift.monitoring.commencement import extract_commencement, find_conflicts, is_commencement_subject
from temporal_legal_drift.parsing.text_quality import quarantine_document

ROOT = Path(__file__).resolve().parents[2]
FROZEN = json.loads((ROOT / "tests/fixtures/text_quality/frozen_extraction.v1.json").read_text(encoding="utf-8"))["documents"]
MSMED = FROZEN["egazette-CG-DL-E-12102026-277080.pdf"]


def msmed() -> dict:
    evidence = quarantine_document({"blocks": MSMED["blocks"]})[0]
    return extract_commencement(evidence, official_id="CG-DL-E-12102026-277080", sha256=MSMED["sha256"], published="2026-10-12")


def synthetic(text: str, official_id: str = "CG-DL-E-01012027-1", digest: str = "a" * 64) -> dict | None:
    return extract_commencement({"blocks": [{"source_anchor": "pdf:page:1", "normalized_text": text}]},
                                official_id=official_id, sha256=digest, published="2027-01-01")


ENABLING = ("S.O. 1(E).— In exercise of the powers conferred by sub-section (2) of section 1 of the Example (Amendment) "
            "Act, 2026 (9 of 2026), the Central Government hereby appoints ")


class DiscoveryTests(unittest.TestCase):
    def test_only_precise_commencement_subjects_are_selected(self) -> None:
        # Real e-Gazette "Bills & Acts" subjects observed 2026-10-12.
        self.assertTrue(is_commencement_subject("appointment of the date 15th October 2026 for MSMED Amendment Act 2026"))
        for subject in ("For publication in the Gazette of India under section 20A of Railways Amendment Act 2008 for Burhwal",
                        "Publication of a Notification under Section 3(1) of the Petroleum and Minerals Pipelines (ARUL) Act 1962",
                        "Publication of Notification in respect of construction of ROB in lieu of LC No 56 in terms of clause 20E"):
            self.assertFalse(is_commencement_subject(subject), subject)
        self.assertFalse(is_commencement_subject("appointment of the date for interviews"))  # no enactment named


class RealNotificationTests(unittest.TestCase):
    def test_each_appointed_date_is_a_separate_unreviewed_partial_commencement(self) -> None:
        record = msmed()
        commencement = [f for f in record["facts"] if f["fact_type"] != "publication"]
        self.assertEqual([(f["fact_type"], f["effective_date"]) for f in commencement],
                         [("partial_commencement", "2026-10-15"), ("partial_commencement", "2026-12-15")])
        self.assertEqual(commencement[0]["conditions"]["provisions"],
                         "the provisions of sections 2 to 7 (both inclusive), section 11 and sections 13 to 17 (both inclusive) of the said Act")
        self.assertEqual(commencement[1]["conditions"]["provisions"], "the provisions of section 12 of the said Act")
        for fact in commencement:
            self.assertEqual(fact["review_status"], "unreviewed")
            self.assertEqual(fact["conditions"]["act_number"], "16 of 2026")
            self.assertEqual(fact["conditions"]["notification"], "S.O. 5575(E)")
            self.assertEqual(fact["conditions"]["enabling_provision"], "sub-section (2) of section 1")

    def test_publication_commencement_and_applicability_stay_distinct(self) -> None:
        record = msmed()
        publication = [f for f in record["facts"] if f["fact_type"] == "publication"]
        self.assertEqual([(f["effective_date"], f["uncertainty"]) for f in publication], [("2026-10-12", "publication is not commencement")])
        self.assertEqual(record["applicability"]["status"], "NOT_DETERMINED")
        self.assertFalse(record["legal_effect_claimed"])
        self.assertIn("legal_effect", record["review_required_before"])

    def test_unreviewed_commencement_cannot_drive_the_applicability_resolver(self) -> None:
        from temporal_legal_drift.applicability import selfcheck
        from temporal_legal_drift.applicability.resolver import ApplicabilityResolver

        captured = {}
        original = ApplicabilityResolver.__init__

        def capture(self, graph, facts):
            captured["graph"] = graph
            original(self, graph, facts)

        ApplicabilityResolver.__init__ = capture
        try:
            selfcheck.run_resolver_self_check()
        finally:
            ApplicabilityResolver.__init__ = original
        facts = tuple(replace(TemporalFact.from_dict(f), version_id="ver_after") for f in msmed()["facts"])
        query = ApplicabilityQuery("s", "lin_fixture", date(2026, 11, 1))
        result = ApplicabilityResolver(captured["graph"], facts).resolve(query)
        self.assertEqual((result.status, result.governing_version_id, result.escalation_reasons),
                         ("unresolved_escalate", None, ("no_approved_temporal_evidence",)))
        # Control: once a reviewer approves, the facts are considered (and still escalate on their stated uncertainty).
        approved = tuple(replace(f, review_status="approved") for f in facts)
        self.assertNotIn("no_approved_temporal_evidence", ApplicabilityResolver(captured["graph"], approved).resolve(query).escalation_reasons)


class ConservativeExtractionTests(unittest.TestCase):
    def test_whole_act_commencement(self) -> None:
        record = synthetic(ENABLING + "the 1st day of April, 2027 as the date on which the said Act shall come into force.")
        self.assertEqual([(f["fact_type"], f["effective_date"]) for f in record["facts"] if f["fact_type"] != "publication"],
                         [("commencement", "2027-04-01")])

    def test_unparsed_wording_is_unresolved_with_verbatim_text_and_no_date(self) -> None:
        record = synthetic(ENABLING + "such date as may be notified later on which the said Act shall come into force.")
        self.assertEqual(record["status"], "UNRESOLVED")
        self.assertEqual([f["fact_type"] for f in record["facts"]], ["publication"])
        self.assertIn("as may be notified later", record["unresolved"][0]["verbatim"])

    def test_hindi_only_commencement_text_yields_nothing(self) -> None:
        hindi = "15 अक्तूबर, 2026 को ऐसी तारीख के रूप में नियत करती है जिसको उक्त अधिनियम प्रवृत्त होगा"
        evidence = quarantine_document({"blocks": [{"source_anchor": "pdf:page:1", "normalized_text": hindi}]})[0]
        self.assertIsNone(extract_commencement(evidence, official_id="x", sha256="b" * 64, published="2026-10-12"))

    def test_a_different_date_for_the_same_provisions_is_a_conflict(self) -> None:
        clause = "the {} as the date on which the provisions of section 3 of the said Act shall come into force."
        first = synthetic(ENABLING + clause.format("1st April, 2027"))
        second = synthetic(ENABLING + clause.format("1st May, 2027"), official_id="CG-DL-E-02012027-2", digest="c" * 64)
        self.assertEqual(find_conflicts(second, [first]), [{
            "official_id": "CG-DL-E-01012027-1", "act_number": "9 of 2026",
            "provisions": "the provisions of section 3 of the said act", "this_date": "2027-05-01", "other_date": "2027-04-01"}])
        self.assertEqual(find_conflicts(first, [first]), [])


class PipelineTests(unittest.TestCase):
    def test_monitoring_stores_a_write_once_record_pending_review(self) -> None:
        from temporal_legal_drift.monitoring import MonitoringService
        from unit.test_monitoring import Clock, FakeConnector, record

        class FrozenParser:
            name, version = "frozen-pypdf", "1"

            def parse(self, payload, context):
                return type("Doc", (), {"to_dict": staticmethod(lambda: {"blocks": MSMED["blocks"]})})()

        with tempfile.TemporaryDirectory() as directory:
            gazette = FakeConnector()
            url = "https://egazette.gov.in/WriteReadData/2026/277080.pdf"
            gazette.records = [record("egazette", "CG-DL-E-12102026-277080", "2026-10-12T00:00:00Z", url)]
            gazette.payloads[url] = (ROOT / "tests/fixtures/text_quality/egazette-CG-DL-E-12102026-277080.pdf").read_bytes()
            service = MonitoringService(Path(directory), {"egazette": gazette}, clock=Clock("2026-10-12T00:00:00+00:00"),
                                        parser=FrozenParser(), graph_mapper=lambda event: {"status": "TARGET_UNRESOLVED"})
            stages = service.run_due("t")[0]["records"][0]["stages"]
            self.assertEqual(stages["commencement"]["facts"], 2)
            self.assertFalse(stages["commencement"]["legal_effect_claimed"])
            self.assertEqual(stages["applicability"]["status"], "NOT_DETERMINED")
            self.assertEqual(service.health()["commencement_pending_review"], 1)
            self.assertEqual(service.commencement_records()[0]["status"], "MACHINE_EXTRACTED_PENDING_REVIEW")


if __name__ == "__main__":
    unittest.main()
