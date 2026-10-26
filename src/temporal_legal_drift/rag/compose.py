"""Direct, evidence-linked answer text (answer-composition-v1).

The opening answer comes first and in plain language; then Before, After, What changed and Effect on the
question for comparisons, or a short summary for general questions. Every section lists the evidence IDs it
relies on; text that is derived or inferred says so. Generic mode is a shorter view of the SAME evidence.
Method details stay out of the answer (they live in the expandable score panel).
"""

from __future__ import annotations

import re
from typing import Any

from .question import QuestionFrame
from .versions import VERSION_CLAIMS

COMPOSITION_VERSION = "answer-composition-v3"  # v3: Act-only questions list sections to compare; v2: concise before/after, "Key change"
ROLE_LABELS = {
    "before_fragment": "Before — amendment fragment (only the words the amendment changed, not the full section)",
    "after_fragment": "After — amendment fragment (only the words the amendment changed, not the full section)",
    "reconstructed_earlier_wording": "Before — reconstructed from the India Code footnote (derived, not a verbatim historical text)",
    "current_consolidated_text": "After — current consolidated text (today's wording; not proven to be the text in force on a past date)",
}


def _quote(text: str, limit: int = 220) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _around(text: str, needle: str, width: int = 170) -> str:
    # India Code footnote markers ("1[twenty-one days]") are dropped from the short excerpt; the verbatim text stays in the evidence.
    flat = re.sub(r"(?<!\w)\d+\[([^\]]*)\]", r"\1", " ".join(str(text or "").split()))
    index = flat.casefold().find(str(needle or "").casefold()) if needle else -1
    if index < 0:
        return _quote(flat, 2 * width)
    start, end = max(0, index - width), min(len(flat), index + len(needle) + width)
    if start:
        start = flat.find(" ", start) + 1 or start  # whole words only
    if end < len(flat):
        end = flat.rfind(" ", index + len(needle), end) if flat.rfind(" ", index + len(needle), end) > 0 else end
    return ("…" if start else "") + flat[start:end].strip() + ("…" if end < len(flat) else "")


def _provision(frame: QuestionFrame) -> str:
    section = f"section {frame.sections[0]}" if frame.sections else "the provision"
    return f"{section} of the {frame.principal.name}" if frame.principal else section


def _amending_name(versions: dict[str, Any], catalog_names: dict[str, str]) -> str:
    entry = versions.get("amending_entry")
    if entry and entry in catalog_names:
        return catalog_names[entry]
    act = versions.get("footnote_act")
    return f"Act {act['number']} of {act['year']}" if act else "the amendment"


