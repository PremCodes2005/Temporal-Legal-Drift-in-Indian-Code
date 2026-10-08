"""Reproducible Phase 1 checkpoint over 25 already-downloaded India Code PDFs."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from temporal_legal_drift.acquisition import FetchResponse, SourcePolicy
from temporal_legal_drift.errors import AcquisitionError
from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json

from .discover import SourceDiscoverer
from .downloader import LegalDocumentDownloader
from .metadata import IngestionStore
from .pipeline import IngestionPipeline
from .sources import LegalSource, SourceRegistry


CHECKPOINT_TIME = "2026-10-08T09:30:00Z"


class LocalCorpusTransport:
    """Offline checkpoint transport backed by verified local corpus PDFs."""

    def __init__(self, files_by_url: dict[str, Path]) -> None:
        self.files_by_url = files_by_url

    def fetch(self, url, *, timeout, maximum_bytes, validate_url):  # type: ignore[no-untyped-def]
        validate_url(url)
        path = self.files_by_url.get(url)
        if path is None or not path.is_file():
            raise AcquisitionError(f"checkpoint mirror has no file for {url}")
        payload = path.read_bytes()
        if len(payload) > maximum_bytes:
            raise AcquisitionError("checkpoint file exceeds source policy size limit")
        return FetchResponse(payload, url, "application/pdf", {"x-checkpoint-mirror": "local"})


def build_phase1_checkpoint(root: Path) -> dict[str, object]:
    root = root.resolve()
    registry = SourceRegistry.from_file(root / "configs/ingestion/source_registry.v1.json")
    if not 20 <= len(registry.sources) <= 30:
        raise ValueError("Phase 1 checkpoint registry must contain 20-30 legal documents")
    corpus = load_json(root / "data/corpus/index.json")
    entries = {
        str(item["entry_id"]): item
        for item in corpus.get("entries", []) if isinstance(item, dict)
    }
    files_by_url: dict[str, Path] = {}
    for source in registry.sources:
        entry = entries.get(source.source_id)
        if not entry:
            raise ValueError(f"checkpoint source is absent from corpus index: {source.source_id}")
        path = root / "data/corpus/pdfs" / str(entry["filename"])
        if not path.is_file():
            raise ValueError(f"checkpoint PDF is missing: {path}")
        files_by_url[source.url] = path

    policy = SourcePolicy.from_file(root / "configs/source_policy.v1.json")
    fixed_clock = lambda: CHECKPOINT_TIME
    candidates = SourceDiscoverer(registry, fixed_clock).discover()
    store = IngestionStore(root)

    # Preserve a controlled failed attempt, then retry through the full mirror.
    missing_first = dict(files_by_url)
    missing_first.pop(candidates[0].source.url)
    failed = IngestionPipeline(
        LegalDocumentDownloader(policy, LocalCorpusTransport(missing_first), fixed_clock), store
    ).process(candidates[0])
    pipeline = IngestionPipeline(
        LegalDocumentDownloader(policy, LocalCorpusTransport(files_by_url), fixed_clock), store
    )
    results = pipeline.run(candidates)
    duplicate = pipeline.process(candidates[0])
    revision_verified = _verify_revision_semantics(policy, registry.sources[0])

    manifest_path = root / "data/manifests/gazette_ingestion_v1.provenance.json"
    manifest = store.write_provenance_manifest(manifest_path)
    records = manifest["documents"]
    checks = {
        "test_set_between_20_and_30": 20 <= len(records) <= 30,
        "all_document_ids_unique": manifest["unique_document_ids"] == len(records),
        "all_sha256_recorded": all(len(str(item.get("sha256", ""))) == 64 for item in records),
        "duplicate_download_detected": duplicate.duplicate is True,
        "duplicate_reuses_document_id": duplicate.document_id == results[0].document_id,
        "revised_file_creates_new_version": revision_verified,
        "source_urls_preserved": all(bool(item.get("source_url")) for item in records),
        "retrieval_timestamps_preserved": all(bool(item.get("retrieved_at")) for item in records),
        "publication_dates_preserved": all(bool(item.get("publication_date")) for item in records),
        "failed_download_logged": failed.status == "DOWNLOAD_FAILED" and manifest["failure_count"] >= 1,
        "new_documents_enter_review_queue": manifest["review_queue_count"] == len(records),
        "no_legal_change_claimed": manifest["legal_change_claimed"] is False,
    }
    document = {
        "schema_version": "1.0.0",
        "phase": 1,
        "deliverable": "Gazette ingestion pipeline v1 + source registry + immutable provenance manifest",
        "status": "passed" if all(checks.values()) else "failed",
        "registry_id": registry.registry_id,
        "document_count": len(records),
        "checks": checks,
        "provenance_manifest": str(manifest_path.relative_to(root)),
        "human_review_required": True,
        "legal_change_claimed": False,
    }
    checkpoint_path = root / "reports/phase1/ingestion_checkpoint.v1.json"
    atomic_write_new(checkpoint_path, canonical_json_bytes(document))
    if document["status"] != "passed":
        raise ValueError("Phase 1 checkpoint did not pass every check")
    return document


def _verify_revision_semantics(policy: SourcePolicy, template: LegalSource) -> bool:
    class RevisionTransport:
        def __init__(self) -> None:
            self.payload = b"%PDF-1.4\nversion one"

        def fetch(self, url, *, timeout, maximum_bytes, validate_url):  # type: ignore[no-untyped-def]
            validate_url(url)
            return FetchResponse(self.payload, url, "application/pdf", {})

    with TemporaryDirectory(prefix="tldrift-phase1-revision-") as directory:
        transport = RevisionTransport()
        pipeline = IngestionPipeline(
            LegalDocumentDownloader(policy, transport, lambda: CHECKPOINT_TIME),
            IngestionStore(Path(directory)),
        )
        candidate = SourceDiscoverer(
            SourceRegistry("revision-fixture", "1.0.0", (template,)),
            lambda: CHECKPOINT_TIME,
        ).discover()[0]
        first = pipeline.process(candidate)
        transport.payload = b"%PDF-1.4\nversion two"
        second = pipeline.process(candidate)
        records = pipeline.store.records()
        return (
            first.status == second.status == "INGESTED"
            and first.document_id != second.document_id
            and [item["version"] for item in records] == [1, 2]
            and records[1]["previous_document_id"] == records[0]["document_id"]
        )
