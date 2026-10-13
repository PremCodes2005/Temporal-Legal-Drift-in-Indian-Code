"""Text-quality gate on real Gazette PDFs: garbled Hindi is withheld and never reaches evidence use."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from temporal_legal_drift.parsing import text_quality
from temporal_legal_drift.parsing.text_quality import quarantine_document

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/text_quality"
FROZEN = json.loads((FIXTURES / "frozen_extraction.v1.json").read_text(encoding="utf-8"))["documents"]
MSMED = "egazette-CG-DL-E-12102026-277080.pdf"     # Hindi glyphs mapped to wrong code points
RAILWAYS = "egazette-CG-DL-E-10102026-277026.pdf"  # Hindi in a legacy KrutiDev-style font
CONTROL = "correct-unicode-hindi-control.pdf"      # correctly encoded Hindi; pypdf still drops vowel signs
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def frozen(name: str) -> dict:
    return {"blocks": FROZEN[name]["blocks"]}


def evidence_text(name: str) -> str:
    return "\n".join(block["normalized_text"] for block in quarantine_document(frozen(name))[0]["blocks"])


class RealGazettePdfTests(unittest.TestCase):
    def test_fixture_pdfs_match_their_recorded_hashes(self) -> None:
        for name, item in FROZEN.items():
            self.assertEqual(sha256((FIXTURES / name).read_bytes()).hexdigest(), item["sha256"], name)

    def test_unicode_garbled_hindi_is_withheld_and_english_kept(self) -> None:
        raw = "\n".join(block["normalized_text"] for block in FROZEN[MSMED]["blocks"])
        self.assertIn("अजधसूचना", raw)  # the defect: "अधिसूचना" (notification) extracted wrongly
        text = evidence_text(MSMED)
        self.assertIsNone(DEVANAGARI.search(text))
        for kept in ("S.O. 5575(E).— In exercise of the powers conferred", "(a) the 15th October, 2026 as the date on which",
                     "(b) the 15th December, 2026 as the date"):
            self.assertIn(kept, text)
        report = quarantine_document(frozen(MSMED))[1]
        self.assertEqual(report["by_reason"], {"DEVANAGARI_TEXT_LAYER_UNVERIFIED": 17})

    def test_legacy_font_mojibake_is_withheld_and_english_kept(self) -> None:
        text = evidence_text(RAILWAYS)
        for garbled in ("vf/klwpuk", "jsyos", "¼", "fQjkstiqj", "rkfydk", "fuekZ.k", "vf/kfu;e"):
            self.assertNotIn(garbled, text)
        self.assertIn("In exercise of the power conferred by clause 20 F (6) of section 2 of the Railway's", text)
        self.assertIn("Kapurthala Punjab Construction of Limited Height", text)

    def test_correctly_encoded_hindi_is_withheld_because_the_text_layer_is_lossy(self) -> None:
        raw = "\n".join(block["normalized_text"] for block in FROZEN[CONTROL]["blocks"])
        source = (FIXTURES / "correct-unicode-hindi-control.html").read_text(encoding="utf-8")
        self.assertIn("अधिसूचना", source)
        self.assertNotIn("अधिसूचना", raw)  # pypdf dropped the vowel sign from a correct PDF
        text = evidence_text(CONTROL)
        self.assertIsNone(DEVANAGARI.search(text))
        self.assertIn("In exercise of the powers conferred by sub-section (2) of section 1", text)

    def test_line_numbers_are_preserved_for_provenance(self) -> None:
        evidence = quarantine_document(frozen(MSMED))[0]
        for before, after in zip(FROZEN[MSMED]["blocks"], evidence["blocks"]):
            self.assertEqual(before["normalized_text"].count("\n"), after["normalized_text"].count("\n"))

    def test_live_pypdf_extraction_matches_the_frozen_fixture(self) -> None:
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf not installed")
        from temporal_legal_drift.parsing.models import ParseContext
        from temporal_legal_drift.parsing.pdf import PdfParser

        for name, item in FROZEN.items():
            payload = (FIXTURES / name).read_bytes()
            parsed = PdfParser().parse(payload, ParseContext(name, item["sha256"], "application/pdf", name)).to_dict()
            self.assertEqual([b["normalized_text"] for b in parsed["blocks"]], [b["normalized_text"] for b in item["blocks"]], name)


class CorpusFalsePositiveTests(unittest.TestCase):
    """Frozen normalized corpus (restored release input): English statutory text must survive the gate."""

    def test_english_text_survives_and_known_garbage_is_withheld(self) -> None:
        paths = sorted((ROOT / "data/normalized").glob("doc_*.json"))
        if not paths:
            self.skipTest("frozen normalized corpus not restored (run tldrift restore-release-inputs)")
        counts: dict[str, int] = {}
        kept = []
        for path in paths:
            evidence, report = quarantine_document(json.loads(path.read_text(encoding="utf-8")))
            for reason, number in report["by_reason"].items():
                counts[reason] = counts.get(reason, 0) + number
            kept.append("\n".join(block["normalized_text"] for block in evidence["blocks"]))
        corpus = "\n".join(kept)
        # Measured 2026-10-13 over 245,761 lines; any change must be re-reviewed line by line.
        self.assertEqual(counts, {"LEGACY_FONT_MOJIBAKE": 140, "UNRECOGNISED_ON_MOJIBAKE_PAGE": 123,
                                  "DEVANAGARI_TEXT_LAYER_UNVERIFIED": 15})
        for line in ("Profit/Loss (-) brought forward", "“Court” means", "Short title", "150 g/m2 or less:",
                     "(Legislative Department)", "G r a n u l e s o f n a t u r a l"):
            self.assertIn(line, corpus)
        for garbage in ("izkf/kdkj ls izdkf'kr", "jftLVªh", "sect~on"):
            self.assertNotIn(garbage, corpus)


class VocabularyTests(unittest.TestCase):
    def test_a_modified_vocabulary_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "english_vocabulary.v1.txt"
            fake.write_text("rkfydk\n", encoding="utf-8")
            text_quality.english_vocabulary.cache_clear()
            try:
                with patch.object(text_quality, "VOCABULARY_PATH", fake), self.assertRaises(ValueError):
                    text_quality.english_vocabulary()
            finally:
                text_quality.english_vocabulary.cache_clear()


class EvidenceUseTests(unittest.TestCase):
    """Withheld lines never reach extraction, the monitored index or an answer without a warning."""

    def test_garbled_gazette_reaches_index_without_withheld_lines_and_answers_warn(self) -> None:
        from temporal_legal_drift.monitoring import MonitoringService
        from temporal_legal_drift.rag.rag_pipeline import RagPipeline
        from temporal_legal_drift.rag.retriever import HybridRetriever, update_monitored_overlay
        from unit.test_monitoring import Clock, FakeConnector, record

        class FrozenParser:
            name, version = "frozen-pypdf", "1"

            def parse(self, payload, context):
                return type("Doc", (), {"to_dict": staticmethod(lambda: {"blocks": FROZEN[MSMED]["blocks"]})})()

        with tempfile.TemporaryDirectory() as directory, \
                patch.object(HybridRetriever, "_active_version", return_value={"rag_index_version": "t"}), \
                patch.object(HybridRetriever, "ensure_index", return_value={"index_identity": "base-1"}):
            root = Path(directory)
            gazette = FakeConnector()
            url = "https://egazette.gov.in/WriteReadData/2026/277080.pdf"
            gazette.records = [record("egazette", "CG-DL-E-12102026-277080", "2026-10-12T00:00:00Z", url)]
            gazette.payloads[url] = (FIXTURES / MSMED).read_bytes()
            service = MonitoringService(root, {"egazette": gazette}, clock=Clock("2026-10-12T00:00:00+00:00"),
                                        parser=FrozenParser(), index_updater=update_monitored_overlay,
                                        graph_mapper=lambda event: {"status": "TARGET_UNRESOLVED"})
            result = service.run_due("t")[0]["records"][0]
            self.assertEqual(result["stages"]["text_fidelity"]["quarantine"]["withheld_lines"], 17)
            stored = list((root / "data/monitoring/quarantine").glob("*.json"))
            self.assertEqual(len(stored), 1)
            self.assertEqual(json.loads(stored[0].read_text())["sha256"], FROZEN[MSMED]["sha256"])
            chunks = HybridRetriever(root)._overlay_chunks()
            self.assertTrue(chunks)
            self.assertFalse(any(DEVANAGARI.search(chunk["text"]) for chunk in chunks))
            page_one = next(chunk for chunk in chunks if chunk["metadata"]["source_anchor"] == "pdf:page:1")
            self.assertEqual(page_one["metadata"]["quarantined_lines_on_page"], 17)

        from temporal_legal_drift.rag.retriever import RetrievedChunk

        pipeline = RagPipeline.__new__(RagPipeline)
        pipeline.root = ROOT
        warnings = pipeline._source_fidelity_warnings(RetrievedChunk("c", "text", 1, 1, 1, page_one["metadata"]))
        self.assertEqual([w["warning"] for w in warnings], ["source text partly withheld"])


if __name__ == "__main__":
    unittest.main()
