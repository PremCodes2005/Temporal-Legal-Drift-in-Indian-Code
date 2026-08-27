"""Strict corpus-manifest loading without implying legal sufficiency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from temporal_legal_drift.acquisition.models import SourceRequest
from temporal_legal_drift.jsonio import load_json


@dataclass(frozen=True)
class CorpusEntry:
    entry_id: str
    url: str
    parent_reference_url: str
    official_identifier: str
    instrument_type: str
    expected_media_type: str
    research_role: str
    known_extraction_risk: str | None = None

    def to_request(self) -> SourceRequest:
        return SourceRequest(
            url=self.url,
            official_identifier=self.official_identifier,
            instrument_type=self.instrument_type,
            notes=self.research_role,
            corpus_entry_id=self.entry_id,
            parent_reference_url=self.parent_reference_url,
            expected_media_type=self.expected_media_type,
        )


@dataclass(frozen=True)
class CorpusManifest:
    schema_version: str
    manifest_id: str
    status: str
    description: str
    entries: tuple[CorpusEntry, ...]

    @classmethod
    def from_file(cls, path: Path) -> "CorpusManifest":
        value = load_json(path)
        raw_entries = value.get("entries")
        if not isinstance(raw_entries, list) or not raw_entries:
            raise ValueError("Corpus manifest must contain at least one entry")
        entries = tuple(CorpusEntry(**entry) for entry in raw_entries)
        manifest = cls(
            schema_version=str(value["schema_version"]),
            manifest_id=str(value["manifest_id"]),
            status=str(value["status"]),
            description=str(value["description"]),
            entries=entries,
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if self.schema_version != "1.0.0":
            raise ValueError(f"Unsupported corpus manifest schema: {self.schema_version}")
        if self.status != "bounded_technical_pilot_not_legal_gold":
            raise ValueError("Pilot manifest must state that it is not legal gold")
        entry_ids = [entry.entry_id for entry in self.entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("Corpus entry IDs must be unique")
        for entry in self.entries:
            for label, url in (("url", entry.url), ("parent_reference_url", entry.parent_reference_url)):
                parsed = urlparse(url)
                if parsed.scheme != "https" or not parsed.hostname:
                    raise ValueError(f"{entry.entry_id} has invalid {label}: {url}")
            if entry.expected_media_type != "application/pdf":
                raise ValueError(
                    f"Pilot entry {entry.entry_id} must explicitly expect application/pdf"
                )
