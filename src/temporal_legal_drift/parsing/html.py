"""HTML parser that preserves extracted blocks and structural heading paths."""

from __future__ import annotations

from html.parser import HTMLParser

from temporal_legal_drift.errors import ParseError

from .models import (
    NormalizedBlock,
    NormalizedDocument,
    ParseContext,
    make_block_id,
    make_document_id,
)
from .normalize import normalize_block_text


BLOCK_TAGS = {"title", "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th"}
IGNORED_TAGS = {"script", "style", "noscript"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.current_tag: str | None = None
        self.current_text: list[str] = []
        self.records: list[tuple[str, str, str]] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self.stack.append(tag)
        if tag in IGNORED_TAGS:
            self.ignored_depth += 1
        if self.ignored_depth == 0 and tag in BLOCK_TAGS and self.current_tag is None:
            self.current_tag = tag
            self.current_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.ignored_depth == 0 and self.current_tag == tag:
            raw = "".join(self.current_text)
            self.records.append((tag, raw, f"html:{tag}:{len(self.records)}"))
            self.current_tag = None
            self.current_text = []
        if tag in IGNORED_TAGS and self.ignored_depth:
            self.ignored_depth -= 1
        if tag in self.stack:
            reverse_index = self.stack[::-1].index(tag)
            del self.stack[len(self.stack) - reverse_index - 1 :]

    def handle_data(self, data: str) -> None:
        if self.ignored_depth == 0 and self.current_tag is not None:
            self.current_text.append(data)


class HtmlParser:
    name = "html"
    version = "1.0.0"

    def parse(self, payload: bytes, context: ParseContext) -> NormalizedDocument:
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ParseError("HTML input is not valid UTF-8") from error

        extractor = _Extractor()
        try:
            extractor.feed(text)
            extractor.close()
        except Exception as error:  # HTMLParser exposes several parse-time ValueErrors
            raise ParseError(f"Malformed HTML: {error}") from error

        blocks: list[NormalizedBlock] = []
        headings: dict[int, str] = {}
        for tag, raw, anchor in extractor.records:
            normalized = normalize_block_text(raw)
            if not normalized:
                continue
            if tag == "title":
                block_type = "title"
            elif tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
                block_type = "heading"
                level = int(tag[1])
                headings = {key: value for key, value in headings.items() if key < level}
                headings[level] = normalized
            elif tag == "li":
                block_type = "list_item"
            elif tag in {"td", "th"}:
                block_type = "table_text"
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
                    structural_path=tuple(value for _, value in sorted(headings.items())),
                    source_anchor=anchor,
                )
            )

        if not blocks and payload:
            raise ParseError("HTML input contains no supported text blocks")
        return NormalizedDocument(
            normalized_document_id=make_document_id(context.source_sha256, self.name, self.version),
            source_artifact_id=context.source_artifact_id,
            source_sha256=context.source_sha256,
            parser_name=self.name,
            parser_version=self.version,
            media_type=context.media_type,
            encoding="utf-8",
            blocks=tuple(blocks),
            transformations=(
                "html_text_extraction",
                "script_style_exclusion",
                "unicode_nfc",
                "inline_whitespace_collapse",
            ),
        )

