"""Question routing (question-route-v1): a deterministic decision, made before any retrieval, about what the question
is and which documents may be used to answer it.

The model never chooses the Act. Every route names its response type, a reason code and the corpus entries that
retrieval and citations are limited to; routes that do not answer from an Act allow none.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from .question import CANONICAL, ActCatalog, QuestionFrame, _norm

ROUTE_VERSION = "question-route-v1"
RESPONSE_TYPES = {  # route -> response type
    "act_identified": "act_answer",
    "amendment_mismatch": "act_answer",
    "act_comparison": "act_comparison",
    "act_ambiguous": "act_choice",
    "several_acts": "act_choice",
    "act_not_found": "act_not_found",
    "latest_records": "latest_records",
    "general_no_act": "act_choice",
    "outside_domain": "scope_guidance",
}
LATEST = re.compile(r"\b(?:latest|recent(?:ly)?|newest|new(?:ly)?\s+(?:published|notified)|just\s+(?:published|notified)|this\s+(?:week|month))\b", re.I)
SOURCE = {"india_code": re.compile(r"\bindia\s*code\b", re.I), "egazette": re.compile(r"\be-?\s*gazette\b|\bgazette\b", re.I)}
LAW_SCOPE = re.compile(r"\b(?:law|laws|legislation|notifications?|amendments?|acts?|ordinances?|changes?|updates?|published|appeared)\b", re.I)
COMPARE = re.compile(r"\b(?:compare|comparison|versus|vs\.?|differences?|differ)\b|\bbetween\b.+\band\b", re.I)
OVERVIEW = re.compile(r"\b(?:generally|overall|overview|summar(?:y|ise|ize)|purpose|cover(?:s|ed)?|deals?\s+with)\b|^\W*what\s+is\s+(?:the\s+)?[\w\s()'-]{2,80}\b(?:act|code|sanhita|adhiniyam)\W*$", re.I)
# Words that make a question a legal one; without any of them the question is outside what this assistant answers.
LEGAL = re.compile(r"\b(?:laws?|legal|legally|act|code|sanhita|section|offen[cs]es?|punish\w*|penalt\w*|fines?|court|tribunal|judge|rules?|regulations?|"
                   r"notif\w*|gazette|amend\w*|complian\w*|liab\w*|contracts?|rights?|dut(?:y|ies)|obligations?|licen[cs]\w*|tax\w*|gst|compan(?:y|ies)|"
                   r"directors?|employ\w*|tenants?|landlords?|consumers?|police|arrest\w*|bail|crimes?|criminal|civil|statut\w*|provisions?|penal|"
                   r"prosecut\w*|compensation|registration|permits?|privacy|personal\s+data|theft|murder|fraud|cheating|defamation|divorce|marriage|"
                   r"propert(?:y|ies)|lease|wages?|insolvency|bankruptcy|arbitration|patents?|copyright|trademarks?|environment\w*|pollution|"
                   r"electricity|customs|evidence|procedure|sue|appeal|petition|lawful|unlawful|illegal|authority|regulator|ministry|government)\b", re.I)
CLOSE_MATCH = 0.85  # spelling similarity needed to offer an Act as "did you mean"; below this nothing is suggested


def route_question(query: str, frame: QuestionFrame, catalog: ActCatalog, *, chosen: bool = False) -> dict[str, Any]:
    """The route for a parsed question. Order matters: a choice the user must make comes before any answer."""
    if frame.act_choices:
        return _route("act_ambiguous", "SEVERAL_ACTS_SHARE_THE_NAME", choices=frame.act_choices,
                      message="More than one Act in the corpus has this name. Choose the one you mean.")
    if frame.unresolved_act_phrases:
        suggestions = {phrase: close_matches(phrase, catalog) for phrase in frame.unresolved_act_phrases}
        return _route("act_not_found", "ACT_NOT_IN_CORPUS", unresolved=frame.unresolved_act_phrases,
                      choices=[ref for refs in suggestions.values() for ref in refs], suggestions_by_phrase=suggestions)
    if frame.principal and frame.other_acts:
        acts = [frame.principal, *frame.other_acts]
        if COMPARE.search(query):
            return _route("act_comparison", "COMPARISON_REQUESTED", acts=acts, allowed=[a.entry_id for a in acts])
        return _route("several_acts", "SEVERAL_ACTS_NAMED", choices=acts,
                      message="The question names more than one Act. Choose one, or ask for a comparison of them.")
    if frame.principal or frame.amending:
        acts = [ref for ref in (frame.principal, frame.amending) if ref]
        if frame.relation_error:
            targets = sorted(t for t in catalog.relations.get(frame.amending.entry_id, set()) if t in catalog.entries)
            return _route("amendment_mismatch", "AMENDMENT_NOT_RECORDED_FOR_ACT", acts=acts, allowed=[], choices=[catalog.ref(t) for t in targets])
        allowed = allowed_entries(frame, catalog)
        reason = "USER_SELECTED_ACT" if chosen else "ACT_NAMED_IN_QUESTION"
        overview = bool(not frame.sections and not frame.asks_about_versions and (OVERVIEW.search(query) or not frame.focus_terms))
        return _route("act_identified", reason, acts=acts, allowed=allowed, overview=overview)
    if LATEST.search(query) and (LAW_SCOPE.search(query) or any(p.search(query) for p in SOURCE.values())):
        named = [key for key, pattern in SOURCE.items() if pattern.search(query)]
        return _route("latest_records", "LATEST_FROM_MONITORING", sources=named or list(SOURCE))
    if LEGAL.search(query):
        return _route("general_no_act", "NO_ACT_NAMED",
                      message="The question does not name an Act, so no Act's text is used to answer it.")
    return _route("outside_domain", "OUTSIDE_LEGAL_SCOPE",
                  message="This assistant answers questions about Indian Acts in its corpus and the official sources it monitors.")


def allowed_entries(frame: QuestionFrame, catalog: ActCatalog) -> list[str]:
    """The interpreted Act, the amending instruments recorded as amending it, and a named amending Act whose relation is recorded."""
    allowed = []
    if frame.principal:
        principal = frame.principal.entry_id
        allowed = [principal, *sorted({e for e, targets in catalog.relations.items() if principal in targets and e in catalog.entries})]
        allowed += sorted(alias for alias, canonical in CANONICAL.items() if canonical == principal)  # a duplicate copy of the same Act
    if frame.amending and not frame.relation_error and frame.amending.entry_id not in allowed:
        allowed.append(frame.amending.entry_id)
    return allowed


def close_matches(phrase: str, catalog: ActCatalog) -> list[Any]:
    """Corpus Acts that the name could mean: the same words inside a longer title, or a near spelling. Never a guess beyond that."""
    words = [t for t in _norm(phrase) if t not in {"act", "amendment"}]
    if not words:
        return []
    found: list[str] = []
    for name, entry in catalog.principals():
        entry = CANONICAL.get(entry, entry)
        title = [t for t in name if t != "act"]
        similar = difflib.SequenceMatcher(None, " ".join(words), " ".join(title)).ratio() >= CLOSE_MATCH
        contained = len(words) >= 1 and set(words) < set(title) and len(set(words)) * 2 >= len(set(title))
        if (similar or contained) and entry not in found:
            found.append(entry)
    return [catalog.ref(entry) for entry in found[:4]]


def _route(route: str, reason: str, *, acts=(), choices=(), allowed=(), **extra: Any) -> dict[str, Any]:
    return {"version": ROUTE_VERSION, "route": route, "response_type": RESPONSE_TYPES[route], "reason_code": reason,
            "interpreted_acts": [_act(ref) for ref in acts], "choices": [_act(ref) for ref in choices],
            "allowed_entry_ids": list(allowed), "rejected_candidates": [],
            **{k: ({p: [_act(r) for r in refs] for p, refs in v.items()} if k == "suggestions_by_phrase" else v) for k, v in extra.items()}}


def _act(ref: Any) -> dict[str, Any]:
    return {"entry_id": ref.entry_id, "name": ref.name, "year": ref.year, "kind": ref.kind}


RECORD_KINDS = {
    "act_amendment": "Act amendment (verified)",
    "commencement_notification": "Commencement notification",
    "unverified_candidate": "Possible amendment found by machine extraction (unverified)",
    "other_notice": "Other notice",
}


def record_kind(item: dict[str, Any]) -> str:
    """What a monitored record is. Only a review can verify an amendment; a title is enough only to call it a commencement notice."""
    from temporal_legal_drift.monitoring.commencement import is_commencement_subject

    if item.get("category") == "VERIFIED_AMENDMENT":
        return "act_amendment"
    if is_commencement_subject(str(item.get("title") or "")):
        return "commencement_notification"
    if item.get("category") == "POSSIBLE_AMENDMENT":
        return "unverified_candidate"
    return "other_notice"


def latest_records(feed: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    """The persisted monitoring feed limited to the sources asked about. "Latest" means latest observed within that scope."""
    items = [{**{k: item.get(k) for k in ("title", "source", "source_key", "published", "discovered_at", "last_checked_at", "official_url",
                                            "status", "status_label", "category", "candidate_targets")},
              "record_kind": (kind := record_kind(item)), "record_kind_label": RECORD_KINDS[kind]}
             for item in feed.get("items", []) if item.get("source_key") in sources]
    health = [{k: s.get(k) for k in ("source_key", "source", "state", "detail", "last_success_at", "next_eligible_at")}
              for s in feed.get("sources", []) if s.get("source_key") in sources]
    return {"version": "latest-records-v1", "sources_asked": sources, "items": items, "sources": health,
            "scope": feed.get("scope"), "note": feed.get("note"), "generated_at": feed.get("generated_at"),
            "fetched_for_this_question": False, "legal_effect_claimed": False}
