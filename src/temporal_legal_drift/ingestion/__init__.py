"""Phase 1 authoritative legal-source ingestion pipeline."""

from .discover import DiscoveryCandidate, SourceDiscoverer
from .downloader import DownloadedDocument, LegalDocumentDownloader
from .metadata import DocumentRecord, IngestionStore
from .pipeline import IngestionPipeline, IngestionResult
from .scheduler import IngestionScheduler, ScheduledRun
from .sources import LegalSource, SourceRegistry

__all__ = [
    "DiscoveryCandidate",
    "DocumentRecord",
    "DownloadedDocument",
    "IngestionPipeline",
    "IngestionResult",
    "IngestionScheduler",
    "IngestionStore",
    "LegalDocumentDownloader",
    "LegalSource",
    "SourceDiscoverer",
    "SourceRegistry",
    "ScheduledRun",
]
