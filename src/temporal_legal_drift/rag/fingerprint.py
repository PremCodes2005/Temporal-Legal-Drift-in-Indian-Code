"""Legal Change Fingerprint: wording drift, rule drift and outcome drift (legal-change-fingerprint-v1).

docs/methodology/legal_change_fingerprint.v1.md and ADR 0015 define the method; the weights live in
configs/metrics/wording_drift.v1.json and configs/metrics/rule_drift.v1.json. Every component carries its
evidence, transformation version, uncertainty and abstention reason; a missing component is null, never 0.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from .metrics import calculate_drift_metrics
from .versions import VERSION_CLAIMS

FINGERPRINT_VERSION = "legal-change-fingerprint-v1.1"  # rule-drift-v1.1; explicit limit kinds
CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs/metrics"
MARKER = re.compile(r"(\d+)\[([^\]]{1,800})\]")
FOOTNOTES = re.compile(r"\s+\d+\.\s+(?:Subs|Ins|Omitted|Added)\.", re.I)
# A footnote entry, wherever a page break placed it inside the clause, and page furniture.
FOOTNOTE_ENTRY = re.compile(r"(?:\*|\b\d{1,2}\.)\s*(?:Subs|Ins|Omitted|Added|Rep)\.\s(?:(?!\b\d{1,2}\.\s*(?:Subs|Ins|Omitted|Added|Rep)\.).){0,400}?"
                            r"(?:\(w\.e\.f\.\s*[\d-]+\)\.?|[”‖\"]\s*\.(?=\s|$))", re.I)
FURNITURE = re.compile(r"\bIndiaCode\s+\d+\b|\bIndia\s*Code\s+\d+\b")


def strip_footnotes(text: str) -> str:
    return " ".join(FURNITURE.sub(" ", FOOTNOTE_ENTRY.sub(" ", " ".join(str(text or "").split()))).split())
TOKEN = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?")


def _config(name: str) -> dict[str, Any]:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


def _component(state: str, *, value: float | None = None, label: str | None = None, summary: str, reason: str,
               next_action: str | None = None, method: str, evidence_ids: list[str] | None = None, details: dict[str, Any] | None = None,
               needs: list[dict[str, Any]] | None = None, uncertainty: list[str] | None = None, limit_kind: str | None = None) -> dict[str, Any]:
    from .determinations import limit_for

    kind = limit_kind or ("method" if "unclassified_change" in (uncertainty or []) else None)
    return {"state": state, "value": value, "label": label, "summary": summary, "reason": reason, "next_action": next_action,
            "method": method, "evidence_ids": evidence_ids or [], "details": details or {}, "needs": needs or [],
            "uncertainty": uncertainty or [], "limit": limit_for(state, reason, kind), "legal_validation": "UNVERIFIED"}


# ---------------- clauses ----------------
def clean_clause(text: str) -> str:
    """Section text without its footnotes and amendment markers; offsets in the response refer to this text."""
    body = MARKER.sub(lambda m: m.group(2), strip_footnotes(text))
    return re.sub(r"(?<!\w)\d+\[|\]", "", body).strip()


def clause_pair(versions: dict[str, Any]) -> dict[str, Any]:
    """Whole-clause before/after for the scored change, or the reason it cannot be built."""
    if versions["support_class"] not in VERSION_CLAIMS:
        return {"status": "UNSUPPORTED", "reason": versions["reason"]}
    items = {item["evidence_id"]: item for item in versions["evidence"]}
    if versions["support_class"] == "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION":
        after_item, before_item = items["E1"], items["E3"]
        return {"status": "OK", "derivation": "footnote_reconstruction", "before": clean_clause(before_item["text"]),
                "after": clean_clause(after_item["text"]), "before_evidence": [before_item["evidence_id"], "E2"],
                "after_evidence": [after_item["evidence_id"]],
                "before_kind": "derived: earlier wording reconstructed from the India Code footnote",
                "after_kind": "verbatim: current consolidated text"}
    consolidated = next((item for item in versions["evidence"] if item["role"] == "current_consolidated_text"), None)
    if consolidated is None:
        return {"status": "INCOMPLETE", "reason": "No consolidated clause text corroborates this change, so the whole clause cannot be compared."}
    raw = strip_footnotes(consolidated["text"])
    before_words, after_words = str(versions["before"]["text"]), str(versions["after"]["text"])
    norm = lambda t: " ".join(TOKEN.findall(t.casefold()))  # noqa: E731
    markers = [m for m in MARKER.finditer(raw) if norm(m.group(2)) == norm(after_words)]
    if len(markers) > 1:  # the same words amended in several places: use the sub-section the instruction names
        instruction = next((item["text"] for item in versions["evidence"] if item["role"] == "amendment_instruction"), "")
        named = re.search(r"sub-?\s?section\s*\(\s*(\d+[A-Z]?)\s*\)", instruction, re.I)
        if named:
            starts = {m.group(1): m.start() for m in re.finditer(r"\((\d+[A-Z]?)\)\s", raw)}
            begin = starts.get(named.group(1))
            later = sorted(p for p in starts.values() if begin is not None and p > begin)
            end = later[0] if later else len(raw)
            markers = [m for m in markers if begin is not None and begin <= m.start() < end]
    if len(markers) == 1:
        m = markers[0]
        derived = raw[:m.start()] + before_words + raw[m.end():]
    else:
        plain = clean_clause(raw)
        hits = [h.start() for h in re.finditer(re.escape(" ".join(after_words.split())), plain)] if after_words.strip() else []
        if len(hits) != 1:
            return {"status": "INCOMPLETE", "reason": "The amended words could not be located exactly once in the consolidated clause, "
                                                      "so the earlier clause cannot be rebuilt reliably."}
        derived = plain[:hits[0]] + before_words + plain[hits[0] + len(" ".join(after_words.split())):]
    before, after = clean_clause(derived), clean_clause(raw)
    if not re.match(r"\s*\(?\d+[A-Z]{0,3}\)?\.?", after) or "…" in after:
        return {"status": "INCOMPLETE", "reason": "The consolidated clause text is truncated, so the before and after clauses would be incomplete."}
    return {"status": "OK", "derivation": "revert_this_amendment_in_current_text", "before": before, "after": after,
            "before_evidence": [consolidated["evidence_id"], "E1", "E2"], "after_evidence": [consolidated["evidence_id"]],
            "before_kind": "derived: today's clause with this amendment's words reverted (later amendments, if any, remain)",
            "after_kind": "verbatim: current consolidated text"}


def text_gate(versions: dict[str, Any], pair: dict[str, Any]) -> str | None:
    """Reason the texts must not be scored, or None."""
    from temporal_legal_drift.parsing.text_quality import line_reason

    if any(item.get("text_reliability") == "UNRELIABLE_TEXT_LAYER" for item in versions.get("evidence", [])):
        return "A cited source has a known unreliable text layer (OCR), so its wording is not scored as law."
    from temporal_legal_drift.parsing.text_quality import LEGACY_MARK

    for side in ("before", "after"):
        if line_reason(pair[side]):
            return f"The {side} clause contains text the quality gate rejects ({line_reason(pair[side]).lower().replace('_', ' ')})."
    # The amended words themselves must be clean: a few garbled tokens in a long clause stay under the clause-level ratio.
    for text in (str(versions["before"]["text"]), str(versions["after"]["text"])):
        if line_reason(text) or any(LEGACY_MARK.search(token) for token in text.split()):
            return "The amended words contain garbled OCR text, so they are not scored as law."
    return None


# ---------------- wording drift ----------------
def _normalise(text: str) -> str:
    text = re.sub(r"\b(\w+?)iz(e|ed|es|ing|ation|ations)\b", r"\1is\2", text.casefold())
    return " ".join(TOKEN.findall(text))


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    return [(_normalise(m.group(0)), m.start(), m.end()) for m in TOKEN.finditer(text)]


def changed_spans(before: str, after: str) -> list[dict[str, Any]]:
    """Added, removed and substituted spans with character offsets into the exact compared clauses."""
    a, b = _token_spans(before), _token_spans(after)
    spans = []
    for op, a0, a1, b0, b1 in SequenceMatcher(None, [t[0] for t in a], [t[0] for t in b], autojunk=False).get_opcodes():
        if op == "equal":
            continue
        start_a = a[a0][1] if a0 < len(a) else len(before)
        end_a = a[a1 - 1][2] if a1 > a0 else start_a
        start_b = b[b0][1] if b0 < len(b) else len(after)
        end_b = b[b1 - 1][2] if b1 > b0 else start_b
        operation = {"replace": "substituted", "delete": "removed", "insert": "added"}[op]
        spans.append({"operation": operation, "before_text": before[start_a:end_a], "after_text": after[start_b:end_b],
                      "before_offsets": [start_a, end_a], "after_offsets": [start_b, end_b]})
    return spans


def wording_drift(pair: dict[str, Any], embed: Callable[[str], list[float]]) -> dict[str, Any]:
    method = "wording-drift-v1"
    before, after = pair["before"], pair["after"]
    spans = changed_spans(before, after)
    details = {"before_clause": before, "after_clause": after, "before_kind": pair["before_kind"], "after_kind": pair["after_kind"],
               "derivation": pair["derivation"], "spans": spans, "normalisation": _config("wording_drift.v1.json")["normalisation_before_scoring"],
               "clause_sha256": {"before": sha256(before.encode()).hexdigest(), "after": sha256(after.encode()).hexdigest()}}
    ids = sorted(set(pair["before_evidence"] + pair["after_evidence"]))
    if _normalise(before) == _normalise(after):
        flag = "IDENTICAL" if before == after else "FORMATTING_ONLY"
        return _component("DETERMINED", value=0.0, label="0%", method=method, evidence_ids=ids, details={**details, "flag": flag},
                          summary="No wording change." if flag == "IDENTICAL" else "Only formatting, punctuation or spelling differs.",
                          reason="After normalisation the two clauses are the same words.")
    norm_before, norm_after = _normalise(before), _normalise(after)
    legacy = calculate_drift_metrics(norm_before, norm_after, pre_vector=embed(norm_before), post_vector=embed(norm_after))
    lexical, vector = legacy["lexical_drift_percent"], legacy["semantic_drift_percent"]
    weights = _config("wording_drift.v1.json")["weights"]
    if vector is None or lexical is None:
        return _component("INSUFFICIENT_EVIDENCE", method=method, evidence_ids=ids, details=details,
                          summary="Wording drift could not be computed.", reason="A required input (lexical or feature-vector drift) is unavailable.",
                          next_action="Check that both clauses have text.")
    value = round(weights["lexical"] * lexical + weights["feature_vector"] * vector, 1)
    changed_words = sum(len(TOKEN.findall(s["after_text"])) + len(TOKEN.findall(s["before_text"])) for s in spans)
    total = max(1, len(TOKEN.findall(before)) + len(TOKEN.findall(after)))
    details.update({"inputs": {"lexical_drift_percent": lexical, "feature_vector_drift_percent": vector},
                    "weights": weights, "formula": "0.5 × lexical drift + 0.5 × feature-vector drift (on normalised clauses)",
                    "calculation": f"0.5 × {lexical} + 0.5 × {vector} = {value}",
                    "legacy_trace": legacy["calculation_trace"], "changed_word_share_percent": round(100 * changed_words / total, 1)})
    return _component("DETERMINED", value=value, label=f"{value}%", method=method, evidence_ids=ids, details=details,
                      summary=f"About {details['changed_word_share_percent']}% of the clause's words are in changed spans; "
                              f"the wording measures move {value}% (0 = same words, 100 = no shared wording).",
                      reason="Computed on the whole aligned clause from surface wording only; it says nothing about legal effect.")


# ---------------- rule drift ----------------
# Word boundaries matter: without them "extend" yields "ten" and "often" yields "ten".
WORD_NUM = r"(?:\b\d[\d,]*\b|\b(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|thousands|lakh|lakhs|crore|crores)\b[\s-]*)+)"
MONEY = re.compile(rf"(?:(not exceeding|not less than|up to|which may extend to|of)\s+)?({WORD_NUM})\s*(rupees|lakh rupees|crore rupees)?", re.I)
PERIOD = re.compile(rf"(?:(within|not later than|not exceeding|after|before|of|for|at least once in every|once in every|every)\s+)?({WORD_NUM})\s+(days?|weeks?|months?|years?|hours?)\b|\b(annually)\b", re.I)
EXCEPTION = re.compile(r"Provided\s+(?:further\s+|also\s+)?that\b[^.;:]{0,200}|\bexcept\b[^.;,]{0,120}|\bunless\b[^.;,]{0,120}|\bNotwithstanding\b[^,.;]{0,140}", re.I)
SCOPE = re.compile(r"\b(?:means|includes|applies to)\b[^.;]{0,160}", re.I)
PENALTY = re.compile(r"\bpunishable with[^.;]{0,160}|\bliable to (?:a )?penalty[^.;]{0,120}|\bfine which may extend to[^.;]{0,80}|\bimprisonment for a term[^.;]{0,120}", re.I)
PROHIBITION = re.compile(r"\bshall not\b|\bmust not\b|\bno\s+(?:\w+\s+){0,3}shall\b|\b(?:is|are|be)\s+prohibited\b", re.I)
OBLIGATION = re.compile(r"\b(?:shall|must)\b(?!\s+not)", re.I)
# "as may be decided" and "may be prescribed" delegate or describe; they do not grant a permission.
PERMISSION = re.compile(r"(?<!\bas\s)\bmay\b(?!\s+(?:be\s+(?:prescribed|notified|specified|decided|determined|made|required|necessary)|extend|not))|\bdiscretion\b", re.I)
# An actor is a person or body that can act; a certificate, a sum or an offence is not (rule-drift-v1.1).
ACTOR_HEAD = re.compile(r"\b(?:Central Government|State Government|Government|Commission|Court|court|Tribunal|tribunal|Authority|authority|Board|Committee|"
                        r"Controller|Registrar|Officer|officer|Magistrate|Collector|Commissioner|Inspector|Police|police|Director|director|Chairperson|"
                        r"Secretary|Member|member|person|party|parties|applicant|respondent|claimant|employer|employee|company|depositor|licensee|owner|"
                        r"driver|auditor|liquidator|creditor|debtor|arbitrator|mediator|trustee|bank|Bank|Council|Minister|insurer|assessee)s?\b")
LEAD_IN = re.compile(r"^\s*(?:\d+\s+)?(?:Provided\s+(?:further\s+|also\s+)?that\s+|it is hereby (?:declared|clarified) that\s+|and\s+|or\s+)", re.I)
FIELDS = ("modality", "penalty", "monetary_threshold", "deadline", "exception", "scope", "actor", "action")


def _sentences(text: str) -> list[tuple[int, int]]:
    bounds, start = [], 0
    for m in re.finditer(r"(?<=[.;:])\s+(?=\(|[A-Z0-9“\"])", text):
        bounds.append((start, m.start()))
        start = m.end()
    bounds.append((start, len(text)))
    return [b for b in bounds if text[b[0]:b[1]].strip()]


def _operative(text: str, offsets: list[list[int]]) -> list[tuple[int, int]]:
    sentences = _sentences(text)
    chosen = [s for s in sentences if any(s[0] <= o[0] <= s[1] or s[0] <= o[1] <= s[1] or (o[0] <= s[0] and o[1] >= s[1]) for o in offsets)]
    return chosen


def _value_norm(text: str) -> str:
    text = re.sub(r"\bProvided\s+(?:further|also)\s+that\b", "provided that", text, flags=re.I)
    return _normalise(text)


def _extract(text: str, sentences: list[tuple[int, int]]) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {name: [] for name in FIELDS}

    def add(name: str, value: str, start: int, end: int) -> None:
        if value.strip() and all(_value_norm(v["value"]) != _value_norm(value) for v in found[name]):
            found[name].append({"value": " ".join(value.split()), "span": [start, end]})

    for s0, s1 in sentences:
        sentence = text[s0:s1]
        for label, pattern in (("prohibition", PROHIBITION), ("obligation", OBLIGATION), ("permission", PERMISSION)):
            for m in pattern.finditer(sentence):
                if label == "obligation" and re.match(r"shall have the discretion", sentence[m.start():], re.I):
                    continue  # "shall have the discretion" grants a discretion, it does not impose a duty
                add("modality", f"{label}: {m.group(0).lower()}", s0 + m.start(), s0 + m.end())
        for m in PENALTY.finditer(sentence):
            add("penalty", m.group(0).strip(" ,"), s0 + m.start(), s0 + m.end())
        for m in MONEY.finditer(sentence):
            phrase = m.group(0).strip()
            if m.group(3) or re.search(r"lakh|crore|thousand|hundred", phrase, re.I):
                if not PERIOD.match(sentence[m.start():]):
                    add("monetary_threshold", phrase, s0 + m.start(), s0 + m.end())
        for m in PERIOD.finditer(sentence):
            add("deadline", m.group(0).strip(), s0 + m.start(), s0 + m.end())
        for m in EXCEPTION.finditer(sentence):
            add("exception", m.group(0).strip(" ,"), s0 + m.start(), s0 + m.end())
        for m in SCOPE.finditer(sentence):
            add("scope", m.group(0).strip(" ,"), s0 + m.start(), s0 + m.end())
        modal = re.search(r"\b(?:shall|must|may)\b", sentence)
        actor_found = False
        if modal:
            head = sentence[:modal.start()]
            cut = max(head.rfind(","), head.rfind("—"), head.rfind(")"))
            phrase = head[cut + 1:]
            lead = LEAD_IN.match(phrase)
            subject = phrase[lead.end():] if lead else phrase
            # The head noun decides: "the Certificate issued by such Certifying Authority" is a certificate, not an authority.
            head_np = re.split(r"\b(?:issued|made|granted|appointed|referred|authorised|seizing|by|under|of|which|who|whose|for|in respect)\b", subject, maxsplit=1)[0]
            matches = list(ACTOR_HEAD.finditer(head_np))
            match = matches[-1] if matches else None
            if match and 1 <= len(subject.split()) <= 14 and not re.match(r"\s*(?:nothing|no\s|it\b|such rules|all sums|offence)", subject, re.I):
                value = head_np[:match.end()].strip()  # the noun phrase up to its person or body head
                start = s0 + cut + 1 + (lead.end() if lead else 0) + subject.index(value)
                add("actor", value, start, start + len(value))
                actor_found = True
            rest_start = modal.end()
            rest = sentence[rest_start:]
            parenthetical = re.match(r"\s*,[^,]{1,120},", rest)  # "may, in the discretion of the court, be enforced"
            if parenthetical:
                rest_start += parenthetical.end()
                rest = sentence[rest_start:]
            verb = re.match(r"[\s,]*(?:(?:also|further|thereafter|then)\s+)?((?:not\s+)?(?:be\s+|have\s+)?[A-Za-z][A-Za-z’'-]*)", rest)
            if verb and actor_found:  # an action is only meaningful for a person or body that can act
                begin = s0 + rest_start + verb.start(1)
                add("action", verb.group(1), begin, begin + len(verb.group(1)))
    return found


def aligned_operative(before: str, after: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Sentences that differ, matched one-to-one across versions; an inserted sentence has no before counterpart."""
    left, right = _sentences(before), _sentences(after)
    key = lambda text, bounds: [_normalise(text[a:b]) for a, b in bounds]  # noqa: E731
    out_before, out_after = [], []
    for op, a0, a1, b0, b1 in SequenceMatcher(None, key(before, left), key(after, right), autojunk=False).get_opcodes():
        if op != "equal":
            out_before += left[a0:a1]
            out_after += right[b0:b1]
    return out_before, out_after


