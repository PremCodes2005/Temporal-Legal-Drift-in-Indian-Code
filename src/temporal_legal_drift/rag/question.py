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

QUESTION_FRAME_VERSION = "question-frame-v2"  # v2: every named Act is kept (other_acts, act_choices), lowercase names
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
    "pmla": "prevention-of-money-laundering-act-2002",
    "money laundering act": "prevention-of-money-laundering-act-2002",
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
ACT_WORDS = {"act", "code", "sanhita", "adhiniyam"}
# Words that end an Act name when reading backwards from "Act": question words, verbs and connectives, never part of a title.
LEAD = set("""what which who whom whose how why when where is are was were be been being does do did has have had can could may might must shall
should will would say says said tell me explain describe summarise summarize about under per by with from between versus vs compare comparison
change changes changed amend amended amends made make new latest recent recently i my we our you your this that these those into at as or not no
any all section sections s generally cover covers provide provides apply applies against also both than its their there""".split())
SOURCE_NAMES = ({"india"}, {"gazette"}, {"e", "gazette"}, {"egazette"})  # "India Code" and "the Gazette" are sources, not Acts


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
    other_acts: list[ActRef] = field(default_factory=list)  # further Acts named in the question, besides the principal
    act_choices: list[ActRef] = field(default_factory=list)  # one name that fits several corpus Acts: the user must choose

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.casefold()) if token not in STOPWORDS]


def _contains(haystack: list[str], needle: list[str]) -> bool:
    return _find(haystack, needle) is not None


def _find(haystack: list[str], needle: list[str]) -> tuple[int, int] | None:
    return next(((i, i + len(needle)) for i in range(len(haystack) - len(needle) + 1) if needle and haystack[i:i + len(needle)] == needle), None)


def _as_written(query: str, words: list[str]) -> str:
    """The name as the user typed it (case and small words kept)."""
    gap = r"[^a-z0-9]+(?:(?:" + "|".join(STOPWORDS) + r")[^a-z0-9]+)*"
    match = re.search(r"(?<![a-z0-9])" + gap.join(map(re.escape, words)) + r"(?![a-z0-9])", query, re.I)
    return match.group(0) if match else " ".join(words).title()


def act_phrases(tokens: list[str]) -> list[tuple[int, int]]:
    """Spans of Act-like names: the words before "Act"/"Code"/"Sanhita"/"Adhiniyam" back to a question word. Letter case is ignored."""
    spans = []
    for end, token in enumerate(tokens):
        if token not in ACT_WORDS:
            continue
        start = end
        while start > 0 and end - start < 8 and tokens[start - 1] not in LEAD | ACT_WORDS and not tokens[start - 1].isdigit():
            start -= 1
        if start < end and set(tokens[start:end]) not in SOURCE_NAMES:
            spans.append((start, end + 1))
    return spans


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


def parse_question(query: str, catalog: ActCatalog, *, reference_date: str | None = None, chosen: str | None = None) -> QuestionFrame:
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

    # Named amending Act: "<base> (Amendment) Act, YYYY" or "<base> Amendment Act YYYY"; <base> may also be a name of the Act it amends.
    masked = list(tokens)
    for entry, info in catalog.entries.items():
        if info["kind"] != "amending" or not info["year"]:
            continue
        targets = catalog.relations.get(entry, set())
        bases = [[t for t in name if t != "act"] for name in [_norm(info["base"])] + [n for n, principal in catalog.principals() if principal in targets]]
        patterns = [base + tail for base in bases if base for tail in (["amendment", "act", info["year"]], ["amendment", info["year"]])]
        span = next((hit for pattern in patterns if (hit := _find(tokens, pattern))), None)
        if span:
            frame.amending = catalog.ref(entry)
            masked[span[0]:span[1]] = ["#"] * (span[1] - span[0])
            break

    # Every other corpus name or alias in the question; a name inside a longer matched name is not a separate Act.
    found: dict[tuple[int, int], set[str]] = {}
    for name, entry in catalog.principals():
        for i in range(len(masked) - len(name) + 1):
            if masked[i:i + len(name)] == name:
                found.setdefault((i, i + len(name)), set()).add(CANONICAL.get(entry, entry))
    spans = sorted(span for span in found if not any(o != span and o[0] <= span[0] and span[1] <= o[1] for o in found))
    named: list[str] = []
    for span in spans:
        entries = sorted(found[span])
        if len(entries) > 1:  # e.g. two Representation of the People Acts: a stated year may decide, never a guess
            dated = [e for e in entries if catalog.entries[e]["year"] in years]
            entries = dated if len(dated) == 1 else entries
        if len(entries) > 1:
            frame.act_choices = [catalog.ref(e) for e in entries]
            frame.ambiguities.append("several Acts match the name used: " + ", ".join(entries))
        elif catalog.entries[entries[0]]["kind"] == "amending" and frame.amending is None:
            frame.amending = catalog.ref(entries[0])
        elif entries[0] not in named:
            named.append(entries[0])
    if named:
        frame.principal = catalog.ref(named[0])
        frame.other_acts = [catalog.ref(e) for e in named[1:]]
    resolved_spans = spans + [(i, i + 1) for i, t in enumerate(masked) if t == "#"]

    if chosen is not None:  # the user picked the Act (from a choice or a correction): it replaces whatever the name matched
        frame.principal = catalog.ref(CANONICAL.get(chosen, chosen))
        frame.other_acts, frame.act_choices, frame.ambiguities = [], [], []
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
        named = frame.amending.name if (frame.amending.year or "") in frame.amending.name else f"{frame.amending.name} {frame.amending.year}"
        frame.relation_error = f"{named} is not recorded as amending the {frame.principal.name} in this corpus."

    # An Act-like name (any letter case) that no corpus name or alias covers is reported, never replaced by another Act.
    for start, end in [] if chosen is not None else act_phrases(tokens):
        if not any(s < end and start < e for s, e in resolved_spans):
            frame.unresolved_act_phrases.append(_as_written(query, tokens[start:end]))

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
