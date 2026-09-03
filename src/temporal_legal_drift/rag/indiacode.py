"""Authoritative India Code source metadata used by the RAG layer."""

from __future__ import annotations

from urllib.parse import urlparse


INDIA_CODE_HOME = "https://indiacode.gov.in/"
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
