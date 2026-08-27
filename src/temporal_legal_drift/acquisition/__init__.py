"""Policy-controlled authoritative-source acquisition."""

from .fetch import AcquisitionService, FetchResponse, UrllibTransport
from .models import SourceArtifact, SourceRequest
from .policy import SourcePolicy
from .store import RawArtifactStore

__all__ = [
    "AcquisitionService",
    "FetchResponse",
    "RawArtifactStore",
    "SourceArtifact",
    "SourcePolicy",
    "SourceRequest",
    "UrllibTransport",
]

