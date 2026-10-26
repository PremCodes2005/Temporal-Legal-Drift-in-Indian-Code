"""India Code discovery through the DSpace REST interface recorded in S1.

Only read endpoints observed on 2026-10-12 are used. If the response shape
changes, the connector raises SourceShapeError instead of guessing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlencode, urlparse

from temporal_legal_drift.acquisition.fetch import Transport, UrllibTransport
from temporal_legal_drift.errors import AcquisitionError

API = "https://indiacode.gov.in/server/api"
ALLOWED_HOSTS = frozenset({"indiacode.gov.in", "www.indiacode.gov.in"})
MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 50 * 1024 * 1024


class SourceShapeError(ValueError):
    """The official response no longer matches the recorded interface."""


@dataclass(frozen=True)
class DiscoveredRecord:
    source_key: str
    official_id: str          # DSpace item UUID
    handle: str | None
    title: str
    canonical_url: str
    accessioned_at: str
    last_modified: str | None
    stated_dates: dict[str, str | None]   # unapproved facts, kept separate
    bitstream_name: str | None
    bitstream_url: str | None
    bitstream_md5: str | None
    bitstream_bytes: int | None
    listing: dict[str, object] = field(default_factory=dict)  # source-specific listing fields
    download_eligible: bool = True                              # False: keep as a metadata observation only
    size_tolerance: float | None = None                         # e.g. 0.15 when only an approximate size is listed

    def metadata_fingerprint(self) -> str:
        """What the source says about the bytes, without downloading them."""
        from hashlib import sha256
        from json import dumps

        return sha256(dumps([self.bitstream_md5, self.bitstream_bytes, self.last_modified, self.listing], sort_keys=True,
                            default=str).encode()).hexdigest()


def validate_official_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise AcquisitionError(f"URL is outside the India Code allowlist: {url}")


class IndiaCodeConnector:
    source_key = "india_code"

    def __init__(self, transport: Transport | None = None, *, pause_seconds: float = 2.0,
                 sleep: Callable[[float], None] = time.sleep, page_size: int = 20) -> None:
        self.transport = transport or UrllibTransport()
        self.pause_seconds = pause_seconds
        self.sleep = sleep
        self.page_size = page_size

    def discover(self, since: str | None, *, max_pages: int = 5) -> list[DiscoveredRecord]:
        """Items accessioned after ``since`` (ISO UTC), newest first, within a page bound."""
        records: list[DiscoveredRecord] = []
        for page in range(max_pages):
            query = urlencode({"dsoType": "ITEM", "sort": "dc.date.accessioned,DESC", "size": self.page_size, "page": page})
            objects = self._json(f"{API}/discover/search/objects?{query}")
            try:
                found = objects["_embedded"]["searchResult"]["_embedded"]["objects"]
            except (KeyError, TypeError) as error:
                raise SourceShapeError("search response lacks _embedded.searchResult objects") from error
            reached_cursor = False
            for item in found:
                record = self._record(item)
                if since is not None and record.accessioned_at <= since:
                    reached_cursor = True
                    break
                records.append(record)
            if reached_cursor or len(found) < self.page_size:
                break
        return records

    def download(self, url: str) -> bytes:
        response = self._fetch(url, MAX_PDF_BYTES)
        if response.media_type != "application/pdf" or not response.payload.startswith(b"%PDF-"):
            raise AcquisitionError(f"expected a PDF from {url}, received {response.media_type}")
        return response.payload

    def _record(self, item: dict) -> DiscoveredRecord:
        try:
            obj = item["_embedded"]["indexableObject"]
            uuid, metadata = str(obj["uuid"]), obj["metadata"]
        except (KeyError, TypeError) as error:
            raise SourceShapeError("search object lacks indexableObject uuid/metadata") from error
        value = lambda key: (metadata.get(key) or [{}])[0].get("value")  # noqa: E731
        accessioned = value("dc.date.accessioned")
        if not accessioned:
            raise SourceShapeError(f"item {uuid} has no dc.date.accessioned")
        bitstream = self._original_bitstream(uuid)
        return DiscoveredRecord(
            source_key=self.source_key, official_id=uuid, handle=obj.get("handle"),
            title=str(value("dc.title") or "(untitled)"), canonical_url=f"https://indiacode.gov.in/items/{uuid}",
            accessioned_at=str(accessioned), last_modified=obj.get("lastModified"),
            stated_dates={"issued": value("dc.date.issued"), "enactment": value("dc.date.enactment")},
            bitstream_name=bitstream.get("name"), bitstream_url=bitstream.get("url"),
            bitstream_md5=bitstream.get("md5"), bitstream_bytes=bitstream.get("bytes"),
            download_eligible=bool(bitstream.get("url")),  # no single PDF: listed only, never guessed
        )

    def _original_bitstream(self, uuid: str) -> dict:
        bundles = self._json(f"{API}/core/items/{uuid}/bundles?embed=bitstreams")
        for bundle in bundles.get("_embedded", {}).get("bundles", []):
            if bundle.get("name") != "ORIGINAL":
                continue
            streams = bundle.get("_embedded", {}).get("bitstreams", {}).get("_embedded", {}).get("bitstreams", [])
            pdfs = [s for s in streams if str(s.get("name", "")).lower().endswith(".pdf")]
            if len(pdfs) == 1:  # several files: leave for review rather than choose one
                stream = pdfs[0]
                checksum = stream.get("checkSum") or {}
                return {"name": stream.get("name"), "url": stream["_links"]["content"]["href"],
                        "md5": checksum.get("value") if checksum.get("checkSumAlgorithm") == "MD5" else None,
                        "bytes": stream.get("sizeBytes")}
        return {}

    def _json(self, url: str) -> dict:
        response = self._fetch(url, MAX_JSON_BYTES)
        try:
            return json.loads(response.payload)
        except json.JSONDecodeError as error:
            raise SourceShapeError(f"non-JSON response from {url}") from error

    def _fetch(self, url: str, limit: int):
        validate_official_url(url)
        response = self.transport.fetch(url, timeout=60, maximum_bytes=limit, validate_url=validate_official_url)
        self.sleep(self.pause_seconds)
        return response
