"""Content-hash deduplication and source version lineage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeduplicationDecision:
    is_duplicate: bool
    version: int
    existing_document_id: str | None
    previous_document_id: str | None


class DocumentDeduplicator:
    def decide(
        self,
        source_id: str,
        content_hash: str,
        records: list[dict[str, object]],
    ) -> DeduplicationDecision:
        source_records = sorted(
            (item for item in records if item.get("source_id") == source_id),
            key=lambda item: int(item.get("version", 0)),
        )
        duplicate = next(
            (item for item in source_records if item.get("sha256") == content_hash), None
        )
        if duplicate:
            return DeduplicationDecision(
                True,
                int(duplicate["version"]),
                str(duplicate["document_id"]),
                str(duplicate.get("previous_document_id"))
                if duplicate.get("previous_document_id") else None,
            )
        previous = source_records[-1] if source_records else None
        return DeduplicationDecision(
            False,
            int(previous["version"]) + 1 if previous else 1,
            None,
            str(previous["document_id"]) if previous else None,
        )
