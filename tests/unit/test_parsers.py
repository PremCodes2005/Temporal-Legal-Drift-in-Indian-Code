from __future__ import annotations

import unittest
from hashlib import sha256

from temporal_legal_drift.errors import ParseError
from temporal_legal_drift.parsing.html import HtmlParser
from temporal_legal_drift.parsing.models import ParseContext
from temporal_legal_drift.parsing.plain_text import PlainTextParser
from temporal_legal_drift.parsing.xml import XmlParser


def context(payload: bytes, media_type: str, filename: str) -> ParseContext:
    return ParseContext("src_fixture", sha256(payload).hexdigest(), media_type, filename)


class ParserTests(unittest.TestCase):
    def test_plain_text_parser_is_deterministic_and_preserves_raw_blocks(self) -> None:
        payload = b"SECTION 1  Short title\r\n\r\nA  legal\tparagraph.\r\n\r\n(a) First item"
        parser = PlainTextParser()
        first = parser.parse(payload, context(payload, "text/plain", "source.txt"))
        second = parser.parse(payload, context(payload, "text/plain", "source.txt"))
        self.assertEqual(first, second)
        self.assertEqual([block.block_type for block in first.blocks], ["heading", "paragraph", "list_item"])
        self.assertEqual(first.blocks[1].raw_text, "A  legal\tparagraph.")
        self.assertEqual(first.blocks[1].normalized_text, "A legal paragraph.")
        self.assertEqual(first.blocks[1].structural_path, ("SECTION 1 Short title",))

    def test_html_parser_tracks_heading_path_and_ignores_scripts(self) -> None:
        payload = (
            b"<html><head><title>Act title</title><script>ignore()</script></head>"
            b"<body><h1>Chapter I</h1><p>First <b>provision</b>.</p>"
            b"<h2>Section 1</h2><p>Second provision.</p></body></html>"
        )
        document = HtmlParser().parse(payload, context(payload, "text/html", "source.html"))
        texts = [block.normalized_text for block in document.blocks]
        self.assertNotIn("ignore()", texts)
        self.assertIn("First provision.", texts)
        second = next(block for block in document.blocks if block.normalized_text == "Second provision.")
        self.assertEqual(second.structural_path, ("Chapter I", "Section 1"))

    def test_xml_parser_rejects_doctype_and_entities(self) -> None:
        payload = b'<!DOCTYPE law [<!ENTITY x "unsafe">]><law>&x;</law>'
        with self.assertRaises(ParseError):
            XmlParser().parse(payload, context(payload, "application/xml", "law.xml"))

    def test_xml_parser_extracts_leaf_text_with_source_path(self) -> None:
        payload = b"<act><section id='1'><title>Section 1</title><p>Legal text.</p></section></act>"
        document = XmlParser().parse(payload, context(payload, "application/xml", "law.xml"))
        self.assertTrue(any(block.normalized_text == "Section 1" for block in document.blocks))
        paragraph = next(block for block in document.blocks if block.normalized_text == "Legal text.")
        self.assertEqual(paragraph.source_anchor, "xml:/act/section/p")


if __name__ == "__main__":
    unittest.main()