def compose_version_answer(frame: QuestionFrame, mode: str, versions: dict[str, Any], determinations: dict[str, Any],
                           catalog_names: dict[str, str], fingerprint: dict[str, Any] | None = None) -> dict[str, Any]:
    if versions["support_class"] not in VERSION_CLAIMS:
        return _abstention(frame, versions, catalog_names)
    sub = versions.get("substitution")
    before = sub["old"] if sub else versions["before"]["text"]
    after = sub["new"] if sub else versions["after"]["text"]
    provision, amending = _provision(frame), _amending_name(versions, catalog_names)
    change = determinations["answer_change"]
    operation = versions.get("operation")
    if operation == "INSERT" or not before.strip():
        opening = f"The {amending} inserted new words into {provision}: “{_quote(after)}”."
        what = f"Inserted: “{_quote(after)}”. There was no earlier wording at this point to replace."
    else:
        opening = f"The {amending} changed {provision}: “{_quote(before)}” was replaced by “{_quote(after)}”."
        what = f"Substituted “{_quote(before)}” with “{_quote(after)}”."
    if frame.question_type in {"quantity", "modal"} and change["state"] in {"DETERMINED", "CONDITIONAL"} and change.get("label"):
        verdict = "So the answer to your question changes" if change["label"] == "Changes" else "So the answer to your question is the same"
        opening += f" {verdict}" + (" (subject to the condition below)." if change["state"] == "CONDITIONAL" else ".")
    dated = versions.get("effective_date")
    if dated:
        opening += f" The amending Act came into force on {dated} (Act-wide)."
    elif versions.get("footnote_stated_date"):
        opening += f" The footnote states effect from {versions['footnote_stated_date']} (not verified as commencement)."

    items = {item["evidence_id"]: item for item in versions["evidence"]}
    before_item, after_item = items[versions["before"]["evidence_id"]], items[versions["after"]["evidence_id"]]
    sections = []
    if mode == "specific":
        before_text = ("— No words: this text was inserted by the amendment." if not before.strip()
                       else _around(before_item["text"], sub["old"], 80) if sub else f"“{before}”")
        after_text = _around(after_item["text"], sub["new"], 80) if sub else f"“{after}”"
        before_ids = [versions["before"]["evidence_id"]] + [i for i in items if items[i]["role"] in {"amendment_instruction", "substitution_footnote"}]
        after_ids = [versions["after"]["evidence_id"]] + [i for i in items if items[i]["role"] == "current_consolidated_text" and i != versions["after"]["evidence_id"]]
        sections += [
            {"id": "before", "title": "Before", "label": ROLE_LABELS.get(before_item["role"], before_item["role"]), "text": before_text,
             "evidence_ids": before_ids, "kind": "derived" if not before_item["verbatim"] else "evidence"},
            {"id": "after", "title": "After", "label": ROLE_LABELS.get(after_item["role"], after_item["role"]), "text": after_text,
             "evidence_ids": after_ids, "kind": "evidence" if after_item["verbatim"] else "derived"},
        ]
    caveats = []
    if versions.get("other_unreconstructed_footnotes"):
        caveats.append(f"{versions['other_unreconstructed_footnotes']} other amendment footnote(s) for this section could not be reconstructed, "
                       "so other wording in it may also have changed.")
    rule = (fingerprint or {}).get("rule_drift") or {}
    if rule.get("state") in {"DETERMINED", "PROVISIONAL"}:
        caveats.insert(0, rule["summary"])
    sections.append({"id": "what_changed", "title": "Key change", "text": what + (" " + " ".join(caveats) if caveats else ""),
                     "evidence_ids": [i for i in items if items[i]["role"] in {"amendment_instruction", "substitution_footnote"}] or list(items)[:1],
                     "kind": "evidence"})
    if change["state"] not in {"DETERMINED", "CONDITIONAL"}:
        # Nothing was applied to facts: the answer stays clean and Scenario & Impact explains what is needed.
        return {"version": COMPOSITION_VERSION, "direct_answer": opening, "sections": sections, "limitations": _limitations(versions)}
    effect = change["summary"] + (" " + change["reason"] if change["state"] == "CONDITIONAL" else "")
    sections.append({"id": "effect", "title": "Effect on this scenario" if change.get("method") == "outcome-drift-v1" else "Effect on your question",
                     "text": effect, "evidence_ids": change.get("evidence_ids", []),
                     "kind": "inference" if change["state"] != "DETERMINED" else "evidence"})
    return {"version": COMPOSITION_VERSION, "direct_answer": opening, "sections": sections, "limitations": _limitations(versions)}


def _limitations(versions: dict[str, Any]) -> list[str]:
    rows = []
    if versions["support_class"] == "GRAPH_TRANSITION_FRAGMENTS":
        rows.append("Before and after are amendment fragments, not complete historical sections.")
        if not versions.get("effective_date"):
            rows.append("No commencement date is recorded for this amendment, so which version applies on a given date is unresolved.")
    if versions["support_class"] == "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION":
        rows.append("The earlier wording is reconstructed from India Code's footnote; the current text is today's version, not proven for a past date.")
        if versions.get("relation_verification") == "RELATION_RECORDED_ACT_NUMBER_NOT_TEXT_VERIFIED":
            rows.append("The footnote's amending Act number could not be confirmed in the amending Act's own text.")
    rows.append("Machine-checked evidence; not legal advice and not independently legally validated.")
    return rows


def _abstention(frame: QuestionFrame, versions: dict[str, Any], catalog_names: dict[str, str]) -> dict[str, Any]:
    code = versions["reason_code"]
    provision = _provision(frame)
    openings = {
        "AMENDING_ACT_DOES_NOT_AMEND_PRINCIPAL": f"I can't compare versions of {provision} using that amendment: {versions['reason']}",
        "TRANSITION_NOT_CORROBORATED": f"I can't give a reliable before/after for {provision}. {versions['reason']}",
        "SEVERAL_CORROBORATED_CHANGES": f"Several recorded changes to {provision} fit your question, so I haven't picked one. {versions['reason']}",
        "SECTION_NOT_IDENTIFIED": f"Please name the section you mean. {versions['reason']}",
        "ACT_NOT_IDENTIFIED": versions["reason"],
    }
    opening = openings.get(code, f"I can't compare versions of {provision}: {versions['reason']}")
    found = versions.get("section_candidates")
    if code == "SECTION_NOT_IDENTIFIED" and found:
        return _act_overview(found)
    if versions.get("suggested_sections"):
        opening += " Sections that mention your topic: " + ", ".join(row["section"] for row in versions["suggested_sections"]) + "."
    sections = []  # the opening already states the reason
    if versions.get("suggested_sections"):
        listed = "; ".join(f"section {row['section']}" + (f" ({row['heading']})" if row["heading"] else "") for row in versions["suggested_sections"])
        sections.append({"id": "suggestions", "title": "Sections that mention your topic", "text": listed + ". Ask again naming one of them.",
                         "evidence_ids": [], "kind": "limitation"})
    if versions.get("candidates"):
        listed = "; ".join(f"{c.get('amending_entry') or '?'} ({c.get('operation') or '?'}, {c.get('validation_status', 'corroborated')})"
                           for c in versions["candidates"][:6])
        sections.append({"id": "candidates", "title": "What the corpus records", "text": listed, "evidence_ids": [], "kind": "limitation"})
    return {"version": COMPOSITION_VERSION, "direct_answer": opening, "sections": sections,
            "limitations": ["No version comparison is shown because its support could not be established."]}


