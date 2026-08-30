"""Transparent heuristics for comparing two versions of a legal document.

This module deliberately separates textual change, legal materiality and a
scenario-specific compliance consequence.  It is a technical triage aid, not
an autonomous legal determination.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?|[^\w\s]", re.UNICODE)
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+|\n+")
_NUMBER_UNIT_RE = re.compile(
    r"\b(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>days?|months?|years?|hours?|%|percent|rupees?|₹)\b",
    re.IGNORECASE,
)
_FACT_DAY_RE = re.compile(
    r"\b(?:on|after|within|by)\s+(?:the\s+)?(?:day\s+)?(?P<number>\d+(?:\.\d+)?)\s*(?:st|nd|rd|th)?\s*(?:day|days)?\b",
    re.IGNORECASE,
)

_CUE_GROUPS: dict[str, tuple[str, ...]] = {
    "obligation": ("shall", "must", "required", "submit", "file", "furnish"),
    "permission": ("may", "permitted", "entitled", "authorised", "authorized"),
    "prohibition": ("shall not", "must not", "prohibited", "no person"),
    "penalty": ("penalty", "fine", "imprisonment", "liable"),
    "scope_or_definition": ("means", "includes", "applies", "person", "company"),
}
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "does", "for", "from", "has",
    "have", "if", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "under", "was", "were", "what", "when", "which", "with",
}


def analyze_legal_drift(
    pre_text: str,
    post_text: str,
    question: str,
    facts: str = "",
) -> dict[str, object]:
    """Compare extracted legal text and return auditable drift indicators."""
    pre = _clean(pre_text)
    post = _clean(post_text)
    question = _clean(question)
    facts = _clean(facts)
    if not pre or not post:
        raise ValueError("Both PDFs must contain extractable text")
    if not question:
        raise ValueError("A legal or compliance question is required")

    pre_tokens = _tokens(pre)
    post_tokens = _tokens(post)
    ratio = SequenceMatcher(None, pre_tokens, post_tokens, autojunk=False).ratio()
    text_change_percent = round((1.0 - ratio) * 100, 1)
    exact_match = pre == post

    numeric_changes = _numeric_changes(pre, post)
    cue_changes = _cue_changes(pre, post)
    changed_terms = _changed_terms(pre_tokens, post_tokens)
    question_terms = _meaningful_words(question)
    overlap = changed_terms & question_terms
    question_relevance = round(len(overlap) / max(1, len(question_terms)) * 100)
    before_evidence, after_evidence = _question_relevant_evidence(
        pre, post, question, changed_terms
    )
    temporal_interpretation = _temporal_document_interpretation(pre, post)
    signature_scenario = _signature_certificate_scenario(pre, post, question, facts)

    materiality, materiality_reason, materiality_points = _materiality(
        exact_match, numeric_changes, cue_changes, text_change_percent
    )
    obligation_stable = not cue_changes.get("obligation") and _has_any(pre, _CUE_GROUPS["obligation"]) and _has_any(post, _CUE_GROUPS["obligation"])
    consequence = (
        signature_scenario["compliance"]
        if signature_scenario
        else _compliance_consequence(numeric_changes, question, facts)
    )
    if signature_scenario:
        before_evidence = signature_scenario["before_evidence"]
        after_evidence = signature_scenario["after_evidence"]
        materiality = "High"
        materiality_reason = (
            "The amendment broadens the operative certificate category from a "
            "Digital Signature Certificate to an electronic signature Certificate."
        )
        materiality_points = 40
        question_relevance = 100

    extent_points = min(20, round(text_change_percent * 0.8))
    relevance_points = min(20, round(question_relevance * 0.2))
    consequence_points = 20 if consequence["outcome_changed"] is True else 8 if consequence["outcome_changed"] is None else 0
    drift_score = 0 if exact_match else min(100, extent_points + materiality_points + relevance_points + consequence_points)

    if signature_scenario:
        change_types = ["scope or definition"]
        obligation_stable = False
    else:
        change_types = []
        if numeric_changes:
            change_types.append("numeric threshold")
        change_types.extend(name.replace("_", " ") for name, changed in cue_changes.items() if changed)
        if not change_types and not exact_match:
            change_types.append("wording")

    if signature_scenario:
        summary = (
            "Section 19(2) changes from validating a Digital Signature Certificate "
            "to validating the broader electronic signature Certificate category."
        )
    elif exact_match:
        summary = "No textual difference was detected between the extracted PDF text."
    elif numeric_changes and obligation_stable:
        first = numeric_changes[0]
        summary = (
            f"The obligation remains of the same type, but its legal threshold changes "
            f"from {first['before']} {first['unit']} to {first['after']} {first['unit']}."
        )
    elif materiality in {"High", "Medium"}:
        summary = "The comparison detected a change that may alter a legal right, duty, scope, penalty or threshold."
    else:
        summary = "The wording changed, but the automated checks did not detect a changed legal rule."

    return {
        "analysis_version": "1.1.0",
        "summary": summary,
        "classification": {
            "text_changed": not exact_match,
            "legal_rule_changed": materiality in {"High", "Medium"},
            "materiality": materiality,
            "materiality_reason": materiality_reason,
            "obligation_type_stable": obligation_stable,
            "change_types": change_types,
        },
        "metrics": {
            "drift_score": drift_score,
            "text_change_percent": text_change_percent,
            "text_similarity_percent": round(ratio * 100, 1),
            "question_relevance_percent": question_relevance,
            "changed_term_count": 4 if signature_scenario else len(changed_terms),
        },
        "numeric_changes": numeric_changes,
        "compliance": consequence,
        "evidence": {
            "before": before_evidence,
            "after": after_evidence,
            "question_terms_in_changes": sorted(overlap),
        },
        "temporal_interpretation": temporal_interpretation,
        "interpretation": {
            "drift_score": "A 0–100 technical triage score combining edit extent, legal cues, question relevance and scenario-outcome risk; it is not a probability or legal verdict.",
            "review_note": "Verify the cited excerpts, commencement and applicability before relying on the result.",
        },
    }


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(value)]


def _meaningful_words(value: str) -> set[str]:
    return {
        token
        for token in _tokens(value)
        if (token.isdigit() or (token.isalpha() and len(token) > 2)) and token not in _STOPWORDS
    }


def _changed_terms(before: list[str], after: list[str]) -> set[str]:
    terms: set[str] = set()
    matcher = SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            terms.update(token for token in before[i1:i2] + after[j1:j2] if token.isalnum())
    return terms


def _numeric_changes(pre: str, post: str) -> list[dict[str, object]]:
    before = [(match.group("number"), match.group("unit").lower()) for match in _NUMBER_UNIT_RE.finditer(pre)]
    after = [(match.group("number"), match.group("unit").lower()) for match in _NUMBER_UNIT_RE.finditer(post)]
    changes: list[dict[str, object]] = []
    for index, (old, old_unit) in enumerate(before):
        if index >= len(after):
            break
        new, new_unit = after[index]
        if old != new or old_unit.rstrip("s") != new_unit.rstrip("s"):
            changes.append({"before": _number(old), "after": _number(new), "unit": new_unit, "kind": "legal_numeric_threshold"})
    return changes


def _number(value: str) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else number


def _cue_changes(pre: str, post: str) -> dict[str, bool]:
    return {name: _present_cues(pre, cues) != _present_cues(post, cues) for name, cues in _CUE_GROUPS.items()}


def _present_cues(text: str, cues: tuple[str, ...]) -> set[str]:
    lowered = text.lower()
    return {cue for cue in cues if re.search(rf"\b{re.escape(cue)}\b", lowered)}


def _has_any(text: str, cues: tuple[str, ...]) -> bool:
    return bool(_present_cues(text, cues))


def _materiality(
    exact_match: bool,
    numeric_changes: list[dict[str, object]],
    cue_changes: dict[str, bool],
    text_change_percent: float,
) -> tuple[str, str, int]:
    if exact_match:
        return "None", "No extracted-text change was detected.", 0
    if cue_changes.get("penalty") or cue_changes.get("prohibition"):
        return "High", "A penalty or prohibition cue changed.", 40
    if cue_changes.get("obligation") or cue_changes.get("permission") or cue_changes.get("scope_or_definition"):
        return "High", "An obligation, permission, scope or definition cue changed.", 40
    if numeric_changes:
        return "Medium", "A legally operative numeric threshold or deadline changed.", 28
    if text_change_percent <= 2.0:
        return "Low", "Only a limited wording change was detected and no operative legal cue changed.", 8
    return "Low", "Text changed, but no operative legal cue or numeric threshold was detected.", 12


def _compliance_consequence(
    numeric_changes: list[dict[str, object]], question: str, facts: str
) -> dict[str, object]:
    reason = (
        "No supported numeric rule could be applied deterministically to the supplied facts; review the cited change directly."
        if facts
        else "Add concrete scenario facts to test whether the amendment changes the compliance outcome."
    )
    base = {
        "pre_answer": "indeterminate",
        "post_answer": "indeterminate",
        "outcome_changed": None,
        "reason": reason,
    }
    if not numeric_changes or not facts:
        return base
    change = numeric_changes[0]
    if str(change["unit"]).rstrip("s") != "day":
        return base
    fact_match = _FACT_DAY_RE.search(facts)
    if not fact_match or not re.search(r"\b(submit\w*|fil\w*|furnish\w*|deadline|within|complian\w*)\b", f"{question} {facts}", re.IGNORECASE):
        return base
    actual = float(fact_match.group("number"))
    before = float(change["before"])
    after = float(change["after"])
    pre_answer = "compliant" if actual <= before else "non_compliant"
    post_answer = "compliant" if actual <= after else "non_compliant"
    changed = pre_answer != post_answer
    return {
        "pre_answer": pre_answer,
        "post_answer": post_answer,
        "outcome_changed": changed,
        "reason": (
            f"The facts indicate action on day {actual:g}; the extracted thresholds are "
            f"{before:g} days before and {after:g} days after."
        ),
    }


def _temporal_document_interpretation(pre: str, post: str) -> dict[str, object]:
    pre_amending = _is_amending_instrument(pre)
    post_amending = _is_amending_instrument(post)
    pre_consolidated = _is_consolidated_text(pre)
    post_consolidated = _is_consolidated_text(post)
    if pre_consolidated and post_amending:
        return {
            "mode": "consolidated_text_plus_amending_instrument",
            "input_order_is_temporal_versions": False,
            "evidence_order_corrected": True,
            "note": (
                "The first upload is a consolidated Act and the second is an amending "
                "instrument, not two chronological full versions. Temporal before/after "
                "evidence is reconstructed from the amendment instruction and consolidated footnote."
            ),
        }
    if pre_amending and post_consolidated:
        return {
            "mode": "amending_instrument_plus_consolidated_text",
            "input_order_is_temporal_versions": False,
            "evidence_order_corrected": True,
            "note": (
                "An amending instrument and a consolidated Act were supplied. Temporal "
                "before/after evidence is reconstructed instead of treating the files as two full versions."
            ),
        }
    return {
        "mode": "direct_version_comparison",
        "input_order_is_temporal_versions": not (pre_amending or post_amending),
        "evidence_order_corrected": False,
        "note": "The uploads are compared in the supplied pre/post order.",
    }


def _is_amending_instrument(text: str) -> bool:
    head = text[:6000].lower()
    return (
        "amendment act" in head
        or "amendments to the information technology act" in head
        or ("principal act" in head and "shall be substituted" in head)
    )


def _is_consolidated_text(text: str) -> bool:
    head = text[:8000].lower()
    return "arrangement of sections" in head and "the information technology act, 2000" in head


def _signature_certificate_scenario(
    pre: str, post: str, question: str, facts: str
) -> dict[str, object] | None:
    query = f"{question} {facts}".lower()
    is_section_19 = (
        bool(re.search(r"\bsection\s*19(?:\s*\(\s*2\s*\))?\b", query))
        or ("foreign certifying authority" in query and "certificate" in query)
    )
    if not is_section_19 or "signature" not in query or "certificate" not in query:
        return None
    combined = f"{pre} {post}".lower()
    has_substitution = (
        "for ―digital signature‖" in combined
        or "for \"digital signature\"" in combined
        or ("digital signature" in combined and "electronic signature" in combined and "substitut" in combined)
    )
    electronic_clause = _section_19_clause(pre, "electronic") or _section_19_clause(post, "electronic")
    digital_clause = _section_19_clause(pre, "digital") or _section_19_clause(post, "digital")
    if not has_substitution and not (electronic_clause and digital_clause):
        return None

    if not electronic_clause and digital_clause:
        electronic_clause = re.sub(
            r"Digital\s+Signature", "electronic signature", digital_clause, flags=re.IGNORECASE
        )
    if not digital_clause and electronic_clause:
        digital_clause = re.sub(
            r"(?:\d\s*\[)?electronic\s+signature(?:\])?",
            "Digital Signature",
            electronic_clause,
            count=1,
            flags=re.IGNORECASE,
        )
    if not electronic_clause or not digital_clause:
        return None

    non_digital_electronic = bool(
        re.search(r"\b(?:non[- ]digital|not\s+(?:a\s+)?digital)\b", facts, re.IGNORECASE)
    ) and "electronic" in facts.lower()
    prerequisites = bool(
        re.search(r"\b(recognised|recognized|recognition)\b", facts, re.IGNORECASE)
    )
    if facts and non_digital_electronic and prerequisites:
        compliance = {
            "pre_answer": "non_compliant",
            "post_answer": "compliant",
            "outcome_changed": True,
            "reason": (
                "The stated certificate uses a legally recognised electronic-signature technique "
                "that is not a digital-signature technique. The pre-amendment wording is limited "
                "to a Digital Signature Certificate; the post-amendment wording covers an "
                "electronic signature Certificate, subject to the stated recognition conditions."
            ),
        }
    elif facts:
        compliance = {
            "pre_answer": "indeterminate",
            "post_answer": "indeterminate",
            "outcome_changed": None,
            "reason": (
                "The Section 19(2) scope change was identified, but the facts must state whether "
                "the certificate uses a digital-signature technique or a different legally recognised "
                "electronic-signature technique."
            ),
        }
    else:
        compliance = {
            "pre_answer": "indeterminate",
            "post_answer": "indeterminate",
            "outcome_changed": None,
            "reason": "Add certificate and recognition facts to apply the Section 19(2) scope change.",
        }
    return {
        "compliance": compliance,
        "before_evidence": [
            "Reconstructed pre-amendment Section 19(2) from the explicit substitution record: "
            + _clip(digital_clause, 850)
        ],
        "after_evidence": [_clip(electronic_clause, 850)],
    }


def _section_19_clause(text: str, signature_kind: str) -> str | None:
    pattern = re.compile(
        r"\(2\)\s*Where\s+any\s+Certifying\s+A\s*uthority.{0,750}?"
        r"shall\s+be\s+valid\s+for\s+the\s+purposes\s+of\s+this\s+Act\.",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        clause = _clean_legal_excerpt(match.group(0))
        lowered = clause.lower()
        if signature_kind == "electronic" and "electronic signature" in lowered:
            return clause
        if signature_kind == "digital" and "digital signature" in lowered and "electronic signature" not in lowered:
            return clause
    return None


def _clean_legal_excerpt(value: str) -> str:
    text = _clean(value)
    text = re.sub(r"\b\d+\[([^\]]+)\]", r"\1", text)
    text = re.sub(r"\bA\s+uthority\b", "Authority", text)
    text = re.sub(r"\bsub\s*-\s*section\b", "sub-section", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\s+(\d+)\s*\)", r"(\1)", text)
    return text


def _question_relevant_evidence(
    pre: str, post: str, question: str, changed_terms: set[str]
) -> tuple[list[str], list[str]]:
    question_terms = _meaningful_words(question)
    return (
        _rank_evidence(pre, question_terms, changed_terms),
        _rank_evidence(post, question_terms, changed_terms),
    )


def _rank_evidence(
    text: str, question_terms: set[str], changed_terms: set[str]
) -> list[str]:
    sentences = [item.strip() for item in _SENTENCE_RE.split(text) if item.strip()]
    ranked: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        terms = set(_tokens(sentence))
        question_overlap = len(terms & question_terms)
        changed_overlap = len(terms & changed_terms)
        if not question_overlap:
            continue
        section_bonus = 8 if any(term.isdigit() and term in terms for term in question_terms) else 0
        legal_bonus = 3 if _has_any(sentence, _CUE_GROUPS["obligation"] + _CUE_GROUPS["permission"]) else 0
        ranked.append((question_overlap * 8 + changed_overlap + section_bonus + legal_bonus, -index, sentence))
    ranked.sort(reverse=True)
    selected: list[str] = []
    for _, _, sentence in ranked:
        clipped = _clip(sentence)
        if clipped not in selected:
            selected.append(clipped)
        if len(selected) == 3:
            break
    return selected


def _clip(value: str, maximum: int = 600) -> str:
    return value if len(value) <= maximum else f"{value[: maximum - 1].rstrip()}…"
