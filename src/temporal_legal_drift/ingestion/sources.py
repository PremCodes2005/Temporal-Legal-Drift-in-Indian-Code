"""Versioned registry contracts for authoritative Indian legal sources."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from temporal_legal_drift.jsonio import load_json


DATE_RE = re.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")
SOURCE_STATUSES = {"REGISTERED", "DISCOVERED", "DISABLED"}


@dataclass(frozen=True)
class LegalSource:
    source_id: str
    source_type: str
    authority: str
    title: str
    url: str
    publication_date: str | None
    publication_date_precision: str = "unknown"
    retrieved_at: str | None = None
    document_hash: str | None = None
    mime_type: str | None = None
    status: str = "REGISTERED"

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.source_type.strip():
            raise ValueError("source_id and source_type are required")
        if not self.authority.strip() or not self.title.strip():
            raise ValueError("authority and title are required")
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("legal source URL must be an absolute HTTPS URL")
        if self.publication_date is not None and not DATE_RE.fullmatch(self.publication_date):
            raise ValueError("publication_date must be YYYY, YYYY-MM, YYYY-MM-DD, or null")
        if self.status not in SOURCE_STATUSES:
            raise ValueError(f"unsupported legal source status: {self.status}")
        if self.document_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", self.document_hash):
            raise ValueError("document_hash must be a lowercase SHA-256 digest")

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "LegalSource":
        return cls(
            source_id=str(value["source_id"]),
            source_type=str(value["source_type"]),
            authority=str(value["authority"]),
            title=str(value["title"]),
            url=str(value["url"]),
            publication_date=str(value["publication_date"])
            if value.get("publication_date") is not None else None,
            publication_date_precision=str(value.get("publication_date_precision", "unknown")),
            retrieved_at=str(value["retrieved_at"])
            if value.get("retrieved_at") is not None else None,
            document_hash=str(value["document_hash"])
            if value.get("document_hash") is not None else None,
            mime_type=str(value["mime_type"])
            if value.get("mime_type") is not None else None,
            status=str(value.get("status", "REGISTERED")),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRegistry:
    registry_id: str
    schema_version: str
    sources: tuple[LegalSource, ...]

    @classmethod
    def from_file(cls, path: Path) -> "SourceRegistry":
        value = load_json(path)
        raw_sources = value.get("sources")
        if not isinstance(raw_sources, list) or not raw_sources:
            raise ValueError("source registry requires a non-empty sources array")
        sources = tuple(
            LegalSource.from_dict(item) for item in raw_sources if isinstance(item, dict)
        )
        if len(sources) != len(raw_sources):
            raise ValueError("every source registry entry must be an object")
        source_ids = [item.source_id for item in sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source registry source_id values must be unique")
        return cls(str(value["registry_id"]), str(value["schema_version"]), sources)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "registry_id": self.registry_id,
            "sources": [source.to_dict() for source in self.sources],
        }