STATUS_TEXT = {"SUPPORTED": "before/after available", "SEVERAL_CHANGES": "several changes; say which wording",
               "NOT_CORROBORATED": "change recorded but not corroborated; no comparison", "TEXT_UNRELIABLE": "change recorded; source text unreliable",
               "NO_RECORDED_CHANGE": "mentions your topic; no recorded change"}


def _act_overview(found: dict[str, Any]) -> dict[str, Any]:
    """An Act-only question: which sections can be compared, never a score for the whole Act."""
    act = found["act_name"]
    asked = f" made by the {found['amendment']}" if found.get("amendment") else f" made by a {found['amendment_year']} amendment" if found.get("amendment_year") else ""
    counts = found["counts"]
    supported = counts.get("SUPPORTED", 0)
    listed = [c for c in found["candidates"] if c["status"] == "SUPPORTED"][:4]
    if supported:
        examples = "; ".join(f"section {c['section']}" + (f" ({c['heading']})" if c.get("heading") else "") for c in listed)
        opening = (f"This corpus records changes{asked} to {supported} section{'s' if supported != 1 else ''} of the {act} that can be compared "
                   f"before and after, for example {examples}. Choose a section below to see its comparison.")
    else:
        others = counts.get("OTHER_AMENDMENT", 0)
        opening = (f"No recorded change{asked} to the {act} has a before/after comparison that passes this system's evidence checks."
                   + (f" {others} recorded change{'s' if others != 1 else ''} come{'s' if others == 1 else ''} from other amendments." if others else "")
                   + " Check the official text on India Code.")
    rows = "; ".join(f"section {c['section']}: {STATUS_TEXT.get(c['status'], c['status'].lower())}" for c in found["candidates"])
    sections = [{"id": "candidates", "title": "Sections you can choose", "text": rows or "None.", "evidence_ids": [], "kind": "limitation"}] if found["candidates"] else []
    return {"version": COMPOSITION_VERSION, "direct_answer": opening, "sections": sections,
            "limitations": [found["note"], "Not legal advice; verify on India Code."]}


def compose_general_answer(frame: QuestionFrame, mode: str, short_answer: str, key_points: list[str], evidence_ids: list[str]) -> dict[str, Any]:
    points = key_points[:5] if mode == "specific" else key_points[:3]
    opening = _quote(short_answer, 600 if mode == "specific" else 360)
    sections = [{"id": "key_points", "title": "Key points", "text": " ".join(f"• {_quote(p, 300)}" for p in points),
                 "evidence_ids": evidence_ids, "kind": "evidence"}] if points else []
    return {"version": COMPOSITION_VERSION, "direct_answer": opening, "sections": sections,
            "limitations": ["Summarises the cited excerpts only, not the whole Act.", "Not legal advice; verify on India Code."]}


def section_answer(text: str, terms: list[str], mode: str, act_name: str | None, section: str | None = None) -> str | None:
    """'Section N (heading) of the Act says: “…”' from the section's own most relevant sentences."""
    flat = " ".join(str(text or "").split())
    number = section or (re.match(r"\s*(\d+[A-Z]{0,3})\s*\.", flat) or [None, None])[1]
    if not number:
        return None
    head = re.match(rf"\s*{re.escape(number)}\s*\.\s*([^.—]{{3,90}})[.—]+\s*", flat, re.I)
    body = re.split(r"\s+\d+\.\s+(?:Subs|Ins|Omitted|Added)\.", flat[head.end():] if head else flat, maxsplit=1)[0]
    sentences = [s.strip() for s in re.split(r"(?<=[.;:])\s+(?=\(?[A-Za-z0-9])", body) if len(s.strip()) > 20]
    ranked = sorted(sentences, key=lambda s: -sum(t in s.casefold() for t in terms))
    chosen = [s for s in ranked[: 2 if mode == "specific" else 1] if any(t in s.casefold() for t in terms)] or sentences[:1]
    ordered = [s for s in sentences if s in chosen]
    quote = _quote(" ".join(ordered), 520 if mode == "specific" else 300)
    heading = re.sub(r"\d+\[|\]", "", head.group(1)).strip(" .—-") if head else ""  # outside the f-string: Python 3.11
    title = f" ({heading})" if heading else ""
    return f"Section {number}{title} of the {act_name or 'Act'} says: “{quote}”"


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text and not re.match(r"[A-Z]{2}", text) else text
