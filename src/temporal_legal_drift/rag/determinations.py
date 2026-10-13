"""Four independent determinations for one question (determinations-v1).

textual drift  - how far the compared wording moved (only for a supported, query-relevant pair);
materiality    - the versioned silver assessment, only on an exact provenance match;
answer change  - whether the answer to THIS question differs between the supported versions;
risk           - the existing risk engine, only when a registry rule covers the provision.

Each determination is independent: drift and materiality are never inputs to answer change or risk.
States: DETERMINED, PROVISIONAL, CONDITIONAL, NEEDS_FACTS, INSUFFICIENT_EVIDENCE, OUT_OF_SCOPE.
None of these is legal validation.
"""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from temporal_legal_drift.jsonio import canonical_json_bytes, load_json

from .question import QuestionFrame
from .versions import VERSION_CLAIMS

DETERMINATIONS_VERSION = "determinations-v4"  # v4: triage input normalises number words; v3: limit kinds, on-the-fly machine triage
MATERIALITY_ARTIFACT = "data/silver/materiality_reassessment.v2.5.json"
LLM_MATERIALITY_ARTIFACT = "data/assessments/materiality_llm_assessments.v2.json"
SCENARIO_FIELDS = {"reference_date", "organization_type", "industry", "jurisdiction", "activity", "facts"}


LIMIT_ACTIONS = {
    "facts": {"type": "add_facts", "label": "Add the facts asked for in Scenario & Impact"},
    "evidence": {"type": "verify_source", "label": "Check the official source on India Code; your facts cannot fill this gap"},
    "method": {"type": "queue_review", "label": "Read the changed words and queue them for expert review"},
    "not_applicable": {"type": "none", "label": "Nothing to do for this question"},
}


def limit_for(state: str, reason: str, kind: str | None = None) -> dict[str, Any] | None:
    """What is missing and the one action that helps: legal evidence, user facts, a method limit, or nothing applies."""
    kind = kind or {"NEEDS_FACTS": "facts", "INSUFFICIENT_EVIDENCE": "evidence", "OUT_OF_SCOPE": "not_applicable"}.get(state)
    return {"kind": kind, "message": reason, "action": LIMIT_ACTIONS[kind]} if kind else None


def _d(state: str, *, label: str | None = None, summary: str, reason: str, method: str | None = None,
       evidence_ids: list[str] | None = None, details: dict[str, Any] | None = None, needs: list[dict[str, Any]] | None = None,
       review_status: str = "UNREVIEWED", limit_kind: str | None = None) -> dict[str, Any]:
    return {"state": state, "label": label, "summary": summary, "reason": reason, "method": method,
            "evidence_ids": evidence_ids or [], "details": details or {}, "needs": needs or [], "review_status": review_status,
            "limit": limit_for(state, reason, limit_kind), "legal_validation": "UNVERIFIED"}


def validate_scenario(value: Any) -> dict[str, Any] | None:
    """Trust boundary for user-supplied facts: small, typed, no unknown fields."""
    if value in (None, {}):
        return None
    if not isinstance(value, dict) or set(value) - SCENARIO_FIELDS:
        raise ValueError("scenario accepts only: " + ", ".join(sorted(SCENARIO_FIELDS)))
    scenario: dict[str, Any] = {}
    for key in ("organization_type", "industry", "jurisdiction", "activity"):
        item = value.get(key)
        if item is not None and (not isinstance(item, str) or not item.strip() or len(item) > 100):
            raise ValueError(f"scenario {key} must be short text")
        scenario[key] = item.strip() if isinstance(item, str) else None
    date = value.get("reference_date")
    if date is not None and (not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)):
        raise ValueError("scenario reference_date must be YYYY-MM-DD")
    scenario["reference_date"] = date
    facts = value.get("facts") or {}
    if not isinstance(facts, dict) or len(facts) > 30 or any(
            not isinstance(k, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,60}", k) or not isinstance(v, (bool, str, int, float, type(None)))
            or isinstance(v, str) and len(v) > 200 for k, v in facts.items()):
        raise ValueError("scenario facts must be up to 30 snake_case names with scalar values")
    scenario["facts"] = dict(facts)
    return scenario


