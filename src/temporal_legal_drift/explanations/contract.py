"""Structured, evidence-bounded explanations over an orchestration trace (ADR 0005).

The explanation states only what the trace's validated stage outputs support;
every claim cites anchors present in the trace. An optional language model may
rephrase the claims, but its output passes the same validator or is discarded
with the fallback recorded. Nothing here is legal advice or legal validation.
"""

from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any, Callable

from temporal_legal_drift.jsonio import canonical_json_bytes

SCHEMA_VERSION = "structured-explanation-v1"
FIELDS = (
    "schema_version", "explanation_id", "correlation_id", "question", "provision", "temporal",
    "amendment", "materiality", "obligation", "risk", "claims", "citations", "uncertainty",
    "escalation", "generation", "legal_validation",
)


def build_explanation(trace: dict[str, Any]) -> dict[str, Any]:
    stages = trace["stages"]
    graph = stages["graph"].get("output") or {}
    materiality = stages["materiality"].get("output") or {}
    risk = stages["risk"].get("output") or {}
    citations = _citations(trace)
    anchors = [item["anchor_id"] for item in citations]
    claims: list[dict[str, Any]] = []
    uncertainty: list[str] = []

    if graph.get("status") == "FRAGMENT_SUPPORTED":
        claims.append({
            "text": (
                f"For {trace['case']['act']} section {trace['case']['section']} on {trace['case']['reference_date']}, "
                f"the graph returns an amendment-controlled fragment ({graph['fragment_state']}), "
                "not the complete consolidated provision."
            ),
            "anchors": anchors[:1],
        })
        if graph.get("valid_from"):
            claims.append({"text": f"The fragment is dated from {graph['valid_from']} on an Act-wide commencement basis.", "anchors": anchors[:1]})
    else:
        uncertainty.extend(str(reason) for reason in graph.get("abstention_reasons", []))
        claims.append({"text": "No supported version could be returned for this provision and date.", "anchors": []})
    uncertainty.append("applicability_not_determined_requires_scenario_facts_and_review")

    if materiality.get("status") == "SILVER_ASSESSED":
        claims.append({"text": f"Machine materiality triage (silver, not gold): {materiality['summary']}.", "anchors": anchors[:1]})
    else:
        uncertainty.append("materiality_not_assessed_for_this_transition")
    if risk:
        if risk.get("risk_level") is None:
            uncertainty.extend(str(item) for item in risk.get("uncertainty", []))
            claims.append({"text": "Compliance risk could not be determined from the available evidence (unknown, not zero).", "anchors": []})
        else:
            claims.append({
                "text": f"Under the selected obligation model, the conditional risk level is {risk['risk_level']} with urgency {risk['urgency']}.",
                "anchors": [item["anchor_id"] for item in citations if item["role"] in {"obligation", "temporal", "consequence"}][:2],
            })
            uncertainty.extend(str(item) for item in risk.get("uncertainty", []))
    unresolved = [name for name, stage in stages.items() if stage["status"] not in {"OK", "NOT_REQUESTED"}]
    explanation = {
        "schema_version": SCHEMA_VERSION,
        "explanation_id": "",
        "correlation_id": trace["correlation_id"],
        "question": trace["case"].get("question") or f"{trace['case']['act']} s.{trace['case']['section']} on {trace['case']['reference_date']}",
        "provision": {
            "act": trace["case"]["act"],
            "section": trace["case"]["section"],
            "version_scope": graph.get("version_scope"),
            "is_complete_consolidated_text": False,
            "transition_id": graph.get("transition_id"),
        },
        "temporal": {
            "reference_date": trace["case"]["reference_date"],
            "valid_from": graph.get("valid_from"),
            "valid_to": graph.get("valid_to"),
            "applicability_status": (stages["applicability"].get("output") or {}).get("status"),
        },
        "amendment": {
            "fragment_text": graph.get("text"),
            "validation_status": graph.get("validation_status"),
        } if graph.get("status") == "FRAGMENT_SUPPORTED" else None,
        "materiality": {"status": materiality.get("status", "NOT_ASSESSED"), "is_gold": False},
        "obligation": {
            "rule_id": risk.get("rule_id"), "obligation": risk.get("obligation"), "consequence": risk.get("consequence"),
        } if risk else None,
        "risk": {
            "status": risk.get("status"), "risk_level": risk.get("risk_level"), "urgency": risk.get("urgency"),
        } if risk else None,
        "claims": claims,
        "citations": citations,
        "uncertainty": list(dict.fromkeys(uncertainty)),
        "escalation": {
            "required": True,  # every output awaits review; legal validation is unavailable
            "reasons": [f"stage_{name}_{stages[name]['status'].lower()}" for name in unresolved] or ["legal_review_unavailable"],
        },
        "generation": {"method": "deterministic_template", "model": None, "fallback_reason": None, "raw_output": None},
        "legal_validation": "UNVERIFIED",
    }
    explanation["explanation_id"] = _explanation_id(explanation)
    return explanation


