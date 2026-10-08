"""Policy-controlled downloader that does not assign legal significance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from temporal_legal_drift.acquisition import FetchResponse, SourcePolicy, SourceRequest
from temporal_legal_drift.acquisition.fetch import Transport, UrllibTransport
from temporal_legal_drift.acquisition.models import utc_now_iso
from temporal_legal_drift.errors import AcquisitionError

from .sources import LegalSource


@dataclass(frozen=True)
class DownloadedDocument:
    payload: bytes
    final_url: str
    content_type: str
    retrieved_at: str
    response_headers: dict[str, str]


class LegalDocumentDownloader:
    def __init__(
        self,
        policy: SourcePolicy,
        transport: Transport | None = None,
        clock: Callable[[], str] = utc_now_iso,
    ) -> None:
        self.policy = policy
        self.transport = transport or UrllibTransport()
        self.clock = clock

    def download(self, source: LegalSource) -> DownloadedDocument:
        request = SourceRequest(source.url, source.source_id, source.source_type)
        self.policy.validate_request(request)
        response: FetchResponse = self.transport.fetch(
            source.url,
            timeout=self.policy.request_timeout_seconds,
            maximum_bytes=self.policy.maximum_response_bytes,
            validate_url=self.policy.validate_url,
        )
        self.policy.validate_url(response.final_url)
        content_type = response.media_type.split(";", 1)[0].strip().lower()
        if source.mime_type and content_type != source.mime_type.lower():
            raise AcquisitionError(
                f"Expected {source.mime_type!r} for {source.source_id}, received {content_type!r}"
            )
        if content_type == "application/pdf" and not response.payload.startswith(b"%PDF-"):
            raise AcquisitionError("PDF response does not begin with a PDF signature")
        return DownloadedDocument(
            response.payload,
            response.final_url,
            content_type,
            self.clock(),
            dict(response.headers),
        )
