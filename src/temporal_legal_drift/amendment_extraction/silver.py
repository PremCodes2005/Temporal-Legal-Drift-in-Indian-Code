"""Evidence-constrained weak supervision for Phase 2 amendment records."""

from __future__ import annotations

import re
from collections import Counter
from hashlib import sha256

from .models import SilverAmendmentLabel


_OPERATION_CUES = {
    "INSERT": re.compile(r"\binsert(?:ed|ing|ion)?\b", re.I),
    "SUBSTITUTE": re.compile(r"\bsubstitut(?:e|ed|ing|ion)\b", re.I),
    "OMIT": re.compile(r"\bomit(?:ted|ting|ission)?\b", re.I),
    "REPEAL": re.compile(r"\brepeal(?:ed|ing)?\b", re.I),
    "RENUMBER": re.compile(r"\bre-?number(?:ed|ing)?\b", re.I),
    "REPLACE": re.compile(r"\breplac(?:e|ed|ing|ement)\b", re.I),
    "MODIFY": re.compile(r"\bamendment\s+of\b", re.I),
}
_STRUCTURAL_OPERATION_CUES = {
    "INSERT": re.compile(r"(?:words|figures|proviso|clause|section).{0,500}?shall\s+be\s+inserted", re.I | re.S),
    "SUBSTITUTE": re.compile(r"\bfor\s+the\s+.+?\bshall\s+be\s+substituted", re.I | re.S),
    "OMIT": re.compile(r"(?:words|figures|proviso|clause|section).{0,500}?shall\s+be\s+omitted", re.I | re.S),
    "REPEAL": re.compile(r"(?:section|provision|Act).{0,300}?shall\s+be\s+repealed", re.I | re.S),
    "RENUMBER": re.compile(r"(?:section|sub-section).{0,300}?shall\s+be\s+re-?numbered", re.I | re.S),
    "REPLACE": re.compile(r"\bshall\s+be\s+replaced\s+by\b", re.I),
    "MODIFY": re.compile(r"^\s*\d+[A-Z]?\.\s+Amendment\s+of\s+section", re.I),
}
_DIRECT_TARGET = re.compile(r"\b(?:in|of)\s+section\s+(\d{1,3}[A-Z]{0,3})\b", re.I)
_ANY_TARGET = re.compile(r"\bsection\s+(\d{1,3}[A-Z]{0,3})\b", re.I)


def build_silver_label(event: dict[str, object], document_text: str) -> SilverAmendmentLabel:
    evidence = str(event.get("evidence_text", ""))
    operation = str(event.get("operation", "UNKNOWN"))
    target = event.get("target_provision")
    target_number = str(target).split(":", 1)[-1] if target else None

    lexical_votes = _matching_operations(_OPERATION_CUES, evidence)
    structural_votes = _matching_operations(_STRUCTURAL_OPERATION_CUES, evidence)
    operation_consensus = (
        operation != "UNKNOWN"
        and lexical_votes == {operation}
        and (not structural_votes or structural_votes == {operation})
    )

    direct_targets = {match.group(1).upper() for match in _DIRECT_TARGET.finditer(evidence)}
    all_targets = {match.group(1).upper() for match in _ANY_TARGET.finditer(evidence)}
    target_consensus = bool(
        target_number
        and target_number.upper() in all_targets
        and (not direct_targets or target_number.upper() in direct_targets)
    )

    principal = event.get("principal_act")
    principal_supported = bool(principal and _normalise(str(principal)) in _normalise(document_text))
    old_text = event.get("old_text")
    new_text = event.get("new_text")
    old_required = operation in {"SUBSTITUTE", "REPLACE", "MODIFY", "REPEAL", "RENUMBER"}
    new_required = operation in {"INSERT", "SUBSTITUTE", "REPLACE", "MODIFY", "RENUMBER"}
    old_supported = _wording_supported(old_text, evidence, allow_empty=operation in {"OMIT", "REPEAL"})
    new_supported = _wording_supported(new_text, evidence, allow_empty=operation in {"OMIT", "REPEAL"})
    wording_complete = (not old_required or old_supported) and (not new_required or new_supported)
    effective_date = event.get("effective_date")
    date_supported = bool(
        effective_date
        and _date_components_supported(str(effective_date), document_text)
    )
    source_supported = bool(
        event.get("source_document")
        and len(str(event.get("source_sha256", ""))) == 64
        and evidence.strip()
    )

    checks = {
        "source_evidence_present": source_supported,
        "principal_act_document_supported": principal_supported,
        "target_rule_agreement": target_consensus,
        "operation_rule_agreement": operation_consensus,
        "old_text_exact_support": old_supported,
        "new_text_exact_support": new_supported,
        "required_wording_complete": wording_complete,
        "effective_date_document_supported": date_supported,
    }
    field_status = {
        "principal_act": "ACCEPTED" if principal_supported else "ABSTAINED",
        "target_provision": "ACCEPTED" if target_consensus else "ABSTAINED",
        "operation": "ACCEPTED" if operation_consensus else "ABSTAINED",
        "old_text": _field_status(old_text, old_supported, old_required),
        "new_text": _field_status(new_text, new_supported, new_required),
        "effective_date": "ACCEPTED" if date_supported else "ABSTAINED",
    }
    core_accepted = source_supported and principal_supported and target_consensus and operation_consensus and wording_complete
    reasons = []
    if not principal_supported:
        reasons.append("principal_act_not_independently_supported")
    if not target_consensus:
        reasons.append("target_rule_disagreement")
    if not operation_consensus:
        reasons.append("operation_rule_disagreement")
    if not wording_complete:
        reasons.append("required_wording_not_exactly_supported")
    if effective_date and not date_supported:
        reasons.append("effective_date_not_independently_supported")

    applicable_checks = [source_supported, principal_supported, target_consensus, operation_consensus, wording_complete]
    if effective_date is not None:
        applicable_checks.append(date_supported)
    agreement = round(sum(applicable_checks) / len(applicable_checks), 4)
    status = "AUTO_ACCEPTED" if core_accepted else "ABSTAIN"
    tier = _tier(agreement, status)
    label_id = "silver_" + sha256(
        f"{event.get('amendment_id')}\n{agreement}\n{status}".encode()
    ).hexdigest()[:24]
    return SilverAmendmentLabel(
        label_id=label_id,
        amendment_id=str(event["amendment_id"]),
        source_document=str(event["source_document"]),
        principal_act=str(principal) if principal_supported else None,
        target_provision=str(target) if target_consensus else None,
        operation=operation if operation_consensus else None,
        old_text=str(old_text) if old_text is not None and old_supported else None,
        new_text=str(new_text) if new_text is not None and new_supported else None,
        effective_date=str(effective_date) if date_supported else None,
        field_status=field_status,
        validator_checks=checks,
        agreement_score=agreement,
        confidence_tier=tier,
        label_status=status,
        abstention_reasons=tuple(reasons),
        evidence_text=evidence,
        source_sha256=str(event["source_sha256"]),
    )