def rule_delta(pair: dict[str, Any], spans: list[dict[str, Any]]) -> dict[str, Any]:
    before_sentences, after_sentences = aligned_operative(pair["before"], pair["after"])
    before, after = _extract(pair["before"], before_sentences), _extract(pair["after"], after_sentences)
    weights = {name: spec["weight"] for name, spec in _config("rule_drift.v1.1.json")["fields"].items()}
    rows, uncertain = [], []
    for name in FIELDS:
        left = {_value_norm(v["value"]) for v in before[name]}
        right = {_value_norm(v["value"]) for v in after[name]}
        if name == "modality":  # compare the kind of modality, not the exact auxiliary word
            left, right = {v.split(":")[0] for v in left}, {v.split(":")[0] for v in right}
        operation = ("ABSENT" if not left and not right else "UNCHANGED" if left == right else
                     "ADDED" if not left else "REMOVED" if not right else "CHANGED")
        status = "EXTRACTED" if left or right else "NOT_PRESENT"
        if name in {"actor", "action"} and operation == "CHANGED" and not (before["modality"] and after["modality"]):
            status, operation = "UNCERTAIN", "UNCERTAIN"
        if status == "UNCERTAIN":
            uncertain.append(name)
        rows.append({"field": name, "weight": weights[name], "operation": operation, "status": status,
                     "before": [v["value"] for v in before[name]], "after": [v["value"] for v in after[name]],
                     "before_spans": [v["span"] for v in before[name]], "after_spans": [v["span"] for v in after[name]],
                     "contribution": weights[name] if operation in {"ADDED", "REMOVED", "CHANGED"} else 0})
    cue = re.compile(r"\b(?:shall|must|may|means|includes|punishable|liable|penalty|fine|imprisonment|provided|unless|except|notwithstanding)\b", re.I)
    # Operative = a changed sentence that carries a modal or rule cue; rewording a non-operative note is not flagged.
    operative_changed = any(cue.search(pair["before"][a:b]) for a, b in before_sentences) or any(cue.search(pair["after"][a:b]) for a, b in after_sentences)
    if operative_changed and not any(row["operation"] in {"ADDED", "REMOVED", "CHANGED"} for row in rows):
        # The operative wording changed but no supported field captured it (e.g. a count of nominees): never report a clean 0.
        uncertain.append("unclassified_change")
    return {"fields": rows, "uncertain_fields": uncertain,
            "operative_sentences": {"before": [list(s) for s in before_sentences], "after": [list(s) for s in after_sentences]}}


