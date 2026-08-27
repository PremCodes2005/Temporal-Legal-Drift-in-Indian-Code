"""Deny-by-default source acquisition policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from temporal_legal_drift.errors import SourcePolicyError
from temporal_legal_drift.jsonio import load_json

from .models import SourceRequest


@dataclass(frozen=True)
class SourcePolicy:
    version: str
    allowed_schemes: frozenset[str]
    approved_hosts: frozenset[str]
    maximum_response_bytes: int
    request_timeout_seconds: float

    @classmethod
    def from_file(cls, path: Path) -> "SourcePolicy":
        value = load_json(path)
        return cls(
            version=str(value["policy_version"]),
            allowed_schemes=frozenset(str(item).lower() for item in value["allowed_schemes"]),
            approved_hosts=frozenset(str(item).lower() for item in value["approved_hosts"]),
            maximum_response_bytes=int(value["maximum_response_bytes"]),
            request_timeout_seconds=float(value["request_timeout_seconds"]),
        )

    def validate_request(self, request: SourceRequest) -> None:
        if not request.official_identifier.strip():
            raise SourcePolicyError("official_identifier is required")
        if not request.instrument_type.strip():
            raise SourcePolicyError("instrument_type is required")
        self.validate_url(request.url)

    def validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()

        if scheme not in self.allowed_schemes:
            raise SourcePolicyError(f"URL scheme {scheme!r} is not approved")
        if not host:
            raise SourcePolicyError("URL must contain a hostname")
        if host not in self.approved_hosts:
            raise SourcePolicyError(
                f"Host {host!r} is not approved by source policy {self.version}; "
                "Phase 1 is deny-by-default"
            )
        if parsed.username or parsed.password:
            raise SourcePolicyError("credentials must not be embedded in source URLs")