# ---------------- textual drift ----------------
def textual_drift(frame: QuestionFrame, versions: dict[str, Any], metrics: dict[str, Any] | None) -> dict[str, Any]:
    if not frame.asks_about_versions:
        return _d("OUT_OF_SCOPE", summary="Not a comparison question.",
                  reason="Textual drift compares two versions of one provision; this question does not ask about a change.")
    if versions["support_class"] not in VERSION_CLAIMS:
        return _d("INSUFFICIENT_EVIDENCE", summary="No supported before/after pair.", reason="No supported before/after versions; the answer above explains why.", details={"upstream_reason": versions["reason"]})
    if not str(versions["before"]["text"]).strip():
        return _d("OUT_OF_SCOPE", summary="Not measured for an insertion.", evidence_ids=[versions["after"]["evidence_id"]],
                  reason="Drift compares two wordings (drift-metrics-v3); an insertion has no earlier wording, so the change is the inserted text itself.")
    if not metrics or metrics.get("overall_drift_percent") is None:
        missing = "; ".join(str(v) for v in (metrics or {}).get("unavailable_reasons", {}).values()) or "a component could not be computed"
        return _d("INSUFFICIENT_EVIDENCE", summary="Score unavailable.", reason=f"The pair is supported but the score is unavailable: {missing}.")
    ids = [versions["before"]["evidence_id"], versions["after"]["evidence_id"]]
    return _d("DETERMINED", label=f"{metrics['overall_drift_percent']}%", method=metrics.get("metrics_contract_version"), evidence_ids=ids,
              summary="How far the compared wording moved; not legal significance.",
              reason="Computed from the supported, query-selected before/after pair.",
              details={"components": {k: metrics.get(k) for k in ("semantic_drift_percent", "lexical_drift_percent", "conceptual_drift_percent")},
                       "component_disagreement": metrics.get("component_disagreement")})


# ---------------- materiality ----------------
def _norm(text: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").casefold()))


def materiality(root: Path, frame: QuestionFrame, versions: dict[str, Any]) -> dict[str, Any]:
    if not frame.asks_about_versions:
        return _d("OUT_OF_SCOPE", summary="Not a comparison question.", reason="Materiality is assessed for a specific amendment; none was asked about.")
    if versions["support_class"] not in VERSION_CLAIMS:
        return _d("INSUFFICIENT_EVIDENCE", summary="No supported change to assess.", reason="No supported before/after versions; the answer above explains why.", details={"upstream_reason": versions["reason"]})
    instruction = next((item for item in versions["evidence"] if item["role"] == "amendment_instruction"), None)
    rows = [] if instruction is None else [row for row in load_json(root / MATERIALITY_ARTIFACT)["rows"]
            if row["source_sha256"] == instruction["source_sha256"]
            and row["extraction_v2"].get("target_provision") == versions["provision_path"]
            and row["extraction_v2"].get("operation") == versions["operation"]
            and _norm(row["v2"].get("after_text")) == _norm(versions["after"]["text"])
            and _norm(row["v2"].get("before_text")) == _norm(versions["before"]["text"])]
    if len(rows) != 1:
        return _machine_triage(versions, len(rows))
    row = rows[0]
    rule_a, rule_b = row["v2"]["rule_a"], row["v2"]["rule_b"]
    labels = [(name, rule["label"]) for name, rule in (("Rule A (cue transition)", rule_a), ("Rule B (operation and cues)", rule_b))
              if rule.get("status") == "PROVISIONAL_RULE_OUTPUT" and rule.get("label")]
    llm = next((r for r in load_json(root / LLM_MATERIALITY_ARTIFACT)["rows"] if r.get("pair_id") == row["pair_id"]), None)
    details = {"pair_id": row["pair_id"], "artifact": MATERIALITY_ARTIFACT, "is_gold": False, "labels_are_legal_truth": False,
               "rule_a": {k: rule_a.get(k) for k in ("label", "status", "rationale", "dimensions", "method_id")},
               "rule_b": {k: rule_b.get(k) for k in ("label", "status", "rationale")},
               "llm_assessment": {"label": llm.get("materiality_label"), "status": llm.get("assessment_status"), "rationale": llm.get("rationale"),
                                  "model": "qwen3:4b, temperature 0", "artifact": LLM_MATERIALITY_ARTIFACT} if llm else None,
               "extraction_status": row["extraction_v2"]["status"]}
    if not labels:
        return _d("INSUFFICIENT_EVIDENCE", summary="The versioned rules abstained.", method="materiality-silver-v2.5", details=details,
                  reason="Both versioned rules abstained for this amendment: " + (rule_a.get("rationale") or rule_b.get("rationale") or "review required") + ".")
    distinct = sorted({label for _, label in labels})
    label = distinct[0] if len(distinct) == 1 else " / ".join(f"{label} ({name.split(' (')[0]})" for name, label in labels)
    details["source"] = "FROZEN_SILVER_SET"
    return _d("PROVISIONAL", label=label, method="materiality-silver-v2.5 (frozen rule-based machine triage)", details=details,
              evidence_ids=[instruction["evidence_id"], versions["before"]["evidence_id"], versions["after"]["evidence_id"]],
              summary="Provisional machine triage of legal significance; not an expert judgment.",
              reason=("Exact match to a case in the versioned materiality set; " +
                      ("both rules agree." if len(distinct) == 1 else "the rules disagree, so both labels are shown.")),
              review_status="NOT_REVIEWED_BY_QUALIFIED_EXPERT")


# ---------------- answer change ----------------
WORD_NUMBERS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                                           "sixteen seventeen eighteen nineteen twenty".split())}
WORD_NUMBERS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90})
SCALES = {"hundred": 100, "thousand": 1000, "thousands": 1000, "lakh": 100000, "lakhs": 100000, "crore": 10000000, "crores": 10000000}
NUMBER = re.compile(r"(?:\b\d[\d,]*(?:\.\d+)?|\b(?:(?:" + "|".join(sorted(list(WORD_NUMBERS) + list(SCALES), key=len, reverse=True)) + r")(?:[\s-]+|\b))+)", re.I)  # \b: "often" is not "ten"
UNITS = re.compile(r"^\s*(rupees|days?|months?|years?|persons?|times|hours?|weeks?)\b", re.I)


