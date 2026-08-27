"""HTTP acquisition with injectable transport and redirect-policy enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from temporal_legal_drift.errors import AcquisitionError

from .models import (
    SourceArtifact,
    SourceRequest,
    make_source_artifact_id,
    utc_now_iso,
)
from .policy import SourcePolicy
from .store import RawArtifactStore


@dataclass(frozen=True)
class FetchResponse:
    payload: bytes
    final_url: str
    media_type: str
    headers: Mapping[str, str]


class Transport(Protocol):
    def fetch(
        self,
        url: str,
        *,
        timeout: float,
        maximum_bytes: int,
        validate_url: Callable[[str], None],
    ) -> FetchResponse: ...


class _PolicyRedirectHandler(HTTPRedirectHandler):
    def __init__(self, validate_url: Callable[[str], None]) -> None:
        super().__init__()
        self.validate_url = validate_url

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        self.validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibTransport:
    user_agent = "TemporalLegalDriftResearch/0.1 (+provenance-controlled acquisition)"

    def fetch(
        self,
        url: str,
        *,
        timeout: float,
        maximum_bytes: int,
        validate_url: Callable[[str], None],
    ) -> FetchResponse:
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "*/*"})
        opener = build_opener(_PolicyRedirectHandler(validate_url))
        try:
            with opener.open(request, timeout=timeout) as response:
                declared_length = response.headers.get("Content-Length")
                if declared_length and int(declared_length) > maximum_bytes:
                    raise AcquisitionError(
                        f"Response declares {declared_length} bytes; limit is {maximum_bytes}"
                    )
                payload = response.read(maximum_bytes + 1)
                if len(payload) > maximum_bytes:
                    raise AcquisitionError(f"Response exceeds {maximum_bytes} byte limit")
                media_type = response.headers.get_content_type() or "application/octet-stream"
                headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                    if key.lower() in {"content-type", "content-length", "etag", "last-modified"}
                }
                return FetchResponse(payload, response.geturl(), media_type, headers)
        except AcquisitionError:
            raise
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            raise AcquisitionError(f"Could not acquire {url}: {error}") from error


class AcquisitionService:
    def __init__(
        self,
        policy: SourcePolicy,
        store: RawArtifactStore,
        transport: Transport | None = None,
        clock: Callable[[], str] = utc_now_iso,
    ) -> None:
        self.policy = policy
        self.store = store
        self.transport = transport or UrllibTransport()
        self.clock = clock

    def acquire(self, request: SourceRequest) -> SourceArtifact:
        self.policy.validate_request(request)
        response = self.transport.fetch(
            request.url,
            timeout=self.policy.request_timeout_seconds,
            maximum_bytes=self.policy.maximum_response_bytes,
            validate_url=self.policy.validate_url,
        )
        self.policy.validate_url(response.final_url)
        actual_media_type = response.media_type.split(";", 1)[0].strip().lower()
        expected_media_type = (request.expected_media_type or "").strip().lower()
        if expected_media_type and actual_media_type != expected_media_type:
            raise AcquisitionError(
                f"Expected media type {expected_media_type!r}, received {actual_media_type!r}"
            )
        if expected_media_type == "application/pdf" and not response.payload.startswith(b"%PDF-"):
            raise AcquisitionError("Response claims to be PDF but does not begin with a PDF signature")

        retrieved_at = self.clock()
        content_hash, blob_path = self.store.store_blob(response.payload, response.media_type)
        artifact = SourceArtifact(
            source_artifact_id=make_source_artifact_id(request, content_hash, retrieved_at),
            request_url=request.url,
            final_url=response.final_url,
            official_identifier=request.official_identifier,
            instrument_type=request.instrument_type,
            retrieved_at=retrieved_at,
            media_type=response.media_type,
            byte_length=len(response.payload),
            sha256=content_hash,
            blob_path=blob_path,
            acquisition_method=type(self.transport).__name__,
            response_headers=response.headers,
            notes=request.notes,
            corpus_entry_id=request.corpus_entry_id,
            parent_reference_url=request.parent_reference_url,
        )
        self.store.store_metadata(artifact)
        self.store.verify(artifact)
        return artifact
