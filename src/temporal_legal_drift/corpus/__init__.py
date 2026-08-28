"""Manifest-driven bounded corpus acquisition and normalization."""

from .download import CorpusDownloader, DownloadSummary
from .manifest import CorpusEntry, CorpusManifest
from .materialize import MaterializationSummary, materialize_corpus

__all__ = [
    "CorpusDownloader",
    "CorpusEntry",
    "CorpusManifest",
    "DownloadSummary",
    "MaterializationSummary",
    "materialize_corpus",
]
