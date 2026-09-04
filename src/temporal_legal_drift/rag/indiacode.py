"""Authoritative India Code source metadata used by the RAG layer."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request, urlopen

INDIA_CODE_HOME = "https://indiacode.gov.in/"
INDIA_CODE_API = "https://indiacode.gov.in/server/api"
LEGACY_HOSTS = {"indiacode.nic.in", "www.indiacode.nic.in"}
CURRENT_HOSTS = {"indiacode.gov.in", "www.indiacode.gov.in"}


def is_india_code_url(value: str) -> bool:
    """Return whether a URL belongs to the current or legacy official portal."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname in LEGACY_HOSTS | CURRENT_HOSTS


def portal_search_url(query: str) -> str:
    """Return a stable portal entry point with a human-readable query hint.

    India Code migrated domains in 2026 and its internal routes may change. The
    application therefore links to the official portal rather than fabricating
    an undocumented search API URL.
    """
    # The portal exposes a human search form, but no stable public query API is
    # assumed here. Keep the link resilient by using the official home route.
    return INDIA_CODE_HOME


def source_guidance(query: str) -> dict[str, str]:
    return {
        "message": (
            "The retrieved excerpts may be incomplete. Visit the official India Code "
            "website for the complete legislation, commencement details and further information."
        ),
        "label": "Visit India Code for further information",
        "url": portal_search_url(query),
    }


@dataclass(frozen=True)
class LiveSearchResult:
    chunks: tuple[dict[str, object], ...]
    amendments: tuple[dict[str, object], ...] = ()
    error: str | None = None


class IndiaCodeLiveRepository:
    """Read current Central-Act section records from India Code's public API.

    Live records supplement the reproducible local corpus. They are never
    labelled as historical pre-amendment versions merely because they contain
    amendment footnotes.
    """

    def search_sections(self, query: str, *, limit: int = 6) -> LiveSearchResult:
        repository_query = _repository_query(query)
        params = urlencode({
            "query": repository_query,
            "f.identifier_collection": "SECTION,equals",
            "size": 20,
        })
        request = Request(
            f"{INDIA_CODE_API}/discover/search/objects?{params}",
            headers={"Accept": "application/json", "User-Agent": "TemporalLegalDriftResearch/1.0"},
        )
        try:
            with urlopen(request, timeout=12) as response:
                document = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
            return LiveSearchResult((), (), type(error).__name__)

        query_tokens = set(_tokens(query))
        candidates: list[dict[str, object]] = []
        objects = (
            document.get("_embedded", {}).get("searchResult", {})
            .get("_embedded", {}).get("objects", [])
        )
        for row in objects:
            item = row.get("_embedded", {}).get("indexableObject", {})
            metadata = item.get("metadata", {})
            if _value(metadata, "dc.identifier.state_name") != "CENTRAL":
                continue
            provision = _plain_text(_value(metadata, "dc.identifier.section_page_note"))
            if not provision:
                continue
            act_name = _value(metadata, "dc.title.act_name")
            section_number = _value(metadata, "dc.identifier.section_number")
            title = item.get("name") or _value(metadata, "dc.title")
            searchable = set(_tokens(f"{act_name} {title} {section_number} {provision}"))
            lexical = len(query_tokens & searchable) / max(1, len(query_tokens))
            if lexical <= 0:
                continue
            uuid = str(item.get("uuid", ""))
            handle = str(item.get("handle", ""))
            candidates.append({
                "chunk_id": f"live_{sha256(uuid.encode()).hexdigest()[:24]}",
                "text": provision,
                "score": min(1.0, 0.45 + lexical * 0.55),
                "semantic_score": 0.0,
                "lexical_score": lexical,
                "metadata": {
                    "entry_id": f"indiacode-live-{uuid}",
                    "document_type": "current_consolidated_section",
                    "version": "current_repository_record",
                    "act_name": act_name,
                    "date": _value(metadata, "dc.date.act_year") or None,
                    "source_anchor": f"Section {section_number}" if section_number else str(title),
                    "official_identifier": f"IndiaCode:{handle}",
                    "source_url": f"https://indiacode.gov.in/items/{uuid}",
                    "official_portal_url": INDIA_CODE_HOME,
                    "source_kind": "live_indiacode_section",
                },
            })
        candidates.sort(key=lambda item: (-float(item["score"]), str(item["chunk_id"])))
        amendments, amendment_error = self.search_amendments(query, limit=30)
        return LiveSearchResult(
            tuple(candidates[:limit]),
            amendments,
            amendment_error,
        )

    def search_amendments(
        self, query: str, *, limit: int = 30
    ) -> tuple[tuple[dict[str, object], ...], str | None]:
        repository_query = _repository_query(query)
        params = urlencode({
            "query": repository_query,
            "f.identifier_collection": "ACT_AMENDMENT,equals",
            "size": 100,
        })
        request = Request(
            f"{INDIA_CODE_API}/discover/search/objects?{params}",
            headers={"Accept": "application/json", "User-Agent": "TemporalLegalDriftResearch/1.0"},
        )
        try:
            with urlopen(request, timeout=12) as response:
                document = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
            return (), type(error).__name__

        ignored = {"the", "act", "acts", "amendment", "amendments", "what", "changed", "change", "in", "of", "and", "under", "recently"}
        query_tokens = set(_tokens(query)) - ignored
        matches: list[tuple[float, dict[str, object]]] = []
        objects = (
            document.get("_embedded", {}).get("searchResult", {})
            .get("_embedded", {}).get("objects", [])
        )
        for row in objects:
            item = row.get("_embedded", {}).get("indexableObject", {})
            metadata = item.get("metadata", {})
            title = str(item.get("name") or _value(metadata, "dc.title"))
            target = _value(metadata, "dc.title.act_name")
            searchable = set(_tokens(f"{title} {target}")) - ignored
            overlap = len(query_tokens & searchable) / max(1, len(query_tokens))
            if overlap < 0.6:
                continue
            uuid = str(item.get("uuid", ""))
            handle = str(item.get("handle", ""))
            years = re.findall(r"(?:19|20)\d{2}", title)
            matches.append((overlap, {
                "title": title,
                "target_act": target or None,
                "year": years[-1] if years else None,
                "official_identifier": f"IndiaCode:{handle}",
                "source_url": f"https://indiacode.gov.in/items/{uuid}",
            }))
        matches.sort(key=lambda row: (-row[0], str(row[1].get("year") or ""), str(row[1]["title"])))
        unique: list[dict[str, object]] = []
        seen: set[tuple[str, str | None]] = set()
        for _, item in matches:
            key = (str(item["title"]).lower(), item.get("target_act"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
            if len(unique) >= limit:
                break
        return tuple(unique), None


def _value(metadata: dict[str, object], key: str) -> str:
    values = metadata.get(key)
    if not isinstance(values, list) or not values or not isinstance(values[0], dict):
        return ""
    return str(values[0].get("value") or "")


def _plain_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>|<hr[^>]*>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(html.unescape(value).split())


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z][a-z0-9]+|\d+", value.lower())


def _repository_query(value: str) -> str:
    ignored = {
        "what", "which", "when", "where", "why", "how", "changed", "change",
        "changes", "recent", "recently", "compare", "before", "after", "under",
        "regarding", "about", "please", "tell", "explain", "amendment", "amendments",
    }
    useful = [token for token in _tokens(value) if token not in ignored]
    return " ".join(useful) or value