def _value(phrase: str) -> int | None:
    phrase = phrase.strip().lower()
    if re.fullmatch(r"\d[\d,]*(?:\.\d+)?", phrase):
        return int(float(phrase.replace(",", "")))
    total, current = 0, 0
    for word in re.findall(r"[a-z]+", phrase):
        if word in WORD_NUMBERS:
            current += WORD_NUMBERS[word]
        elif word in SCALES:
            current = max(current, 1) * SCALES[word]
            if SCALES[word] >= 1000:
                total, current = total + current, 0
    return (total + current) or None


def quantities(text: str) -> list[dict[str, Any]]:
    """Amounts, periods, counts and frequencies stated in a fragment, with their qualifier and nature."""
    found = []
    lowered = " ".join(str(text or "").split()).lower()
    if re.search(r"\bannually\b", lowered):
        found.append({"value": 1, "unit": "years", "qualifier": "every", "text": "annually"})
    for match in NUMBER.finditer(lowered):
        value = _value(match.group(0))
        if value is None or (match.group(0).strip().isdigit() and re.match(r"\s*\(", lowered[match.end():])):
            continue  # skip clause numbering such as "1 (a)"
        unit = UNITS.match(lowered[match.end():])
        before = lowered[max(0, match.start() - 40):match.start()]
        qualifier = ("maximum" if re.search(r"(not exceeding|may extend to|up to|upto)\s*$", before)
                     else "minimum" if re.search(r"(not less than|at least)\s*$", before)
                     else "every" if re.search(r"once in every\s*$", before) else "stated")
        found.append({"value": value, "unit": (unit.group(1).rstrip("s") + "s") if unit else None, "qualifier": qualifier,
                      "text": match.group(0).strip() + (" " + unit.group(1) if unit else "")})
    return found


NATURE = re.compile(r"\b(fine|penalty|imprisonment|fee|deposit|compensation|term)\b")
MODALS = {"may": r"\bmay\b(?! (?:be prescribed|be notified|be specified|extend))", "shall": r"\bshall\b", "must": r"\bmust\b",
          "discretion": r"\bdiscretion\b", "shall not": r"\bshall not\b", "may not": r"\bmay not\b"}


def _modal_set(text: str) -> set[str]:
    lowered = str(text or "").lower()
    return {name for name, pattern in MODALS.items() if re.search(pattern, lowered)}


