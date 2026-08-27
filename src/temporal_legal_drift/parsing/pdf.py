"""Optional PDF text extraction; scanned PDFs fail explicitly for later OCR."""

from __future__ import annotations

from io import BytesIO

from temporal_legal_drift.errors import ParseError, UnsupportedFormatError

from .models import (
    NormalizedBlock,
    NormalizedDocument,
    ParseContext,
    make_block_id,
    make_document_id,
)
from .normalize import normalize_block_text


class PdfParser:
    name = "pdf_pypdf"
    version = "1.0.0"

    def parse(self, payload: bytes, context: ParseContext) -> NormalizedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise UnsupportedFormatError(
                "PDF parsing requires the optional 'pdf' dependency: pip install -e '.[pdf]'"
            ) from error

        try:
            reader = PdfReader(BytesIO(payload), strict=True)
        except Exception as error:
            raise ParseError(f"Malformed or unsupported PDF: {error}") from error

        blocks: list[NormalizedBlock] = []
        warnings: list[str] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                raw = page.extract_text() or ""
            except Exception as error:
                raise ParseError(f"PDF page {page_number} text extraction failed: {error}") from error
            normalized = normalize_block_text(raw)
            if not normalized:
                warnings.append(f"page {page_number} contains no extractable text")
                continue
            ordinal = len(blocks)
            blocks.append(
                NormalizedBlock(
                    block_id=make_block_id(context.source_sha256, ordinal, raw),
                    ordinal=ordinal,
                    block_type="paragraph",
                    raw_text=raw,
                    normalized_text=normalized,
                    structural_path=(f"page:{page_number}",),
                    source_anchor=f"pdf:page:{page_number}",
                )
            )

        if not blocks:
            raise ParseError(
                "PDF contains no extractable text; retain the raw artifact and use a separately versioned OCR workflow"
            )
        return NormalizedDocument(
            normalized_document_id=make_document_id(context.source_sha256, self.name, self.version),
            source_artifact_id=context.source_artifact_id,
            source_sha256=context.source_sha256,
            parser_name=self.name,
            parser_version=self.version,
            media_type=context.media_type,
            encoding=None,
            blocks=tuple(blocks),
            transformations=("pypdf_text_extraction", "unicode_nfc", "inline_whitespace_collapse"),
            warnings=tuple(warnings),
        )

