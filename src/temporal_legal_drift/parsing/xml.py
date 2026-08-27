"""Conservative XML parser for structured legal-source text."""

from __future__ import annotations

from xml.etree import ElementTree

from temporal_legal_drift.errors import ParseError

from .models import (
    NormalizedBlock,
    NormalizedDocument,
    ParseContext,
    make_block_id,
    make_document_id,
)
from .normalize import normalize_block_text


class XmlParser:
    name = "xml"
    version = "1.0.0"

    def parse(self, payload: bytes, context: ParseContext) -> NormalizedDocument:
        upper = payload[:4096].upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise ParseError("XML document types and entity declarations are not accepted")
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as error:
            raise ParseError(f"Malformed XML: {error}") from error

        blocks: list[NormalizedBlock] = []

        def walk(element: ElementTree.Element, path: tuple[str, ...]) -> None:
            tag = element.tag.rsplit("}", 1)[-1]
            current_path = path + (tag,)
            raw = "".join(element.itertext())
            normalized = normalize_block_text(raw)
            direct_children = list(element)
            if normalized and (not direct_children or tag.lower() in {"title", "heading", "p", "paragraph"}):
                block_type = "heading" if tag.lower() in {"title", "heading"} else "paragraph"
                ordinal = len(blocks)
                blocks.append(
                    NormalizedBlock(
                        block_id=make_block_id(context.source_sha256, ordinal, raw),
                        ordinal=ordinal,
                        block_type=block_type,
                        raw_text=raw,
                        normalized_text=normalized,
                        structural_path=current_path,
                        source_anchor="xml:/" + "/".join(current_path),
                    )
                )
            for child in direct_children:
                walk(child, current_path)

        walk(root, ())
        if not blocks and payload:
            raise ParseError("XML input contains no usable text blocks")
        return NormalizedDocument(
            normalized_document_id=make_document_id(context.source_sha256, self.name, self.version),
            source_artifact_id=context.source_artifact_id,
            source_sha256=context.source_sha256,
            parser_name=self.name,
            parser_version=self.version,
            media_type=context.media_type,
            encoding="utf-8",
            blocks=tuple(blocks),
            transformations=("xml_itertext_extraction", "unicode_nfc", "inline_whitespace_collapse"),
        )