def answer_change(frame: QuestionFrame, versions: dict[str, Any], scenario: dict[str, Any] | None,
                  rule_comparison: dict[str, Any] | None) -> dict[str, Any]:
    if not frame.asks_about_versions:
        return _d("OUT_OF_SCOPE", summary="Not a question about a change.", reason="The question does not ask how the law changed over time.")
    if versions["support_class"] not in VERSION_CLAIMS:
        return _d("INSUFFICIENT_EVIDENCE", summary="No supported versions to compare.", reason="No supported before/after versions; the answer above explains why.", details={"upstream_reason": versions["reason"]})
    ids = [versions["before"]["evidence_id"], versions["after"]["evidence_id"]]
    sub = versions.get("substitution")
    before = sub["old"] if sub else versions["before"]["text"]
    after = sub["new"] if sub else versions["after"]["text"]
    conditions = []
    if versions.get("date_basis") == "ACT_WIDE_COMMENCEMENT_NOT_SCENARIO_APPLICABILITY" and scenario and scenario.get("reference_date"):
        effective = versions.get("effective_date")
        applies = "after" if effective and scenario["reference_date"] >= effective else "before"
        conditions.append(f"On {scenario['reference_date']} the {applies}-amendment wording would apply if the Act-wide commencement "
                          f"({effective}) governs your situation; that is not verified.")

    if rule_comparison is not None:
        if rule_comparison["state"] == "NEEDS_FACTS":
            return _d("NEEDS_FACTS", summary="Facts needed to compare the two versions for your situation.", evidence_ids=ids,
                      reason=rule_comparison["reason"], needs=rule_comparison["needs"], method="obligation-registry comparison")
        changed = rule_comparison["changed"]
        return _d("CONDITIONAL", label="Changes" if changed else "Does not change", evidence_ids=ids, method="obligation-registry comparison",
                  summary=rule_comparison["summary"], details=rule_comparison,
                  reason="Both versions were evaluated against your facts using the versioned obligation rules; historical applicability "
                         "is stipulated for demonstration, so the result is conditional.")

    if frame.question_type == "quantity":
        slots_before, slots_after = quantities(before), quantities(after)
        delegated = bool(re.search(r"as may be (?:prescribed|notified|specified)", after.lower()))
        if not slots_before and not slots_after and not delegated:
            return _d("INSUFFICIENT_EVIDENCE", summary="The compared wording states no amount or period.", evidence_ids=ids,
                      reason="Neither version's compared wording contains the amount, period or number the question asks about.")
        if not before.strip():
            return _d("CONDITIONAL", label="Changes", evidence_ids=ids, summary=f"The amendment inserted: “{after}”.",
                      reason="The inserted words did not exist before; whether the earlier law set a different figure elsewhere is not shown.")
        key = lambda q: (q["value"], q["unit"], q["qualifier"])
        same_values = {q["value"] for q in slots_before} == {q["value"] for q in slots_after} and bool(slots_before)
        nature_before, nature_after = set(NATURE.findall(before.lower())), set(NATURE.findall(after.lower()))
        changed = sorted(map(key, slots_before)) != sorted(map(key, slots_after)) or nature_before != nature_after or delegated
        parts = []
        if same_values and changed:
            parts.append("the figure is the same")
        if nature_before != nature_after:
            parts.append(f"it changes from {', '.join(sorted(nature_before)) or 'unspecified'} to {', '.join(sorted(nature_after)) or 'unspecified'}")
        if delegated:
            parts.append("the new wording leaves the figure to be prescribed by rules rather than fixing it in the Act")
        qualifiers = ({q["qualifier"] for q in slots_before}, {q["qualifier"] for q in slots_after})
        if qualifiers[0] != qualifiers[1] and same_values:
            plain = {"maximum": "an upper limit", "minimum": "a minimum", "stated": "a fixed amount", "every": "a frequency"}
            parts.append(f"it changes from {' / '.join(plain[q] for q in sorted(qualifiers[0]))} to {' / '.join(plain[q] for q in sorted(qualifiers[1]))}")
        state = "CONDITIONAL" if conditions else "DETERMINED"
        verdict = (f"Yes: after the amendment the wording is “{after}” (it was “{before}”)." if changed
                   else f"No: the figure you asked about is the same in both versions (“{after}”), although other wording changed.")
        return _d(state, label="Changes" if changed else "Does not change", evidence_ids=ids, method="quantity-slot comparison",
                  summary=verdict + (" " + "; ".join(parts).capitalize() + "." if parts else ""),
                  reason=("Compared the amount, unit, limit and kind of sanction in the supported versions." + (" " + " ".join(conditions) if conditions else "")),
                  details={"before": slots_before, "after": slots_after, "nature": [sorted(nature_before), sorted(nature_after)], "delegated": delegated})

    if frame.question_type == "modal":
        if not before.strip():
            return _d("CONDITIONAL", label="Changes", evidence_ids=ids, method="modal comparison",
                      summary=f"After the amendment the provision says: “{after}”.",
                      reason="These words were inserted; the earlier text of this provision did not contain them, but whether earlier law "
                             "allowed or required the same thing elsewhere is not shown by this evidence.")
        modal_before, modal_after = _modal_set(before), _modal_set(after)
        if not modal_before and not modal_after:
            return _d("INSUFFICIENT_EVIDENCE", summary="No permission or duty wording in the compared text.", evidence_ids=ids,
                      reason="The compared wording has no 'may', 'shall', 'must' or discretion language to answer the question.")
        changed = modal_before != modal_after
        return _d("CONDITIONAL" if conditions else "DETERMINED", label="Changes" if changed else "Does not change", evidence_ids=ids,
                  method="modal comparison",
                  summary=(f"Yes: the provision now says “{after}”, where it said “{before}”." if changed
                           else f"No: the permission or duty wording is the same (“{after}”)."),
                  reason=("Compared permission and duty wording (" + ", ".join(sorted(modal_before)) + " → " + ", ".join(sorted(modal_after)) + ")."
                          + (" " + " ".join(conditions) if conditions else "")),
                  details={"before": sorted(modal_before), "after": sorted(modal_after)})

    # "What changed" / comparison questions: the change itself is the answer; a situation is needed to go further.
    return _d("NEEDS_FACTS", summary="Your question asks what changed; that is answered above.", evidence_ids=ids,
              reason="To say whether the change alters the answer for a particular situation, ask about a specific figure, permission or "
                     "duty in this provision, or add scenario facts where an obligation model exists.",
              needs=[{"key": "question", "label": "A specific question about this provision (for example an amount, a deadline or whether something is allowed)",
                      "kind": "text"}])