def narrate(
    explanation: dict[str, Any], trace: dict[str, Any], call_model: Callable[[list[dict[str, str]]], str], model: str
) -> dict[str, Any]:
    """Let a model rephrase the claims; keep the deterministic claims if its output is not valid."""
    allowed = [item["anchor_id"] for item in explanation["citations"]]
    messages = [
        {"role": "system", "content": (
            "Rephrase the supplied claims in plain English for a non-lawyer. Do not add facts, dates, versions, "
            "labels or legal conclusions. Every claim keeps exactly the anchors it was given. "
            'Return JSON {"claims": [{"text": str, "anchors": [str]}]} with the same number of claims.'
        )},
        {"role": "user", "content": json.dumps({"claims": explanation["claims"], "allowed_anchors": allowed}, ensure_ascii=False)},
    ]
    raw = None
    try:
        raw = call_model(messages)
        claims = json.loads(raw)["claims"]
        candidate = {**explanation, "claims": claims, "generation": {
            "method": "llm_constrained_rephrase", "model": model, "fallback_reason": None, "raw_output": raw}}
        candidate["explanation_id"] = _explanation_id(candidate)
        errors = validate_explanation(candidate, trace)
        if len(claims) != len(explanation["claims"]) or any(
            new.get("anchors") != old["anchors"] for new, old in zip(claims, explanation["claims"])
        ):
            errors.append("model changed the number of claims or their anchors")
        if errors:
            raise ValueError("; ".join(errors))
        return candidate
    except Exception as error:  # any failure keeps the deterministic, validated explanation
        fallback = {**explanation, "generation": {
            "method": "deterministic_template", "model": model,
            "fallback_reason": f"model output rejected: {type(error).__name__}: {str(error)[:200]}", "raw_output": raw}}
        fallback["explanation_id"] = _explanation_id(fallback)
        return fallback


def validate_explanation(explanation: dict[str, Any], trace: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if tuple(explanation) != FIELDS and set(explanation) != set(FIELDS):
        errors.append(f"fields must be exactly {FIELDS}")
        return errors
    if explanation["schema_version"] != SCHEMA_VERSION or explanation["legal_validation"] != "UNVERIFIED":
        errors.append("schema version or legal-validation status invalid")
    if explanation["correlation_id"] != trace["correlation_id"]:
        errors.append("explanation belongs to a different run")
    graph = trace["stages"]["graph"].get("output") or {}
    if explanation["provision"]["transition_id"] != graph.get("transition_id"):
        errors.append("provision version does not match the graph stage")
    if explanation["temporal"]["valid_from"] != graph.get("valid_from"):
        errors.append("date does not match the graph stage")
    if explanation["provision"]["is_complete_consolidated_text"] is not False:
        errors.append("a fragment must not be presented as a complete consolidated provision")
    risk = trace["stages"]["risk"].get("output") or {}
    if (explanation["risk"] or {}).get("risk_level") != risk.get("risk_level"):
        errors.append("risk level does not match the risk stage")
    expected = {item["anchor_id"]: item for item in _citations(trace)}
    for citation in explanation["citations"]:
        reference = expected.get(citation.get("anchor_id"))
        if reference is None or citation != reference:
            errors.append(f"citation {citation.get('anchor_id')} is not an exact trace anchor")
    known = {item["anchor_id"] for item in explanation["citations"]}
    for claim in explanation["claims"]:
        if not isinstance(claim.get("text"), str) or not claim["text"].strip():
            errors.append("empty claim")
        if not set(claim.get("anchors", [])) <= known:
            errors.append("claim cites an anchor that is not in the citations")
        for date in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", claim.get("text", "")):
            if date not in {trace["case"]["reference_date"], graph.get("valid_from"), graph.get("valid_to")}:
                errors.append(f"claim states an unsupported date {date}")
    if not explanation["escalation"]["required"]:
        errors.append("escalation must remain required while legal validation is unavailable")
    if explanation["explanation_id"] != _explanation_id(explanation):
        errors.append("explanation id does not match its content")
    return errors


def _citations(trace: dict[str, Any]) -> list[dict[str, Any]]:
    citations = []
    graph = trace["stages"]["graph"].get("output") or {}
    for evidence in graph.get("source_evidence", []):
        citations.append(_anchor("amendment_instruction", evidence.get("source_id"), evidence.get("source_url"),
                                 evidence.get("source_sha256"), evidence.get("page"), evidence.get("line"),
                                 str(evidence.get("exact_text") or "")[:400]))
    risk = trace["stages"]["risk"].get("output") or {}
    for evidence in risk.get("evidence", []):
        citations.append(_anchor(str(evidence["role"]), evidence.get("source_id"), None, evidence.get("source_sha256"),
                                 None, None, str(evidence.get("quote") or "")[:400], evidence.get("locator")))
    return citations


def _anchor(role: str, source_id: Any, url: Any, digest: Any, page: Any, line: Any, quote: str, locator: Any = None) -> dict[str, Any]:
    body = {"role": role, "source_id": source_id, "source_url": url, "source_sha256": digest,
            "page": page, "line": line, "locator": locator, "quote": quote}
    return {"anchor_id": "anc_" + sha256(canonical_json_bytes(body)).hexdigest()[:16], **body}


def _explanation_id(explanation: dict[str, Any]) -> str:
    body = {key: value for key, value in explanation.items() if key != "explanation_id"}
    return "exp_" + sha256(canonical_json_bytes(body)).hexdigest()[:24]
