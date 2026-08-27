"""Normalized-document data contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256


@dataclass(frozen=True)
class ParseContext:
    source_artifact_id: str
    source_sha256: str
    media_type: str
    filename: str


@dataclass(frozen=True)
class NormalizedBlock:
    block_id: str
    ordinal: int
    block_type: str
    raw_text: str
    normalized_text: str
    structural_path: tuple[str, ...]
    source_anchor: str

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["structural_path"] = list(self.structural_path)
        return value


@dataclass(frozen=True)
class NormalizedDocument:
    normalized_document_id: str
    source_artifact_id: str
    source_sha256: str
    parser_name: str
    parser_version: str
    media_type: str
    encoding: str | None
    blocks: tuple[NormalizedBlock, ...]
    transformations: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "normalized_document_id": self.normalized_document_id,
            "source_artifact_id": self.source_artifact_id,
            "source_sha256": self.source_sha256,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "media_type": self.media_type,
            "encoding": self.encoding,
            "blocks": [block.to_dict() for block in self.blocks],
            "transformations": list(self.transformations),
            "warnings": list(self.warnings),
        }


def make_block_id(source_hash: str, ordinal: int, raw_text: str) -> str:
    value = f"{source_hash}\n{ordinal}\n{raw_text}".encode("utf-8")
    return f"blk_{sha256(value).hexdigest()[:24]}"


def make_document_id(source_hash: str, parser_name: str, parser_version: str) -> str:
    value = f"{source_hash}\n{parser_name}\n{parser_version}".encode("utf-8")
    return f"doc_{sha256(value).hexdigest()[:24]}"