def validate_proposal(proposal: Any, pair: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep only LLM-proposed field values that fit the schema and are verbatim in the cited clause."""
    if not isinstance(proposal, dict) or not isinstance(proposal.get("fields"), list):
        return []
    valid = []
    for row in proposal["fields"]:
        if not isinstance(row, dict) or row.get("field") not in FIELDS:
            continue
        ok = True
        for side in ("before", "after"):
            value = row.get(side)
            if value is None:
                continue
            if not isinstance(value, str) or " ".join(value.split()) not in " ".join(pair[side].split()):
                ok = False
        if ok and (row.get("before") or row.get("after")):
            valid.append({"field": row["field"], "before": row.get("before"), "after": row.get("after")})
    return valid


def rule_drift(pair: dict[str, Any], spans: list[dict[str, Any]], proposer: Callable[[dict[str, Any]], Any] | None = None) -> dict[str, Any]:
    method = "rule-drift-v1.1"
    delta = rule_delta(pair, spans)
    llm = {"status": "NOT_USED"}
    if proposer is not None:
        try:
            accepted = validate_proposal(proposer(pair), pair)
            llm = {"status": "VALIDATED" if accepted else "REJECTED_OR_EMPTY", "accepted_fields": accepted}
            for row in delta["fields"]:
                proposed = next((p for p in accepted if p["field"] == row["field"]), None)
                if proposed and row["status"] != "EXTRACTED":  # only fills gaps the deterministic extractor left
                    row.update({"before": [proposed["before"]] if proposed["before"] else [], "after": [proposed["after"]] if proposed["after"] else [],
                                "status": "LLM_PROPOSED_VALIDATED"})
                    row["operation"] = ("ADDED" if not row["before"] else "REMOVED" if not row["after"] else
                                        "UNCHANGED" if _value_norm(row["before"][0]) == _value_norm(row["after"][0]) else "CHANGED")
                    row["contribution"] = row["weight"] if row["operation"] in {"ADDED", "REMOVED", "CHANGED"} else 0
        except Exception as error:  # model failure: the deterministic result stands
            llm = {"status": "FAILED_DETERMINISTIC_RESULT_USED", "error": type(error).__name__}
    score = sum(row["contribution"] for row in delta["fields"])
    changed = [row["field"] for row in delta["fields"] if row["contribution"]]
    details = {**delta, "weights_config": "configs/metrics/rule_drift.v1.1.json", "llm_proposal": llm,
               "formula": "sum of weights of fields that were added, removed or changed",
               "calculation": " + ".join(f"{row['field']} {row['weight']}" for row in delta["fields"] if row["contribution"]) + f" = {score}" if changed else "0 (no rule field changed)",
               "lower_bound": bool(delta["uncertain_fields"])}
    if not changed and "unclassified_change" in delta["uncertain_fields"]:
        # No supported field explains the change: no score is shown (a 0 or a guessed field would mislead).
        return _component("INSUFFICIENT_EVIDENCE", method=method, label="Not scored", evidence_ids=sorted(set(pair["before_evidence"] + pair["after_evidence"])),
                          details={**details, "unscored_reason": "UNSUPPORTED_RULE_FIELD"}, uncertainty=["unclassified_change"],
                          summary="These exact words changed, but the change is not one of the rule fields this method can extract.",
                          reason="Supported fields: duty, permission, prohibition, deadline, amount, penalty, exception, scope, a named person or body, "
                                 "and what they must do. A change outside these (for example a renamed term or a count) is not scored.",
                          next_action="Read the changed words under Compare & Evidence; queue the change for review if it matters.")
    elif not changed:  # noqa: SIM114
        summary = "No rule field changed: the edit does not alter who must do what, when, or with what consequence."
    else:
        summary = "Changed rule fields: " + ", ".join(f.replace("_", " ") for f in changed) + "."
    return _component("DETERMINED" if not delta["uncertain_fields"] else "PROVISIONAL", value=float(score),
                      label=f"{score}/100" + (" (lower bound)" if delta["uncertain_fields"] else ""),
                      method=method, evidence_ids=sorted(set(pair["before_evidence"] + pair["after_evidence"])), details=details,
                      summary=summary, uncertainty=[f"field_uncertain:{f}" for f in delta["uncertain_fields"]],
                      reason=("Weighted sum of changed rule fields (weights justified in rule_drift.v1.json); independent of wording size and of materiality."
                              + (" Uncertain fields are excluded, so this is a lower bound." if delta["uncertain_fields"] else "")))


# ---------------- outcome drift ----------------
def _number(phrase: str) -> int | None:
    from .determinations import _value

    match = re.search(WORD_NUM, phrase, re.I)
    return _value(match.group(0)) if match else None


def _period(values: list[str]) -> tuple[int, str] | None:
    for value in values:
        if re.search(r"annually", value, re.I):
            return 12, "months"
        m = PERIOD.search(value)
        if m and m.group(2):
            unit = m.group(3).lower().rstrip("s") + "s"
            number = _number(m.group(2))
            if number is not None:
                return (number * 12, "months") if unit == "years" else (number, unit)
    return None


def outcome_drift(delta_component: dict[str, Any] | None, scenario: dict[str, Any] | None, registry_comparison: dict[str, Any] | None,
                  applicability_note: str | None, applies: str | None = None) -> dict[str, Any]:
    method = "outcome-drift-v1"
    if delta_component is None:
        return _component("INSUFFICIENT_EVIDENCE", label="Cannot determine", method=method, summary="No supported rules to apply your facts to.",
                          reason="Outcome drift needs supported before and after rules; this question has none.",
                          next_action="Ask about a named section with a recorded amendment.")
    rows = {row["field"]: row for row in delta_component["details"]["fields"]}
    changed = [r for r in rows.values() if r["operation"] in {"ADDED", "REMOVED", "CHANGED"}]
    facts = (scenario or {}).get("facts") or {}
    evaluated, needs, not_evaluable = [], [], []

    def need(key: str, label: str, kind: str) -> None:
        if all(n["key"] != f"facts.{key}" for n in needs):
            needs.append({"key": f"facts.{key}", "label": label, "kind": kind})

    for row in changed:
        name = row["field"]
        if name == "deadline":
            before, after = _period(row["before"]), _period(row["after"])
            if not before or not after or before[1] != after[1]:
                not_evaluable.append(f"deadline (periods not comparable: {row['before']} → {row['after']})")
                continue
            key = f"elapsed_{before[1]}"
            if not isinstance(facts.get(key), (int, float)) or isinstance(facts.get(key), bool):
                need(key, f"How many {before[1]} have passed since the trigger event", "number")
                continue
            elapsed = facts[key]
            evaluated.append({"field": name, "decisive_fact": f"{key} = {elapsed}",
                              "before_answer": "within the time limit" if elapsed <= before[0] else "outside the time limit",
                              "after_answer": "within the time limit" if elapsed <= after[0] else "outside the time limit",
                              "rule_values": [before, after]})
        elif name == "monetary_threshold":
            before_v = [_number(v) for v in row["before"]]
            after_v = [_number(v) for v in row["after"]]
            if len(before_v) != 1 or len(after_v) != 1 or None in before_v + after_v:
                not_evaluable.append("monetary threshold (not a single comparable amount on each side)")
                continue
            if not isinstance(facts.get("amount"), (int, float)) or isinstance(facts.get("amount"), bool):
                need("amount", "The amount in your situation (rupees)", "number")
                continue
            amount, limit_b, limit_a = facts["amount"], before_v[0], after_v[0]
            evaluated.append({"field": name, "decisive_fact": f"amount = {amount}",
                              "before_answer": "within the limit" if amount <= limit_b else "above the limit",
                              "after_answer": "within the limit" if amount <= limit_a else "above the limit",
                              "rule_values": [limit_b, limit_a]})
        elif name == "exception" and row["operation"] in {"ADDED", "REMOVED"}:
            if not isinstance(facts.get("exception_conditions_met"), bool):
                need("exception_conditions_met", "Do the conditions of the exception apply to you?", "boolean")
                continue
            met = facts["exception_conditions_met"]
            exempt_after = met and row["operation"] == "ADDED"
            exempt_before = met and row["operation"] == "REMOVED"
            evaluated.append({"field": name, "decisive_fact": f"exception_conditions_met = {met}",
                              "before_answer": "covered by an exception" if exempt_before else "the main rule applies",
                              "after_answer": "covered by an exception" if exempt_after else "the main rule applies"})
        elif name == "penalty":
            if not isinstance(facts.get("contravention"), bool):
                need("contravention", "Was the provision contravened?", "boolean")
                continue
            if not facts["contravention"]:
                evaluated.append({"field": name, "decisive_fact": "contravention = False", "before_answer": "no penalty", "after_answer": "no penalty"})
            else:
                evaluated.append({"field": name, "decisive_fact": "contravention = True",
                                  "before_answer": "; ".join(row["before"]) or "no penalty stated", "after_answer": "; ".join(row["after"]) or "no penalty stated"})
        elif name == "modality":
            if not isinstance(facts.get("within_scope"), bool):
                need("within_scope", "Does your situation fall within this provision?", "boolean")
                continue
            if not facts["within_scope"]:
                evaluated.append({"field": name, "decisive_fact": "within_scope = False", "before_answer": "not applicable", "after_answer": "not applicable"})
            else:
                kind = lambda values: ", ".join(sorted({v.split(":")[0] for v in values})) or "no duty or permission stated"  # noqa: E731
                evaluated.append({"field": name, "decisive_fact": "within_scope = True", "before_answer": kind(row["before"]), "after_answer": kind(row["after"])})
        else:
            not_evaluable.append(f"{name.replace('_', ' ')} (needs a reviewed mapping of your situation to this field)")
    if registry_comparison and registry_comparison.get("state") == "COMPARED":
        first, last = registry_comparison["outcomes"][0], registry_comparison["outcomes"][-1]
        meets = lambda o: "does not meet the modelled rule" if o["risk_flag"] else "meets the modelled rule"  # noqa: E731
        decisive = ", ".join(sorted({o.get("decisive_fact") or "" for o in registry_comparison["outcomes"]} - {""})) or "your facts"
        evaluated.append({"field": "obligation_registry", "decisive_fact": decisive.replace("_", " ") + " under each version's modelled rule",
                          "before_answer": meets(first), "after_answer": meets(last), "assumes": registry_comparison.get("assumes")})

    elif registry_comparison and registry_comparison.get("state") == "NEEDS_FACTS":
        for item in registry_comparison["needs"]:
            if all(n["key"] != item["key"] for n in needs):
                needs.append(item)
    for row in evaluated:
        row["changed"] = row["before_answer"] != row["after_answer"]
    flips = [row for row in evaluated if row["changed"]]
    controlled = _controlled(rows)
    assumptions = [row["assumes"] for row in evaluated if row.get("assumes")]
    details = {"evaluated": evaluated, "not_evaluable": not_evaluable, "controlled_scenarios": controlled, "assumptions": assumptions,
               "compat_percent_definition": "100 = a supported answer flip for your facts; 0 = no supported flip; null = cannot determine",
               "applicability": applicability_note}
    condition = (" Which version governs your date is reported separately under applicability." if applicability_note else "")
    unscored = delta_component["details"].get("unscored_reason") == "UNSUPPORTED_RULE_FIELD"
    if not changed and not evaluated and not needs and unscored:
        # "Not scored" is not "no change": the changed words exist but are outside the supported fields.
        return _component("INSUFFICIENT_EVIDENCE", label="Cannot determine", method=method, details={**details, "compat_percent": None},
                          summary="Cannot tell whether your answer changes.", limit_kind="method",
                          reason="The change is not one of the supported rule fields, so it cannot be applied to your facts.",
                          next_action="Read the changed words under Compare & Evidence.")
    if not changed and not evaluated and not needs:
        return _component("DETERMINED", value=0.0, label="Unchanged", method=method, details={**details, "compat_percent": 0},
                          summary="No rule field changed, so no scenario answer can flip.", reason="The rule delta is empty." + condition)
    if flips:
        decisive = "; ".join(f"{r['field'].replace('_', ' ').capitalize()}: {r['before_answer']} → {r['after_answer']} ({_human_fact(r['decisive_fact'])})" for r in flips)
        yours = (f" For your date the {applies}-amendment answer would apply: "
                 + "; ".join(r[f"{applies}_answer"] for r in flips) + "." if applies else "")
        return _component("CONDITIONAL", value=100.0, label="Changed", method=method, details={**details, "compat_percent": 100, "applies": applies},
                          summary=f"Your answer changes. {decisive}.{yours}",
                          reason="Your facts were applied to the before and after rules; at least one supported answer flips."
                                 + (" Assumes " + "; ".join(assumptions) + "." if assumptions else "") + condition)
    if needs or not_evaluable:
        missing = ", ".join(n["label"] for n in needs) if needs else "; ".join(not_evaluable)
        return _component("NEEDS_FACTS" if needs else "INSUFFICIENT_EVIDENCE", label="Cannot determine", method=method,
                          details={**details, "compat_percent": None}, needs=needs,
                          summary="Cannot determine whether your answer changes yet.",
                          reason=f"Missing: {missing}.", next_action="Add the facts listed and re-run." if needs else "These fields need reviewed rules.")
    return _component("CONDITIONAL", value=0.0, label="Unchanged", method=method, details={**details, "compat_percent": 0},
                      summary="Your answer is the same under both versions: " + "; ".join(f"{r['field'].replace('_', ' ')}: {r['after_answer']}" for r in evaluated) + ".",
                      reason="Every changed rule field relevant to your facts was evaluated; none flips." + condition)


def _human_fact(fact: str) -> str:
    """'elapsed_months = 18' -> '18 months elapsed'; the raw form stays in the details table."""
    key, _, value = fact.partition(" = ")
    if key.startswith("elapsed_"):
        return f"{value} {key[8:]} elapsed"
    if key == "amount":
        return f"amount ₹{value}"
    if value in {"True", "False"}:
        return f"{key.replace('_', ' ')}: {'yes' if value == 'True' else 'no'}"
    return fact


def _controlled(rows: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Boundary scenarios generated from the rule values; a percentage with its denominator."""
    row = rows.get("deadline")
    if row and row["operation"] == "CHANGED":
        before, after = _period(row["before"]), _period(row["after"])
        if before and after and before[1] == after[1]:
            points = sorted({p for b in (before[0], after[0]) for p in (b - 1, b, b + 1) if p >= 0})
            flips = sum((p <= before[0]) != (p <= after[0]) for p in points)
            return {"field": "deadline", "unit": before[1], "values_tested": points, "flips": flips, "evaluated": len(points),
                    "percent": round(100 * flips / len(points), 1), "definition": "share of generated boundary scenarios whose on-time answer flips"}
    row = rows.get("monetary_threshold")
    if row and row["operation"] == "CHANGED" and len(row["before"]) == 1 and len(row["after"]) == 1:
        b, a = _number(row["before"][0]), _number(row["after"][0])
        if b and a:
            points = sorted({p for x in (b, a) for p in (x - 1, x, x + 1) if p >= 0})
            flips = sum((p <= b) != (p <= a) for p in points)
            return {"field": "monetary_threshold", "unit": "rupees", "values_tested": points, "flips": flips, "evaluated": len(points),
                    "percent": round(100 * flips / len(points), 1), "definition": "share of generated boundary amounts whose within-limit answer flips"}
    return None


# ---------------- assembly ----------------
def build_fingerprint(versions: dict[str, Any], scenario: dict[str, Any] | None, embed: Callable[[str], list[float]],
                      registry_comparison: dict[str, Any] | None, applicability_note: str | None,
                      proposer: Callable[[dict[str, Any]], Any] | None = None, asks_about_versions: bool = True,
                      applies: str | None = None) -> dict[str, Any]:
    if not asks_about_versions:
        out = lambda name: _component("OUT_OF_SCOPE", method=f"{name}-v1", summary="Not a question about a change.",  # noqa: E731
                                      reason="The fingerprint compares two versions of one provision; this question asks about the law as written.")
        return {"version": FINGERPRINT_VERSION, "wording_drift": out("wording-drift"), "rule_drift": out("rule-drift"),
                "outcome_drift": out("outcome-drift"), "note": "Three separate measures; never averaged."}
    pair = clause_pair(versions)
    gate = None if pair["status"] != "OK" else text_gate(versions, pair)
    if pair["status"] != "OK" or gate:
        # An unsupported pair is already explained in the answer; repeat only gate-specific reasons in full.
        reason = gate or ("No supported before/after versions; the answer above explains why." if pair["status"] == "UNSUPPORTED" else pair["reason"])
        action = ("Name the section and the amendment you mean." if pair["status"] == "UNSUPPORTED"
                  else "Check the official PDF; the wording cannot be scored reliably.")
        blocked = lambda name: _component("INSUFFICIENT_EVIDENCE", method=f"{name}-v1", summary="Not scored.", reason=reason,  # noqa: E731
                                          next_action=action, uncertainty=["evidence_gate_failed"])
        outcome = _component("INSUFFICIENT_EVIDENCE", label="Cannot determine", method="outcome-drift-v1", summary="Cannot determine.",
                             reason=reason, next_action=action, uncertainty=["evidence_gate_failed"])
        return {"version": FINGERPRINT_VERSION, "wording_drift": blocked("wording-drift"), "rule_drift": blocked("rule-drift"),
                "outcome_drift": outcome, "note": "Three separate measures; never averaged."}
    wording = wording_drift(pair, embed)
    rules = rule_drift(pair, wording["details"]["spans"], proposer)
    has_facts = bool(scenario and ((scenario.get("facts") or {}) or registry_comparison))
    outcome = outcome_drift(rules, scenario, registry_comparison, applicability_note, applies) if has_facts else _component(
        "NEEDS_FACTS", label="Cannot determine", method="outcome-drift-v1",
        summary="Add your situation to see whether your answer changes.",
        reason="Outcome drift applies your facts to both rules; no facts were given.",
        next_action="Add the facts asked for below and re-run.",
        needs=outcome_drift(rules, {"facts": {}}, registry_comparison, None)["needs"], details={"compat_percent": None}, limit_kind="facts")
    return {"version": FINGERPRINT_VERSION, "wording_drift": wording, "rule_drift": rules, "outcome_drift": outcome,
            "note": "Three separate measures; never averaged. Neither wording nor rule drift sets risk."}
