"""Acquisition data contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Mapping


@dataclass(frozen=True)
class SourceRequest:
    url: str
    official_identifier: str
    instrument_type: str
    notes: str | None = None


@dataclass(frozen=True)
class SourceArtifact:
    source_artifact_id: str
    request_url: str
    final_url: str
    official_identifier: str
    instrument_type: str
    retrieved_at: str
    media_type: str
    byte_length: int
    sha256: str
    blob_path: str
    acquisition_method: str
    response_headers: Mapping[str, str] = field(default_factory=dict)
    notes: str | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["response_headers"] = dict(sorted(self.response_headers.items()))
        return value


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def content_sha256(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def make_source_artifact_id(
    request: SourceRequest,
    content_hash: str,
    retrieved_at: str,
) -> str:
    identity = "\n".join(
        [request.url, request.official_identifier, request.instrument_type, content_hash, retrieved_at]
    ).encode("utf-8")
    return f"src_{sha256(identity).hexdigest()[:24]}"

