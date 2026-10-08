"""Explicit one-shot scheduler; no autonomous legal conclusions or hidden daemon."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Callable

from temporal_legal_drift.acquisition.models import utc_now_iso

from .discover import SourceDiscoverer
from .pipeline import IngestionPipeline, IngestionResult


@dataclass(frozen=True)
class ScheduledRun:
    started_at: str
    completed_at: str
    results: tuple[IngestionResult, ...]


class IngestionScheduler:
    """Runs discovery and ingestion once when explicitly invoked."""

    def __init__(
        self,
        discoverer: SourceDiscoverer,
        pipeline: IngestionPipeline,
        clock: Callable[[], str] = utc_now_iso,
    ) -> None:
        self.discoverer = discoverer
        self.pipeline = pipeline
        self.clock = clock
        self._lock = Lock()

    def run_once(self) -> ScheduledRun:
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("an ingestion run is already active")
        started_at = self.clock()
        try:
            results = self.pipeline.run(self.discoverer.discover())
        finally:
            self._lock.release()
        return ScheduledRun(started_at, self.clock(), results)
