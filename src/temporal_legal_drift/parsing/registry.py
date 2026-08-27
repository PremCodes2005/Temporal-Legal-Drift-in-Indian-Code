"""Media-type and filename based parser selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from temporal_legal_drift.errors import UnsupportedFormatError

from .html import HtmlParser
from .models import NormalizedDocument, ParseContext
from .pdf import PdfParser
from .plain_text import PlainTextParser
from .xml import XmlParser


class Parser(Protocol):
    name: str
    version: str

    def parse(self, payload: bytes, context: ParseContext) -> NormalizedDocument: ...


@dataclass
class ParserRegistry:
    by_media_type: dict[str, Parser] = field(default_factory=dict)
    by_suffix: dict[str, Parser] = field(default_factory=dict)

    def register(
        self,
        parser: Parser,
        *,
        media_types: tuple[str, ...] = (),
        suffixes: tuple[str, ...] = (),
    ) -> None:
        for media_type in media_types:
            self.by_media_type[media_type.lower()] = parser
        for suffix in suffixes:
            self.by_suffix[suffix.lower()] = parser

    def select(self, media_type: str, filename: str) -> Parser:
        normalized_media = media_type.split(";", 1)[0].strip().lower()
        if normalized_media in self.by_media_type:
            return self.by_media_type[normalized_media]
        suffix = Path(filename).suffix.lower()
        if suffix in self.by_suffix:
            return self.by_suffix[suffix]
        raise UnsupportedFormatError(
            f"No parser registered for media type {media_type!r} or suffix {suffix!r}"
        )


def default_registry() -> ParserRegistry:
    registry = ParserRegistry()
    registry.register(PlainTextParser(), media_types=("text/plain",), suffixes=(".txt", ".md"))
    registry.register(HtmlParser(), media_types=("text/html", "application/xhtml+xml"), suffixes=(".html", ".htm"))
    registry.register(XmlParser(), media_types=("application/xml", "text/xml"), suffixes=(".xml",))
    registry.register(PdfParser(), media_types=("application/pdf",), suffixes=(".pdf",))
    return registry