# ---------------- risk ----------------
def risk(root: Path, frame: QuestionFrame, versions: dict[str, Any], scenario: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Risk via the existing service and registry; returns (determination, rule comparison for answer change)."""
    from temporal_legal_drift.risk.service import RiskService

    if not frame.principal or not frame.sections:
        return _d("OUT_OF_SCOPE", summary="No provision identified.", reason="Risk is assessed only for a named provision with a modelled obligation."), None
    provision = f"{frame.principal.entry_id}:section:{frame.sections[0]}"
    service = RiskService(root)
    rules = [rule for rule in service._registry()["rules"] if rule["provision"] == provision]
    if not rules:
        return _d("OUT_OF_SCOPE", summary="No obligation model for this provision.",
                  reason="Risk is computed only where a versioned obligation rule exists; the registry has no rule for this provision."), None
    dated = [rule for rule in rules if scenario and scenario.get("reference_date") in rule["reference_dates"]]
    needs = _risk_needs(dated or rules)
    missing = [need for need in needs if not _has(scenario, need["key"])]
    if scenario and scenario.get("reference_date") and not dated:
        missing = [need for need in missing if need["key"] in {"organization_type", "industry", "jurisdiction", "activity"}]  # the engine reports the date gap
    if not scenario or missing:
        return (_d("NEEDS_FACTS", summary="Add your situation to assess risk.", method="compliance-risk-baseline-v1", needs=missing or needs,
                   reason="A versioned obligation rule exists for this provision, but risk needs your facts: " + ", ".join(n["label"] for n in (missing or needs)) + "."),
                _decisive_comparison(rules, scenario))
    request = {"scenario_id": "rag_" + sha256(canonical_json_bytes({"q": frame.query, "s": scenario})).hexdigest()[:16],
               "organization_type": scenario["organization_type"], "industry": scenario["industry"], "jurisdiction": scenario["jurisdiction"],
               "facts": scenario["facts"], "reference_date": scenario["reference_date"], "applicable_provision": provision,
               "activity": scenario["activity"], "exposure": {"description": None, "amount": None}}
    result = service.assess(request)
    comparison = _compare_versions(service, request, rules) or _decisive_comparison(rules, scenario)
    uncertainty = result.get("uncertainty") or []
    stipulated = "historical_applicability_stipulated_for_demonstration" in uncertainty
    if result["status"] == "PROVISIONAL_ASSESSMENT":
        return (_d("CONDITIONAL" if stipulated else "PROVISIONAL", label=result["risk_level"], method="compliance-risk-baseline-v1",
                   summary=(result.get("consequence") or "") if result.get("risk_flag") else "No adverse consequence under the selected rule.",
                   reason=("The modelled obligation rule for this wording matched your facts and date. "
                           + ("Historical applicability is stipulated for demonstration, so this is conditional, not validated." if stipulated
                              else "The interpretation is not expert-validated.")),
                   details={k: result.get(k) for k in ("rule_id", "provision_version", "status", "risk_level", "urgency", "uncertainty", "reasoning_trace", "risk_flag", "escalation_required")}),
                comparison)
    if result["status"] == "NOT_APPLICABLE":
        return (_d("CONDITIONAL", label="Outside the modelled rule", method="compliance-risk-baseline-v1",
                   summary="Your situation is outside the scope of the only modelled rule for this provision.",
                   reason="The rule's scope does not match your organisation, industry, jurisdiction or activity; no risk is inferred beyond it.",
                   details={k: result.get(k) for k in ("rule_id", "status", "reasoning_trace", "escalation_required")}), comparison)
    missing_facts = [u.split(":", 1)[1] for u in uncertainty if u.startswith(("missing_applicability_fact:", "missing_obligation_fact:", "missing_scenario_scope:"))]
    if missing_facts:
        return (_d("NEEDS_FACTS", summary="More facts are needed.", method="compliance-risk-baseline-v1",
                   needs=[need for need in needs if need["key"] in missing_facts] or [{"key": k, "label": k.replace("_", " "), "kind": "boolean"} for k in missing_facts],
                   reason="The engine needs: " + ", ".join(k.replace("_", " ") for k in missing_facts) + "."), comparison)
    readable = {"no_applicability_evidence_for_reference_date": "no rule covers your reference date (rules cover: "
                + ", ".join(sorted({d for r in rules for d in r["reference_dates"]})) + ")",
                "applicability_conflict": "more than one rule claims your reference date",
                "temporal_applicability_unresolved": "the provision version for your date is unresolved"}
    why = "; ".join(readable.get(u, u.replace("_", " ")) for u in uncertainty if not u.startswith("operational_")) or result["status"].lower()
    return (_d("INSUFFICIENT_EVIDENCE", summary="Risk cannot be determined; escalate for review.", method="compliance-risk-baseline-v1",
               reason=f"The risk engine abstained: {why}. Unknown risk is not 'no risk'.",
               details={k: result.get(k) for k in ("status", "uncertainty", "rule_id")}), comparison)


def _risk_needs(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    needs = [{"key": "reference_date", "label": "Reference date", "kind": "date",
              "options": sorted({d for r in rules for d in r["reference_dates"]})}]
    for key in ("organization_type", "industry", "jurisdiction", "activity"):
        values = sorted({r["scope"][key] for r in rules if r["scope"][key] != "*"})
        needs.append({"key": key, "label": key.replace("_", " ").capitalize(), "kind": "choice", "options": values})
    facts = sorted({k for r in rules for k in r["conditions"]} | {r["fact_key"] for r in rules})
    needs += [{"key": f"facts.{k}", "label": k.replace("_", " ").capitalize(), "kind": "boolean"} for k in facts]
    return needs


def _has(scenario: dict[str, Any] | None, key: str) -> bool:
    if not scenario:
        return False
    if key.startswith("facts."):
        return key[6:] in (scenario.get("facts") or {})
    return scenario.get(key) is not None


def _decisive_comparison(rules: list[dict[str, Any]], scenario: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compare the versions on the facts their rules differ on; what both rules share is stated as an assumption.

    The minimum facts for "does the answer change between versions" are the decisive ones; the shared scope and
    conditions decide risk (asked for separately), not the difference between the versions.
    """
    if len(rules) < 2 or any(r["kind"] == "deadline" for r in rules):
        return None
    if any(r["scope"] != rules[0]["scope"] or r["conditions"] != rules[0]["conditions"] for r in rules):
        return None
    facts = (scenario or {}).get("facts") or {}
    decisive = sorted({r["fact_key"] for r in rules})
    missing = [k for k in decisive if not isinstance(facts.get(k), type(next(r["required_value"] for r in rules if r["fact_key"] == k)))]
    if missing:
        return {"state": "NEEDS_FACTS", "needs": [{"key": f"facts.{k}", "label": k.replace("_", " ").capitalize(), "kind": "boolean"} for k in missing],
                "reason": "Only the facts on which the two versions' rules differ are needed to compare them."}
    outcomes = []
    for rule in sorted(rules, key=lambda r: r["reference_dates"][0]):
        meets = facts[rule["fact_key"]] == rule["required_value"]
        meets = not meets if rule["kind"] == "prohibition" else meets
        outcomes.append({"rule_id": rule["rule_id"], "provision_version": rule["provision_version"], "date": rule["reference_dates"][0],
                         "status": "DECISIVE_FACT_COMPARISON", "risk_flag": not meets, "risk_level": None, "decisive_fact": rule["fact_key"]})
    describe = lambda o: "meets the rule" if o["risk_flag"] is False else "does not meet the rule"  # noqa: E731
    return {"state": "COMPARED", "changed": outcomes[0]["risk_flag"] != outcomes[-1]["risk_flag"], "outcomes": outcomes,
            "assumes": "your organisation, activity and the shared conditions match the modelled rule (they are identical for both versions)",
            "summary": f"Under the earlier wording your situation {describe(outcomes[0])}; under the later wording it {describe(outcomes[-1])}."}


def _compare_versions(service: Any, request: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Same facts, each version's rule at its own date: does the outcome differ?"""
    if len(rules) < 2:
        return None
    outcomes = []
    for rule in sorted(rules, key=lambda r: r["reference_dates"][0]):
        result = service.assess({**request, "reference_date": rule["reference_dates"][0]})
        outcomes.append({"rule_id": rule["rule_id"], "provision_version": rule["provision_version"], "date": rule["reference_dates"][0],
                         "status": result["status"], "risk_flag": result.get("risk_flag"), "risk_level": result.get("risk_level")})
    if any(o["status"] != "PROVISIONAL_ASSESSMENT" for o in outcomes):
        return None
    changed = outcomes[0]["risk_flag"] != outcomes[-1]["risk_flag"]
    describe = lambda o: "meets the rule" if o["risk_flag"] is False else "does not meet the rule"
    return {"state": "COMPARED", "changed": changed, "outcomes": outcomes,
            "summary": f"Under the earlier wording your situation {describe(outcomes[0])}; under the later wording it {describe(outcomes[-1])}."}


# ---------------- applicability ----------------
def applicability(frame: QuestionFrame, versions: dict[str, Any], scenario: dict[str, Any] | None) -> dict[str, Any]:
    """Publication, commencement and scenario applicability, kept as separate facts; never DETERMINED without approved facts."""
    if not frame.asks_about_versions:
        return _d("OUT_OF_SCOPE", summary="Not a question about versions.", reason="Applicability matters only when two versions are compared.")
    if versions["support_class"] not in VERSION_CLAIMS:
        return _d("INSUFFICIENT_EVIDENCE", summary="No supported versions.", reason="No supported before/after versions; the answer above explains why.",
                  details={"upstream_reason": versions["reason"]})
    if versions.get("effective_date"):
        commencement = {"date": versions["effective_date"], "status": "MACHINE_EVIDENCED_ACT_WIDE",
                        "basis": "graph v4: Act-wide commencement of the amending Act; not provision-specific and not reviewed"}
    elif versions.get("footnote_stated_date"):
        day, month, year = versions["footnote_stated_date"].split("-")
        commencement = {"date": f"{year}-{int(month):02d}-{int(day):02d}", "status": "FOOTNOTE_STATED_UNVERIFIED",
                        "basis": "date printed in the India Code footnote (w.e.f.); not verified as commencement"}
    else:
        commencement = {"date": None, "status": "UNKNOWN", "basis": "no commencement date is recorded for this amendment"}
    details = {"publication": {"date": None, "status": "NOT_IN_THIS_EVIDENCE", "note": "publication is not commencement"},
               "commencement": commencement,
               "scenario_applicability": {"status": "NOT_DETERMINED", "note": "needs approved temporal facts and review"}}
    reference = (scenario or {}).get("reference_date")
    if not reference:
        return _d("NEEDS_FACTS", summary="Add a reference date to see which wording would apply.", details=details,
                  reason="Publication, commencement and your situation's applicability are separate; none decides your date without one.",
                  needs=[{"key": "reference_date", "label": "Reference date (YYYY-MM-DD)", "kind": "date", "options": []}])
    if not commencement["date"]:
        return _d("INSUFFICIENT_EVIDENCE", summary="Cannot tell which wording applies on your date.", details=details,
                  reason="No commencement date is recorded for this amendment.")
    applies = "after" if reference >= commencement["date"] else "before"
    details["scenario_applicability"] = {"status": "CONDITIONAL", "reference_date": reference, "applies": applies}
    return _d("CONDITIONAL", label=f"{applies.capitalize()}-amendment wording", details=details,
              summary=f"On {reference} the {applies}-amendment wording would apply if the commencement date ({commencement['date']}) governs your situation.",
              reason=f"Commencement basis: {commencement['basis']}. Scenario applicability is not verified.")


def _machine_triage(versions: dict[str, Any], silver_rows: int) -> dict[str, Any]:
    """Materiality of the amendment itself, computed now with the same two versioned rules as the silver set.

    It needs no scenario facts. It is provisional machine triage: not a frozen silver row and never legal gold.
    """
    from temporal_legal_drift.materiality.silver import _cue_transition_annotator, _operation_delta_annotator

    if any(item.get("text_reliability") == "UNRELIABLE_TEXT_LAYER" for item in versions["evidence"]):
        return _d("INSUFFICIENT_EVIDENCE", summary="Not assessed: unreliable source text.",
                  reason="A cited source has an unreliable text layer, so its wording is not triaged.")
    sub = versions.get("substitution")
    task = {"operation": versions.get("operation") or "SUBSTITUTE", "before_text": sub["old"] if sub else versions["before"]["text"],
            "after_text": sub["new"] if sub else versions["after"]["text"]}
    # triage-input-v2: number words become digits so "five hundred" -> "five thousand" is seen as a numeric change (the frozen rules see digits only).
    numerals = lambda text: NUMBER.sub(lambda m: f"{_value(m.group(0))} " if _value(m.group(0)) is not None else m.group(0), text)  # noqa: E731
    scored = {**task, "before_text": numerals(task["before_text"]), "after_text": numerals(task["after_text"])}
    rule_a, rule_b = _cue_transition_annotator(scored), _operation_delta_annotator(scored)
    labels = sorted({rule_a["label"], rule_b["label"]})
    label = labels[0] if len(labels) == 1 else f"{rule_a['label']} (rule A) / {rule_b['label']} (rule B)"
    return _d("PROVISIONAL", label=label, method="machine triage computed now: rule-cue-transition-v1 and operation-delta-v1 on number-normalised text (triage-input-v2)",
              evidence_ids=[versions["before"]["evidence_id"], versions["after"]["evidence_id"]],
              summary="Provisional machine triage of the amendment's legal significance, computed for this answer.",
              reason=("No frozen silver assessment covers this amendment"
                      + (f" ({silver_rows} near-matching rows)" if silver_rows else "") + ", so the same two versioned rules were applied now. "
                      + ("Both rules agree." if len(labels) == 1 else "The rules disagree, so both labels are shown.")),
              details={"source": "ON_THE_FLY_MACHINE_TRIAGE", "frozen_silver_match": False, "is_gold": False, "labels_are_legal_truth": False,
                       "rule_a": {k: rule_a.get(k) for k in ("label", "rationale", "dimensions", "method_id")},
                       "rule_b": {k: rule_b.get(k) for k in ("label", "rationale", "dimensions", "method_id")}, "operands": task, "scored_operands": scored,
                       "input_normalisation": "triage-input-v2 (number words to digits)"},
              review_status="NOT_REVIEWED_MACHINE_TRIAGE")
