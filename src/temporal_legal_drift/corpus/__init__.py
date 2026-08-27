"""Manifest-driven bounded corpus acquisition and normalization."""

from .download import CorpusDownloader, DownloadSummary
from .manifest import CorpusEntry, CorpusManifest

__all__ = ["CorpusDownloader", "CorpusEntry", "CorpusManifest", "DownloadSummary"]

