"""Rebuild the immutable raw-artifact store from committed corpus copies.

``download-corpus`` populates ``data/raw`` from the network. That directory is
runtime-only and git-ignored, so a fresh checkout (CI, a reviewer, the Phase 11
fresh-environment check) has the readable PDFs under ``data/corpus`` but not the
content-addressed raw store the rest of the pipeline reads.

This module reconstructs ``data/raw`` deterministically and offline from
``configs/corpus/pilot_v1.json`` plus ``data/corpus/index.json`` plus the
materialized ``data/corpus/pdfs`` files. Bytes are the committed bytes; the
per-artifact SHA-256 and length are verified against the manifest, so the
rebuilt store is byte-identical to one produced by a real download for every
field the downstream stages consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from temporal_legal_drift.acquisition import RawArtifactStore
from temporal_legal_drift.acquisition.models import SourceArtifact, content_sha256
from temporal_legal_drift.errors import IntegrityError
from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes, load_json

from .manifest import CorpusManifest

# Fixed, provenance-only fields. ``retrieved_at``/``final_url``/``acquisition_method``/
# ``response_headers`` are recorded on the artifact but never read by normalization,
# the version graph, the corpus report, the gates or the RAG index, so a constant
# keeps the rebuilt store reproducible.
_REHYDRATED_RETRIEVED_AT = "1970-01-01T00:00:00Z"
_REHYDRATED_METHOD = "OfflineRehydrationFromCommittedCorpus"


@dataclass(frozen=True)
class RehydrationSummary:
    manifest_id: str
    rehydrated: tuple[str, ...]
    checkpoint_path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "rehydrated": list(self.rehydrated),
            "checkpoint_path": str(self.checkpoint_path),
        }


def rehydrate_raw_store(
    manifest: CorpusManifest,
    raw_store: RawArtifactStore,
    corpus_index_path: Path,
    pdf_directory: Path,
) -> RehydrationSummary:
    index_entries = {
        str(entry.get("entry_id")): entry
        for entry in load_json(corpus_index_path).get("entries", [])
        if isinstance(entry, dict)
    }

    completed: dict[str, str] = {}
    rehydrated: list[str] = []
    for entry in manifest.entries:
        index_entry = index_entries.get(entry.entry_id)
        if index_entry is None:
            raise ValueError(f"Corpus index has no entry for {entry.entry_id}")

        expected_sha = str(index_entry["sha256"])
        expected_length = int(index_entry["byte_length"])
        source_artifact_id = str(index_entry["source_artifact_id"])

        pdf_path = pdf_directory / f"{entry.entry_id}.pdf"
        payload = pdf_path.read_bytes()
        actual_sha = content_sha256(payload)
        if actual_sha != expected_sha or len(payload) != expected_length:
            raise IntegrityError(
                f"{entry.entry_id}: committed PDF does not match the corpus index "
                f"({actual_sha}/{len(payload)} vs {expected_sha}/{expected_length})"
            )

        _, blob_path = raw_store.store_blob(payload, "application/pdf")
        artifact = SourceArtifact(
            source_artifact_id=source_artifact_id,
            request_url=entry.url,
            final_url=entry.url,
            official_identifier=entry.official_identifier,
            instrument_type=entry.instrument_type,
            retrieved_at=_REHYDRATED_RETRIEVED_AT,
            media_type="application/pdf",
            byte_length=expected_length,
            sha256=expected_sha,
            blob_path=blob_path,
            acquisition_method=_REHYDRATED_METHOD,
            response_headers={},
            notes=entry.research_role,
            corpus_entry_id=entry.entry_id,
            parent_reference_url=entry.parent_reference_url,
        )
        metadata_path = raw_store.metadata_root / f"{source_artifact_id}.json"
        if metadata_path.exists():
            metadata_path.unlink()
        raw_store.store_metadata(artifact)
        raw_store.verify(artifact)

        completed[entry.entry_id] = source_artifact_id
        rehydrated.append(entry.entry_id)

    checkpoint_path = raw_store.root / "checkpoints" / f"{manifest.manifest_id}.json"
    atomic_replace(
        checkpoint_path,
        canonical_json_bytes(
            {
                "schema_version": "1.0.0",
                "manifest_id": manifest.manifest_id,
                "manifest_schema_version": manifest.schema_version,
                "status": manifest.status,
                "completed": dict(sorted(completed.items())),
            }
        ),
    )
    return RehydrationSummary(manifest.manifest_id, tuple(rehydrated), checkpoint_path)
