"""Deterministic discovery over an approved source registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from temporal_legal_drift.acquisition.models import utc_now_iso

from .sources import LegalSource, SourceRegistry


@dataclass(frozen=True)
class DiscoveryCandidate:
    source: LegalSource
    discovered_at: str
    status: str = "DISCOVERED"


class SourceDiscoverer:
    def __init__(self, registry: SourceRegistry, clock: Callable[[], str] = utc_now_iso) -> None:
        self.registry = registry
        self.clock = clock

    def discover(self) -> tuple[DiscoveryCandidate, ...]:
        discovered_at = self.clock()
        return tuple(
            DiscoveryCandidate(source, discovered_at)
            for source in sorted(self.registry.sources, key=lambda item: item.source_id)
            if source.status != "DISABLED"
        )