def silver_metrics(labels: list[dict[str, object]]) -> dict[str, object]:
    total = len(labels)
    accepted = [item for item in labels if item.get("label_status") == "AUTO_ACCEPTED"]
    abstained = [item for item in labels if item.get("label_status") == "ABSTAIN"]
    tiers = Counter(str(item.get("confidence_tier")) for item in labels)
    fields = ("principal_act", "target_provision", "operation", "old_text", "new_text", "effective_date")
    return {
        "label_count": total,
        "auto_accepted_count": len(accepted),
        "abstained_count": len(abstained),
        "auto_label_coverage": _rate(len(accepted), total),
        "abstention_rate": _rate(len(abstained), total),
        "confidence_tier_counts": {name: tiers.get(name, 0) for name in ("HIGH", "MEDIUM", "LOW", "ABSTAIN")},
        "field_acceptance": {
            field: _rate(
                sum(item.get("field_status", {}).get(field) in {"ACCEPTED", "NOT_APPLICABLE"} for item in labels),
                total,
            )
            for field in fields
        },
        "mean_agreement_score": round(
            sum(float(item.get("agreement_score", 0.0)) for item in labels) / total, 4
        ) if total else None,
        "accepted_exact_evidence_support_rate": _rate(
            sum(
                bool(item.get("validator_checks", {}).get("source_evidence_present"))
                and bool(item.get("validator_checks", {}).get("required_wording_complete"))
                for item in accepted
            ),
            len(accepted),
        ),
        "metric_interpretation": (
            "agreement and evidence-support metrics for machine-generated silver labels; "
            "not real-corpus legal accuracy"
        ),
    }


def _matching_operations(patterns: dict[str, re.Pattern[str]], text: str) -> set[str]:
    return {name for name, pattern in patterns.items() if pattern.search(text)}


def _wording_supported(value: object, evidence: str, *, allow_empty: bool) -> bool:
    if value is None:
        return False
    if value == "":
        return allow_empty
    return _normalise(str(value)) in _normalise(evidence)


def _field_status(value: object, supported: bool, required: bool) -> str:
    if supported:
        return "ACCEPTED"
    if not required and value is None:
        return "NOT_APPLICABLE"
    return "ABSTAINED"


def _normalise(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _date_components_supported(iso_date: str, text: str) -> bool:
    try:
        year, month, day = (int(value) for value in iso_date.split("-"))
    except (TypeError, ValueError):
        return False
    months = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )
    return bool(re.search(rf"\b{day}(?:st|nd|rd|th)?(?:\s+day\s+of)?\s+{months[month - 1]}\s*,?\s*{year}\b", text, re.I))


def _tier(score: float, status: str) -> str:
    if status == "ABSTAIN":
        return "ABSTAIN"
    if score >= 0.9:
        return "HIGH"
    if score >= 0.75:
        return "MEDIUM"
    return "LOW"


def _rate(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": round(100.0 * numerator / denominator, 2) if denominator else None,
    }
