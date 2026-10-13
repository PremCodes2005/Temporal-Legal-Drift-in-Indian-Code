"""Select the version evidence a question is about, with its provenance, or say why there is none.

Order of support (version-evidence-v1):
1. a strongly corroborated graph-v4 transition for the named Act and section (amendment-controlled
   fragments, with the verbatim amending instruction and the corroborating consolidated text);
2. a substitution footnote in the consolidated Act's own text for the named section (reconstruction);
3. otherwise an explicit reason: wrong amending Act, only weak candidates, several candidates, or nothing.
Nothing here is legal validation; fragments are not complete historical sections.
"""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any

from .question import QuestionFrame

VERSION_EVIDENCE_VERSION = "version-evidence-v1"
STRONG = "MACHINE_CROSS_SOURCE_CORROBORATED"
VERSION_CLAIMS = {"GRAPH_TRANSITION_FRAGMENTS", "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION"}
FOOTNOTE = re.compile(r"Subs\.\s*by\s*Act\s*(\d+)\s*of\s*(\d{4}),?\s*s\.\s*(\d+)", re.I)


def footnote_reconstruction(text: str, section: str) -> dict[str, Any] | None:
    """Earlier wording from the consolidated text's own substitution footnote, for the named section only."""
    current_matches = re.findall(r"\[([A-Za-z][A-Za-z ]{2,60})\]", text)
    old_matches = re.findall(r"\bfor\s+[\"“”―‖']?([A-Za-z][A-Za-z ]{2,60}?)[\"“”―‖']?\s*\(w\.e\.f\.", text, re.I)
    provision = re.split(r"\s+\d+\.\s+Subs\.", text, maxsplit=1, flags=re.I)[0]
    if not re.match(rf"\s*(?:section\s+)?{re.escape(section)}\s*\.", provision, re.I):
        return None
    for current in current_matches:
        current_clean = " ".join(current.split())
        for old in old_matches:
            old_clean = " ".join(old.split())
            if not set(current_clean.lower().split()) & set(old_clean.lower().split()):
                continue
            footnotes = text[len(provision):].strip()
            entries = _footnote_entries(footnotes)
            marker = re.search(rf"(\d+)\[{re.escape(current)}\]", provision)
            entry = entries.get(marker.group(1)) if marker else None
            if entry is None:
                continue  # the substituted words cannot be tied to a numbered footnote
            stated = re.search(r"w\.e\.f\.\s*([0-9]{1,2}-[0-9]{1,2}-[0-9]{4})", entry["text"])
            return {"reconstructed": re.sub(rf"\d*\[{re.escape(current)}\]", old_clean, provision, count=1),
                    "provision": provision, "old": old_clean, "new": current_clean, "footnote": entry["text"],
                    "footnote_number": marker.group(1), "footnote_act": entry["act"], "all_footnotes": footnotes,
                    "footnote_count": len(entries), "stated_date": stated.group(1) if stated else None}
    return None


def _footnote_entries(footnotes: str) -> dict[str, dict[str, Any]]:
    """Numbered footnotes with their amending Act; "ibid." inherits the previous footnote's Act."""
    parts = re.split(r"(?:^|\s)(\d+)\.\s+(?=Subs\.|Ins\.|Omitted|Added)", footnotes)
    entries: dict[str, dict[str, Any]] = {}
    previous = None
    for number, body in zip(parts[1::2], parts[2::2]):
        act = re.search(r"Act\s*(\d+)\s*of\s*(\d{4})", body, re.I)
        section = re.search(r"\bs\.\s*(\d+)", body)
        current = ({"number": act.group(1), "year": act.group(2)} if act else (previous if re.search(r"\bibid\b", body, re.I) else None))
        dated = re.search(r"\(w\.e\.f\.\s?[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}\)\.?", body)
        body = body[:dated.end()] if dated else body  # page furniture and the next section follow
        entries[number] = {"text": " ".join(body.split()), "act": {**current, "section": section.group(1) if section else None} if current else None}
        previous = current or previous
    return entries


