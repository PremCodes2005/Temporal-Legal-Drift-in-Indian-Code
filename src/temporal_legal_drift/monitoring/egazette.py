"""e-Gazette discovery from the public "Bills & Acts" recent-uploads listing (decision v2).

Fragile by nature: HTML parsing of a WebForms page, a cookieless session URL,
and a static PDF path inferred from the Gazette ID. Every assumption is
validated; a mismatch raises SourceShapeError or yields REVIEW_REQUIRED.
"""

from __future__ import annotations

import html
from http.cookiejar import CookieJar
import re
import time
from datetime import datetime
from typing import Callable
from urllib.parse import urlparse

from temporal_legal_drift.acquisition.fetch import Transport, UrllibTransport
from temporal_legal_drift.acquisition.tls import LETS_ENCRYPT_GEN_Y_CHAIN, pinned_intermediate_context
from temporal_legal_drift.errors import AcquisitionError

from .commencement import is_commencement_subject
from .indiacode import DiscoveredRecord, SourceShapeError

HOME = "https://egazette.gov.in/"
ALLOWED_HOSTS = frozenset({"egazette.gov.in"})
MAX_HTML_BYTES = 3 * 1024 * 1024
MAX_PDF_BYTES = 50 * 1024 * 1024
FIELDS = ("Ministry", "Department", "Office", "Subject", "Category", "PartSection", "IssueDate", "PublishDate", "UGID", "FileSize")
GAZETTE_ID = re.compile(r"^C[GS]-[A-Z]{2}-[A-Z]-(\d{8})-(\d+)$")
# Titles of amending instruments, e.g. "The X (Amendment) Act, 2026" or "... Ordinance, 2026";
# a notification that merely cites an Act is not downloaded.
RELEVANT = re.compile(r"\((?:[A-Za-z]+\s+)?Amendment\)\s*(?:Act|Ordinance)|\bOrdinance,?\s+\d{4}", re.I)


def validate_official_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise AcquisitionError(f"URL is outside the e-Gazette allowlist: {url}")


def parse_listing(page: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(100):
        row = {}
        for name in FIELDS:
            match = re.search(rf'id="gvGazetteList_lbl_{name}_{index}"[^>]*>(?:<font[^>]*>)?([^<]*)', page)
            if match is None:
                break
            row[name] = " ".join(html.unescape(match.group(1)).split())
        if len(row) != len(FIELDS):
            break
        rows.append(row)
    if not rows:
        raise SourceShapeError("recent-uploads table lacks the expected gvGazetteList span IDs")
    return rows


def _iso_date(value: str) -> str:
    return datetime.strptime(value, "%d-%b-%Y").date().isoformat()


def _instrument_class(row: dict[str, str]) -> str:
    if row["PartSection"].startswith("Part II-Section 1") or RELEVANT.search(row["Subject"]):
        return "AMENDING_INSTRUMENT"
    # Commencement notifications decide when amendments take effect (docs/methodology/commencement_policy.v1.md).
    return "COMMENCEMENT_NOTIFICATION_CANDIDATE" if is_commencement_subject(row["Subject"]) else "OTHER"


def _megabytes(value: str) -> float | None:
    match = re.match(r"([\d.]+)\s*MB", value)
    return float(match.group(1)) if match else None


class EGazetteConnector:
    source_key = "egazette"

    def __init__(self, transport: Transport | None = None, *, pause_seconds: float = 2.0,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        # egazette.gov.in serves its leaf without the intermediate (docs/sprint/s1_source_access_decision.v3.md).
        self.transport = transport or UrllibTransport(pinned_intermediate_context(LETS_ENCRYPT_GEN_Y_CHAIN), CookieJar())
        self.pause_seconds = pause_seconds
        self.sleep = sleep

    def discover(self, since: str | None, *, max_pages: int = 1) -> list[DiscoveredRecord]:
        """Page 1 of "Bills & Acts" only; postback pagination is deliberately not automated."""
        home = self._fetch(HOME, MAX_HTML_BYTES)
        session = re.match(r"(https://egazette\.gov\.in/\(S\([a-z0-9]+\)\))/", home.final_url)
        if session is None:
            raise SourceShapeError(f"no cookieless session URL after redirect: {home.final_url}")
        # Like a browser following the home-page link: same session cookies plus a Referer; without them the site serves error.aspx.
        page = self._fetch(f"{session.group(1)}/RecentUploads.aspx?Category=1", MAX_HTML_BYTES,
                           headers={"Referer": f"{session.group(1)}/default.aspx"})
        if "/error.aspx" in page.final_url.lower():
            raise SourceShapeError(f"listing redirected to the site's error page: {page.final_url}")
        records = []
        for row in parse_listing(page.payload.decode("utf-8", "replace")):
            identity = GAZETTE_ID.match(row["UGID"])
            if identity is None:
                raise SourceShapeError(f"unexpected Gazette ID format: {row['UGID']!r}")
            published = _iso_date(row["PublishDate"])
            if since is not None and published < since[:10]:
                continue
            size = _megabytes(row["FileSize"])
            url = f"https://egazette.gov.in/WriteReadData/{published[:4]}/{identity.group(2)}.pdf"
            records.append(DiscoveredRecord(
                source_key=self.source_key, official_id=row["UGID"], handle=None, title=row["Subject"],
                canonical_url=url, accessioned_at=published, last_modified=None,
                stated_dates={"issued": _iso_date(row["IssueDate"]), "published": published},
                bitstream_name=f"{identity.group(2)}.pdf", bitstream_url=url, bitstream_md5=None,
                bitstream_bytes=int(size * 1024 * 1024) if size else None,
                listing={**{key: row[key] for key in ("Ministry", "Department", "Office", "Category", "PartSection", "FileSize")},
                         "instrument_class": _instrument_class(row)},
                download_eligible=_instrument_class(row) != "OTHER",
                size_tolerance=0.15,
            ))
        return records

    def download(self, url: str) -> bytes:
        response = self._fetch(url, MAX_PDF_BYTES)
        if response.media_type != "application/pdf" or not response.payload.startswith(b"%PDF-"):
            raise AcquisitionError(f"expected a PDF from {url}, received {response.media_type}")
        return response.payload

    def _fetch(self, url: str, limit: int, headers: dict[str, str] | None = None):
        validate_official_url(url)
        response = self.transport.fetch(url, timeout=60, maximum_bytes=limit, validate_url=validate_official_url,
                                        **({"headers": headers} if headers else {}))
        self.sleep(self.pause_seconds)
        return response
