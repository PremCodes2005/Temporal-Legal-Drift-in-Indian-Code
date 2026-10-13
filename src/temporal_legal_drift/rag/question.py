"""Question frame: which Act, provision, amendment, date and question type the user asked about.

Act names resolve against the indexed corpus (one name per entry, from the index metadata) and the
amending -> principal relations recorded in graph v4 plus the curated relations config. Nothing is
guessed: an Act phrase that matches no corpus entry is reported as unresolved, and a named amending Act
that does not amend the named principal Act is a relation error.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from temporal_legal_drift.jsonio import load_json

QUESTION_FRAME_VERSION = "question-frame-v1"
STOPWORDS = {"the", "of", "and", "for", "in", "to", "a", "an", "on"}
# Common short forms; each maps to exactly one corpus principal entry.
ALIASES = {
    "information technology act": "it-act-2000-consolidated",
    "rti act": "right-to-information-act-2005",
    "cpc": "code-of-civil-procedure-1908",
    "ibc": "insolvency-bankruptcy-code-2016",
    "insolvency bankruptcy code": "insolvency-bankruptcy-code-2016",
    "mv act": "motor-vehicles-act-1988",
    "motor vehicle act": "motor-vehicles-act-1988",
    "sebi act": "securities-and-exchange-board-of-india-act-1992",
    "pocso act": "protection-of-children-from-sexual-offences-act-2012",
    # Former official title (renamed "...and Tissues..." in 2011).
    "transplantation human organs act": "transplantation-of-human-organs-and-tissues-act-1994",
    # An amending instrument asked about as the subject itself.
    "jan vishwas act": "jan-vishwas-amendment-of-provisions-act-2023",
}
# Duplicate corpus copies of the same Act: the graph's copy is canonical.
CANONICAL = {"competition-act-2002-679c33d2": "competition-act-2002",
             "prevention-money-laundering-act-2002": "prevention-of-money-laundering-act-2002"}
PRINCIPAL_TYPES = {"act_or_code", "consolidated_act"}

WHAT_CHANGED = re.compile(r"\b(?:compare|comparison|what\s+(?:has\s+|have\s+)?changed|how\s+(?:did|has|was|were)\b.{0,90}\b(?:change|amend)"
                          r"|before\s+and\s+after|difference|what\s+was\s+(?:omitted|inserted|substituted|added|removed))", re.I)
QUANTITY = re.compile(r"\b(?:what\s+(?:is\s+|was\s+|are\s+)?(?:the\s+)?(?:amount|fine|penalty|fee|deposit|term|period|time|limit|punishment|number)"
                      r"|how\s+(?:much|many|long|often)|maximum|minimum)\b", re.I)
MODAL = re.compile(r"\b(?:is|are|was|were)\b.{0,80}\b(?:discretionary|mandatory|compulsory|required|allowed|permitted|obligatory)\b"
                   r"|^\s*(?:can|may|must|shall|does|do|is|are)\b", re.I)
CHANGE_WORDS = re.compile(r"\b(?:amend(?:ed|ment)?|before|after|change[ds]?|compare|omitted|inserted|substituted)\b", re.I)
SECTION = re.compile(r"\bsections?\s+(\d+[A-Z]{0,3})\b", re.I)
ACT_PHRASE = re.compile(r"\b((?:[A-Z][\w’'()&-]*\s+(?:(?:and|of|the|for|in|on)\s+)?){1,9}(?:Act|Code|Sanhita|Adhiniyam))\b")


@dataclass(frozen=True)
class ActRef:
    entry_id: str
    name: str
    kind: str
    year: str | None


@dataclass
class QuestionFrame:
    query: str
    version: str = QUESTION_FRAME_VERSION
    question_type: str = "general"
    asks_about_versions: bool = False
    principal: ActRef | None = None
    amending: ActRef | None = None
    amendment_year: str | None = None
    sections: list[str] = field(default_factory=list)
    reference_date: str | None = None
    focus_terms: list[str] = field(default_factory=list)
    unresolved_act_phrases: list[str] = field(default_factory=list)
    relation_error: str | None = None
    ambiguities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.casefold()) if token not in STOPWORDS]


def _contains(haystack: list[str], needle: list[str]) -> bool:
    return bool(needle) and any(haystack[i:i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1))


class ActCatalog:
    """Corpus entries with their indexed Act names, and amending -> principal relations."""

    def __init__(self, entries: dict[str, dict[str, Any]], relations: dict[str, set[str]]) -> None:
        self.entries = entries
        self.relations = relations

    @classmethod
    def build(cls, root: Path, index_chunks: list[dict[str, Any]], graph: Any | None) -> "ActCatalog":
        entries: dict[str, dict[str, Any]] = {}
        for chunk in index_chunks:
            meta = chunk.get("metadata", {})
            entry = str(meta.get("entry_id") or "")
            if entry and entry not in entries and meta.get("source_kind") is None:
                name = str(meta.get("act_name") or "")
                year = str(meta.get("date") or "") or None
                base = re.sub(r"\s+\d{4}(?:\s+[0-9A-F]{8})?$", "", name).strip()
                entries[entry] = {"name": name, "base": base, "year": year, "kind": "principal" if meta.get("document_type") in PRINCIPAL_TYPES else "amending"}
        relations: dict[str, set[str]] = {}
        if graph is not None:
            act_entry = {a["act_id"]: a["corpus_entry_id"] for a in graph.acts}
            source_entry = {s["source_id"]: s["corpus_entry_id"] for s in graph.legal_sources}
            provisions = {p["provision_id"]: p for p in graph.provisions}
            for event in graph.amendment_events:
                provision = provisions.get(event.get("target_provision_id"))
                amending = source_entry.get(event["evidence"]["source_id"])
                if provision and amending:
                    relations.setdefault(amending, set()).add(CANONICAL.get(act_entry[provision["act_id"]], act_entry[provision["act_id"]]))
        config = root / "configs/versioning/instrument_relations.v1.json"
        if config.is_file():
            for amending, target in load_json(config).get("amending_instrument_targets", {}).items():
                relations.setdefault(str(amending), set()).add(str(target))
        return cls(entries, relations)

    def principals(self) -> list[tuple[list[str], str]]:
        rows = [(_norm(info["base"]), entry) for entry, info in self.entries.items() if info["kind"] == "principal" and entry not in CANONICAL]
        rows += [(_norm(alias), entry) for alias, entry in ALIASES.items()]
        return sorted(rows, key=lambda row: -len(row[0]))

    def ref(self, entry_id: str) -> ActRef:
        info = self.entries[entry_id]
        return ActRef(entry_id, info["name"], info["kind"], info["year"])


def parse_question(query: str, catalog: ActCatalog, *, reference_date: str | None = None) -> QuestionFrame:
    frame = QuestionFrame(query=query)
    tokens = _norm(query)
    frame.sections = list(dict.fromkeys(match.upper() for match in SECTION.findall(query)))
    if QUANTITY.search(query):
        frame.question_type = "quantity"
    elif MODAL.search(query):
        frame.question_type = "modal"
    elif WHAT_CHANGED.search(query):
        frame.question_type = "what_changed"
    years = re.findall(r"\b((?:19|20)\d{2})\b", query)

    # Named amending Act: "<base> (Amendment) Act, YYYY" or "<base> Amendment Act YYYY".
    for entry, info in catalog.entries.items():
        if info["kind"] != "amending" or not info["year"]:
            continue
        base = [t for t in _norm(info["base"]) if t != "act"]
        if base and (_contains(tokens, base + ["amendment", "act", info["year"]]) or _contains(tokens, base + ["amendment", info["year"]])):
            frame.amending = catalog.ref(entry)
            break

    # Principal Act: the longest corpus name or alias in the question that is not part of an amending-Act phrase.
    masked = list(tokens)
    if frame.amending:
        base = [t for t in _norm(catalog.entries[frame.amending.entry_id]["base"]) if t != "act"]
        for i in range(len(masked)):
            if masked[i:i + len(base) + 1] == base + ["amendment"]:
                masked[i:i + len(base) + 1] = ["#"] * (len(base) + 1)
    matches = []
    for name, entry in catalog.principals():
        if _contains(masked, name):
            matches.append((len(name), CANONICAL.get(entry, entry)))
    if matches:
        best = max(length for length, _ in matches)
        chosen = sorted({entry for length, entry in matches if length == best})
        if len(chosen) == 1:
            frame.principal = catalog.ref(chosen[0])
        else:
            frame.ambiguities.append("several Acts match the name used: " + ", ".join(chosen))

    if frame.principal is None and frame.amending is not None:
        targets = sorted(catalog.relations.get(frame.amending.entry_id, set()))
        if len(targets) == 1 and targets[0] in catalog.entries:
            frame.principal = catalog.ref(targets[0])
    if frame.principal and frame.amending is None:
        amending_years = {info["year"]: entry for entry, info in catalog.entries.items()
                          if info["kind"] == "amending" and frame.principal.entry_id in catalog.relations.get(entry, set())}
        stated = [year for year in years if year in amending_years and re.search(rf"{year}\s+amendment|amend\w*\s+(?:act\s+)?(?:of\s+)?{year}|in\s+{year}", query, re.I)]
        if stated:
            frame.amending = catalog.ref(amending_years[stated[0]])
        elif re.search(r"\b(?:\d{4}\s+)?amendment\b", query, re.I) and years:
            frame.amendment_year = years[-1]
    if frame.principal and frame.amending and frame.principal.entry_id not in catalog.relations.get(frame.amending.entry_id, set()):
        frame.relation_error = f"{frame.amending.name} {frame.amending.year} is not recorded as amending the {frame.principal.name}."

    named = {phrase.strip() for phrase in ACT_PHRASE.findall(query)}
    resolved_names = {_norm(catalog.entries[ref.entry_id]["base"]).__str__() for ref in (frame.principal, frame.amending) if ref}
    for phrase in sorted(named):
        words = [t for t in _norm(phrase) if t != "amendment"]
        covered = any(_contains(tokens, name) and set(name) <= set(words) | {"act"} for name, _ in catalog.principals()) \
            or (frame.amending is not None and set(words) <= set(_norm(frame.amending.name)) | {"act"})
        if not covered and len(words) >= 2:
            frame.unresolved_act_phrases.append(phrase)
    del resolved_names

    # A change question about an identified Act or provision; a missing section is reported, not guessed.
    frame.asks_about_versions = bool(CHANGE_WORDS.search(query)) and bool(frame.principal or frame.amending or frame.sections)
    frame.reference_date = reference_date or _date_in(query)
    entity = set()
    for ref in (frame.principal, frame.amending):
        if ref:
            entity |= set(_norm(ref.name))
    frame.focus_terms = [t for t in dict.fromkeys(tokens) if len(t) > 3 and t not in entity and not t.isdigit()
                         and t not in {"section", "after", "before", "amendment", "compare", "change", "changed", "under", "what", "does", "must",
                                       "about", "which", "says", "there", "their", "with", "from", "have", "without", "when", "where", "this", "that", "regarding"}]
    return frame


_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")


def _date_in(query: str) -> str | None:
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", query)
    if iso:
        return iso.group(1)
    written = re.search(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", query, re.I)
    if written:
        return f"{written.group(3)}-{_MONTHS.index(written.group(2).lower()) + 1:02d}-{int(written.group(1)):02d}"
    return None