class VersionSelector:
    def __init__(self, consumer: Any, index_chunks: list[dict[str, Any]], extraction_risk: dict[str, str | None],
                 amenders: dict[str, list[str]] | None = None) -> None:
        self.amenders = amenders or {}  # principal entry -> amending entries (catalog relations)
        self.consumer = consumer
        self.risk = extraction_risk
        self.meta: dict[str, dict[str, Any]] = {}
        self.sections: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.texts: dict[str, list[dict[str, Any]]] = {}
        for chunk in index_chunks:
            meta = chunk.get("metadata", {})
            entry = str(meta.get("entry_id") or "")
            self.meta.setdefault(entry, meta)
            if meta.get("source_kind") is None and str(meta.get("source_anchor", "")).startswith("pdf:page:") \
                    and int(re.search(r"page:(\d+)", meta["source_anchor"]).group(1)) <= 2:
                self.texts.setdefault(entry, []).append(chunk)  # opening pages carry the Act number
            if meta.get("source_kind") == "provision_version":
                for section in meta.get("primary_sections") or []:
                    self.sections.setdefault((entry, str(section).upper()), []).append(chunk)
        graph = consumer.graph if consumer is not None else None
        self.acts = {a["act_id"]: a for a in graph.acts} if graph else {}
        self.provisions = {p["provision_id"]: p for p in graph.provisions} if graph else {}
        self.events = {e["amendment_event_id"]: e for e in graph.amendment_events} if graph else {}
        self.versions = {v["version_id"]: v for v in graph.provision_versions} if graph else {}
        self.sources = {s["source_id"]: s for s in graph.legal_sources} if graph else {}
        self.transitions = list(graph.transitions) if graph else []

    def _entry_matches(self, entry: str, pattern: re.Pattern[str]) -> bool:
        return any(pattern.search(c["text"]) for c in self.texts.get(entry, ()))

    # ---------- evidence items ----------
    def _item(self, evidence_id: str, role: str, entry: str, text: str, *, page: int | None, line: int | None,
              verbatim: bool, scope: str, source_sha256: str | None = None) -> dict[str, Any]:
        meta = self.meta.get(entry, {})
        filename = meta.get("filename")
        return {"evidence_id": evidence_id, "role": role, "entry_id": entry, "act_name": meta.get("act_name"),
                "text": " ".join(str(text).split()), "page": page, "line": line, "verbatim": verbatim, "scope": scope,
                "source_sha256": source_sha256, "text_sha256": sha256(str(text).encode()).hexdigest(),
                "pdf_url": f"/corpus/{filename}#page={page}" if filename and page else None,
                "official_url": meta.get("source_url") or meta.get("official_portal_url"),
                "text_reliability": "UNRELIABLE_TEXT_LAYER" if self.risk.get(entry) else "NO_KNOWN_EXTRACTION_RISK"}

    def section_chunk(self, entry: str, section: str, contains: str | None = None) -> dict[str, Any] | None:
        chunks = self.sections.get((entry, section.upper()), [])
        heading = [c for c in chunks if re.match(rf"\s*{re.escape(section)}\s*\.", c["text"], re.I)]
        if contains:
            probe = " ".join(re.findall(r"[a-z0-9]+", contains.casefold()))[:60]
            exact = [c for c in chunks if probe and probe in " ".join(re.findall(r"[a-z0-9]+", c["text"].casefold()))]
            if exact:
                return exact[0]
        return (heading or chunks or [None])[0]

    def suggest_sections(self, entry: str, terms: list[str], limit: int = 5) -> list[dict[str, Any]]:
        """Sections of an Act whose own text mentions the question's topic words (headings first)."""
        rows = []
        for (owner, section), chunks in self.sections.items():
            if owner != entry or not terms:
                continue
            text = " ".join(chunks[0]["text"].split())
            heading = re.match(rf"\s*{re.escape(section)}\s*\.\s*([^.—]{{3,90}})", text, re.I)
            words = set(re.findall(r"[a-z0-9]+", text.casefold()))
            hits = sum(term in words for term in terms)
            if hits:
                in_heading = sum(term in (heading.group(1).casefold() if heading else "") for term in terms)
                rows.append((in_heading, hits, section, heading.group(1).strip(" .—-") if heading else None))
        rows.sort(key=lambda row: (-row[0], -row[1], len(row[2]), row[2]))
        return [{"section": section, "heading": heading} for _, _, section, heading in rows[:limit]]

    @staticmethod
    def _anchor(chunk: dict[str, Any] | None) -> tuple[int | None, int | None]:
        anchor = str((chunk or {}).get("metadata", {}).get("source_anchor") or "")
        page = re.search(r"page:(\d+)", anchor)
        line = re.search(r"line:(\d+)", anchor)
        return (int(page.group(1)) if page else None, int(line.group(1)) if line else None)

    # ---------- selection ----------
    def select(self, frame: QuestionFrame) -> dict[str, Any]:
        base = {"version": VERSION_EVIDENCE_VERSION, "evidence": [], "candidates": [], "transition_id": None,
                "amendment_event_id": None, "operation": None, "provision_path": None, "effective_date": None,
                "date_basis": None, "relation_verification": None, "before": None, "after": None}
        if frame.relation_error:
            return {**base, "support_class": "RELATION_MISMATCH", "reason_code": "AMENDING_ACT_DOES_NOT_AMEND_PRINCIPAL", "reason": frame.relation_error}
        if not frame.principal:
            return {**base, "support_class": "NO_SUPPORTED_VERSION", "reason_code": "ACT_NOT_IDENTIFIED",
                    "reason": "Name the Act (and section) to compare its versions."}
        if not frame.sections:
            return {**base, "support_class": "NO_SUPPORTED_VERSION", "reason_code": "SECTION_NOT_IDENTIFIED",
                    "reason": f"Name a section of the {frame.principal.name} to compare its versions; whole Acts are not compared."}
        section = frame.sections[0]
        principal = frame.principal.entry_id
        source_entry = {sid: s["corpus_entry_id"] for sid, s in self.sources.items()}
        rows = []
        for transition in self.transitions:
            provision = self.provisions.get(transition["target_provision_id"]) or {}
            act = self.acts.get(provision.get("act_id")) or {}
            if act.get("corpus_entry_id") != principal or str(provision.get("section", "")).upper() != section.upper():
                continue
            event = self.events[transition["amendment_event_id"]]
            amending = source_entry.get(event["evidence"]["source_id"])
            rows.append((transition, event, provision, amending))
        named = [row for row in rows if (not frame.amending or row[3] == frame.amending.entry_id)
                 and (not frame.amendment_year or (row[3] or "").endswith(frame.amendment_year))]
        strong = [row for row in named if row[0]["validation_status"] == STRONG]
        if strong:
            return self._graph(base, frame, strong)
        footnote = self._footnote(base, frame, section)
        if footnote:
            return footnote
        candidates = [{"transition_id": t["transition_id"], "validation_status": t["validation_status"], "operation": t["operation"],
                       "amending_entry": amending} for t, _, _, amending in rows]
        if named:
            return {**base, "candidates": candidates, "support_class": "WEAK_TRANSITION_ONLY", "reason_code": "TRANSITION_NOT_CORROBORATED",
                    "reason": f"A machine-extracted change to section {section} exists but was not corroborated against a second source "
                              f"({', '.join(sorted({t['validation_status'] for t, *_ in named}))}); it is not presented as a version."}
        if rows:
            return {**base, "candidates": candidates, "support_class": "NO_SUPPORTED_VERSION", "reason_code": "NAMED_AMENDMENT_HAS_NO_RECORDED_CHANGE",
                    "reason": f"No recorded change to section {section} comes from the amendment named; other amendments do: "
                              + ", ".join(sorted({c['amending_entry'] or '?' for c in candidates})) + "."}
        amenders = sorted(entry for entry in {row[3] for row in rows} if entry)
        return {**base, "support_class": "NO_SUPPORTED_VERSION", "reason_code": "NO_RECORDED_CHANGE_FOR_SECTION",
                "reason": f"The corpus records no amendment of section {section} of the {frame.principal.name}"
                          + ("" if not amenders else f" (amending Acts present: {', '.join(amenders)})")
                          + ", and its consolidated text shows no substitution footnote for it."}

    def _graph(self, base: dict[str, Any], frame: QuestionFrame, strong: list[tuple]) -> dict[str, Any]:
        if len(strong) > 1:
            focus = set(frame.focus_terms)

            def overlap(row: tuple) -> int:
                text = " ".join([row[1]["evidence"]["exact_text"], self.versions[row[0]["after_version_id"]]["text"],
                                 self.versions[row[0]["before_version_id"]]["text"]]).casefold()
                return len(focus & set(re.findall(r"[a-z0-9]+", text)))

            ranked = sorted(strong, key=overlap, reverse=True)
            if overlap(ranked[0]) == 0 or overlap(ranked[0]) == overlap(ranked[1]):
                return {**base, "support_class": "AMBIGUOUS_CANDIDATES", "reason_code": "SEVERAL_CORROBORATED_CHANGES",
                        "candidates": [{"transition_id": t["transition_id"], "operation": t["operation"], "amending_entry": a,
                                        "after_text": self.versions[t["after_version_id"]]["text"][:160]} for t, _, _, a in strong],
                        "reason": f"{len(strong)} corroborated changes to this section fit the question; say which wording you mean."}
            strong = ranked[:1]
        transition, event, provision, amending = strong[0]
        before = self.versions[transition["before_version_id"]]
        after = self.versions[transition["after_version_id"]]
        evidence = event["evidence"]
        items = [
            self._item("E1", "amendment_instruction", amending, evidence["exact_text"], page=evidence.get("page"), line=evidence.get("line"),
                       verbatim=True, scope="AMENDING_INSTRUMENT_TEXT", source_sha256=evidence.get("source_sha256")),
            self._item("E2", "before_fragment", amending, before["text"], page=evidence.get("page"), line=evidence.get("line"),
                       verbatim=False, scope=before["text_scope"]),
            self._item("E3", "after_fragment", amending, after["text"], page=evidence.get("page"), line=evidence.get("line"),
                       verbatim=False, scope=after["text_scope"]),
        ]
        principal = frame.principal.entry_id
        for version_id in transition.get("corroborating_consolidated_version_ids") or []:
            consolidated = self.versions.get(version_id)
            if consolidated:
                chunk = self.section_chunk(principal, frame.sections[0], consolidated["text"])
                page, line = self._anchor(chunk)
                source = self.sources.get((consolidated.get("source_ids") or [None])[0]) or {}
                items.append(self._item("E4", "current_consolidated_text", principal, consolidated["text"], page=page, line=line,
                                        verbatim=True, scope="UNDATED_CONSOLIDATED_SNAPSHOT", source_sha256=source.get("sha256")))
                break
        return {**base, "support_class": "GRAPH_TRANSITION_FRAGMENTS", "reason_code": "CORROBORATED_TRANSITION",
                "reason": "A machine-checked change recorded in the temporal graph and corroborated against the consolidated Act.",
                "evidence": items, "transition_id": transition["transition_id"], "amendment_event_id": event["amendment_event_id"],
                "operation": transition["operation"], "provision_path": provision.get("canonical_path"),
                "effective_date": transition.get("effective_date"), "date_basis": transition.get("date_basis"),
                "amending_entry": amending, "relation_verification": "GRAPH_SOURCE_LINKED",
                "before": {"evidence_id": "E2", "role": "before_fragment", "text": before["text"]},
                "after": {"evidence_id": "E3", "role": "after_fragment", "text": after["text"]}}

    def _footnote(self, base: dict[str, Any], frame: QuestionFrame, section: str) -> dict[str, Any] | None:
        principal = frame.principal.entry_id
        for chunk in self.sections.get((principal, section.upper()), []):
            found = footnote_reconstruction(chunk["text"], section)
            if not found:
                continue
            page, line = self._anchor(chunk)
            act = found["footnote_act"]
            verification, amending = "FOOTNOTE_ONLY", frame.amending.entry_id if frame.amending else None
            if act:
                pattern = re.compile(rf"No\.?\s*{act['number']}\s*OF\s*{act['year']}", re.I)
                if amending:
                    verification = "ACT_NUMBER_TEXT_VERIFIED" if self._entry_matches(amending, pattern) else "RELATION_RECORDED_ACT_NUMBER_NOT_TEXT_VERIFIED"
                else:  # identify the amending Act only when its own text carries the footnote's Act number
                    found_entries = [entry for entry in self.amenders.get(principal, ()) if self._entry_matches(entry, pattern)]
                    if len(found_entries) == 1:
                        amending, verification = found_entries[0], "ACT_NUMBER_TEXT_VERIFIED"
            others = len(set(re.findall(r"(\d+)\[", found["provision"]))) - 1  # markers in this section's own text only
            items = [
                self._item("E1", "current_consolidated_text", principal, found["provision"], page=page, line=line, verbatim=True,
                           scope="CURRENT_CONSOLIDATED_SECTION"),
                self._item("E2", "substitution_footnote", principal, found["footnote"], page=page, line=line, verbatim=True,
                           scope="CONSOLIDATED_TEXT_FOOTNOTE"),
                self._item("E3", "reconstructed_earlier_wording", principal, found["reconstructed"], page=page, line=line, verbatim=False,
                           scope="DERIVED_FROM_FOOTNOTE"),
            ]
            return {**base, "support_class": "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION", "reason_code": "FOOTNOTE_SUBSTITUTION",
                    "reason": "Earlier wording reconstructed from the consolidated Act's own substitution footnote for this section.",
                    "evidence": items, "operation": "SUBSTITUTE", "provision_path": f"section:{section}",
                    "effective_date": None, "date_basis": "FOOTNOTE_STATED_DATE_UNVERIFIED" if found["stated_date"] else None,
                    "footnote_stated_date": found["stated_date"], "footnote_act": act, "relation_verification": verification,
                    "amending_entry": amending, "other_unreconstructed_footnotes": max(0, others),
                    "substitution": {"old": found["old"], "new": found["new"]},
                    "before": {"evidence_id": "E3", "role": "reconstructed_earlier_wording", "text": found["reconstructed"]},
                    "after": {"evidence_id": "E1", "role": "current_consolidated_text", "text": found["provision"]}}
        return None
