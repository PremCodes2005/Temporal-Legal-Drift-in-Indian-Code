"""Deterministic plain-text structural parser."""

from __future__ import annotations

import re

from temporal_legal_drift.errors import ParseError

from .models import (
    NormalizedBlock,
    NormalizedDocument,
    ParseContext,
    make_block_id,
    make_document_id,
)
from .normalize import normalize_block_text, normalize_line_endings


HEADING_PATTERN = re.compile(
    r"^(?:CHAPTER|PART|SECTION|SCHEDULE|ANNEXURE|APPENDIX)\b|^\d+(?:\.\d+)*[.)]?\s+\S+",
    re.IGNORECASE,
)
LIST_PATTERN = re.compile(r"^(?:[-*•]|\([a-z0-9ivx]+\)|[a-z0-9ivx]+[.)])\s+", re.IGNORECASE)


class PlainTextParser:
    name = "plain_text"
    version = "1.0.0"

    def parse(self, payload: bytes, context: ParseContext) -> NormalizedDocument:
        try:
            decoded = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ParseError("Plain-text input is not valid UTF-8") from error

        decoded = normalize_line_endings(decoded)
        raw_blocks = re.split(r"\n\s*\n", decoded)
        blocks: list[NormalizedBlock] = []
        heading_path: list[str] = []

        for raw in raw_blocks:
            raw = raw.strip("\n")
            normalized = normalize_block_text(raw)
            if not normalized:
                continue
            first_line = normalized.split("\n", 1)[0]
            if HEADING_PATTERN.match(first_line):
                block_type = "heading"
                heading_path = [first_line]
            elif LIST_PATTERN.match(first_line):
                block_type = "list_item"
            else:
                block_type = "paragraph"
            ordinal = len(blocks)
            blocks.append(
                NormalizedBlock(
                    block_id=make_block_id(context.source_sha256, ordinal, raw),
                    ordinal=ordinal,
                    block_type=block_type,
                    raw_text=raw,
                    normalized_text=normalized,
                    structural_path=tuple(heading_path),
                    source_anchor=f"text:block:{ordinal}",
                )
            )

        if not blocks and payload:
            raise ParseError("Plain-text input contains no usable blocks")
        return NormalizedDocument(
            normalized_document_id=make_document_id(context.source_sha256, self.name, self.version),
            source_artifact_id=context.source_artifact_id,
            source_sha256=context.source_sha256,
            parser_name=self.name,
            parser_version=self.version,
            media_type=context.media_type,
            encoding="utf-8",
            blocks=tuple(blocks),
            transformations=("line_endings_to_lf", "unicode_nfc", "inline_whitespace_collapse"),
        )

