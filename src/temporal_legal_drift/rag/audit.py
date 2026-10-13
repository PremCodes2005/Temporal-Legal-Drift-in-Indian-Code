"""Cross-corpus audit of the single-prompt assistant against source-derived expectations.

Expectations come from configs/rag_audit/cases.v*.json (graph v4, silver materiality,
risk registry), never from the assistant's own answers. The metrics are engineering
coverage and error counts, not legal accuracy.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from temporal_legal_drift.jsonio import load_json

VERSION_CLAIMS = {"GRAPH_TRANSITION_FRAGMENTS", "CONSOLIDATED_FOOTNOTE_RECONSTRUCTION"}
DETERMINATIONS = ("textual_drift", "materiality", "answer_change", "risk")


@contextmanager
def offline_extractive() -> Iterator[None]:
    """Reproducible run: no live India Code lookup and no language model (extractive path)."""
    names = ("TLD_LIVE_INDIA_CODE", "TLD_RAG_PROVIDER", "TLD_RAG_API_KEY", "OPENAI_API_KEY")
    saved = {name: os.environ.get(name) for name in names}
    os.environ.update({"TLD_LIVE_INDIA_CODE": "0", "TLD_RAG_PROVIDER": "openai_compatible", "TLD_RAG_API_KEY": "", "OPENAI_API_KEY": ""})
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def run_audit(root: Path, cases_path: Path, *, pipeline: Any = None) -> dict[str, Any]:
    from .rag_pipeline import RagPipeline

    spec = load_json(cases_path)
    pipeline = pipeline or RagPipeline(root)
    rows = []
    for case in spec["cases"]:
        started = time.monotonic()
        try:
            response = pipeline.answer(case["query"], case["mode"], scenario=case.get("scenario")) \
                if "scenario" in _answer_parameters(pipeline) else pipeline.answer(case["query"], case["mode"])
            error = None
        except Exception as exc:  # recorded, never hidden
            response, error = None, f"{type(exc).__name__}: {exc}"
        rows.append(evaluate_case(case, response, error, round(time.monotonic() - started, 2)))
    return {"schema_version": "1.0.0", "case_set": spec["case_set"], "cases": rows, "summary": summarise(rows),
            "interpretation": "engineering coverage and error counts against source-derived expectations; not legal accuracy"}


def _answer_parameters(pipeline: Any) -> set[str]:
    import inspect

    return set(inspect.signature(pipeline.answer).parameters)


def evaluate_case(case: dict[str, Any], response: dict[str, Any] | None, error: str | None, seconds: float) -> dict[str, Any]:
    expected = case["expected"]
    row: dict[str, Any] = {"case_id": case["case_id"], "stratum": case["stratum"], "mode": case["mode"], "seconds": seconds,
                           "expected_support": expected["support"], "error": error}
    if response is None:
        return {**row, "outcome": "ERROR"}
    comparison = response.get("comparison") or {}
    support = comparison.get("support_class") or "NO_COMPARISON_RECORD"
    sides = [comparison.get(side) or {} for side in ("before", "after")]
    entries = {str(side.get("entry_id")) for side in sides if side.get("entry_id")}
    allowed = {expected.get("act"), expected.get("amending")} - {None}
    row.update({
        "actual_support": support,
        "pair_entries": sorted(entries),
        "provision_path": comparison.get("provision_path"),
        "operation": comparison.get("operation"),
        "answer_type": (response.get("answer") or {}).get("answer_type"),
        "generation_method": (response.get("answer") or {}).get("generation_method"),
        "has_drift_score": (response.get("metrics") or {}).get("overall_drift_percent") is not None,
        "citations": [{"entry_id": c.get("entry_id"), "page": c.get("page") or _anchor_page(c.get("source_anchor")),
                       "has_link": bool(c.get("source_url") or c.get("local_pdf_url") or c.get("official_portal_url"))}
                      for c in response.get("citations") or []],
        "fidelity_warnings": len(response.get("source_fidelity_warnings") or []),
        "determinations": {name: ((response.get("determinations") or {}).get(name) or {}).get("state", "ABSENT")
                           for name in (*DETERMINATIONS, *(k for k in expected["states"] if k not in DETERMINATIONS))},
        "fingerprint": {name: ((response.get("fingerprint") or {}).get(name) or {}).get("state", "ABSENT")
                        for name in ("wording_drift", "rule_drift", "outcome_drift")},
        "opening_answer": _opening(response),
    })
    errors = []
    if expected["support"] in VERSION_CLAIMS:
        if support != expected["support"]:
            errors.append(f"support_mismatch:{support}")
        if expected.get("provision") and comparison.get("provision_path") not in {expected["provision"], None}:
            errors.append(f"wrong_provision:{comparison.get('provision_path')}")
        if expected.get("provision") and comparison.get("provision_path") is None and support in VERSION_CLAIMS:
            errors.append("provision_identity_missing")
    elif expected["support"] == "UNALIGNED_OR_ABSTAIN" and support in VERSION_CLAIMS:
        errors.append(f"false_version_claim:{support}")
    elif expected["support"] == "NOT_A_COMPARISON" and support in VERSION_CLAIMS:
        errors.append(f"unrequested_version_claim:{support}")
    pairing_errors = [f"pair_entry_outside_expected:{entry}" for entry in entries if allowed and entry not in allowed]
    if support not in VERSION_CLAIMS and row["has_drift_score"]:
        errors.append("score_without_supported_pair")
    citation_errors = [f"citation_missing_page:{c['entry_id']}" for c in row["citations"] if not c["page"]]
    citation_errors += [f"citation_missing_link:{c['entry_id']}" for c in row["citations"] if not c["has_link"]]
    if allowed:
        citation_errors += [f"citation_outside_expected_act:{c['entry_id']}" for c in row["citations"] if c["entry_id"] not in allowed]
    state_mismatch = {name: {"expected": expected["states"][name], "actual": row["determinations"][name]}
                      for name in expected["states"] if row["determinations"][name] != expected["states"][name]}
    state_mismatch.update({f"fingerprint.{name}": {"expected": state, "actual": row["fingerprint"][name]}
                           for name, state in (expected.get("fingerprint") or {}).items() if row["fingerprint"][name] != state})
    row.update({"support_errors": errors, "pairing_errors": pairing_errors, "citation_errors": citation_errors,
                "state_mismatch": state_mismatch})
    return row


def _anchor_page(anchor: object) -> int | None:
    import re

    match = re.search(r"page:(\d+)", str(anchor or ""))
    return int(match.group(1)) if match else None


def _opening(response: dict[str, Any]) -> str:
    answer = response.get("answer") or {}
    text = answer.get("direct_answer") or answer.get("short_answer") or answer.get("post_amendment_revision") or ""
    return " ".join(str(text).split())[:400]


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    states: dict[str, dict[str, int]] = {}
    for row in rows:
        for name, state in [*(row.get("determinations") or {}).items(), *((f"fingerprint.{k}", v) for k, v in (row.get("fingerprint") or {}).items())]:
            states.setdefault(name, {})
            states[name][state] = states[name].get(state, 0) + 1
    return {
        "cases": len(rows),
        "errors": sum(row.get("outcome") == "ERROR" for row in rows),
        "support_errors": sum(bool(row.get("support_errors")) for row in rows),
        "pairing_errors": sum(bool(row.get("pairing_errors")) for row in rows),
        "citation_errors": sum(bool(row.get("citation_errors")) for row in rows),
        "determination_state_matches": sum(not row.get("state_mismatch") for row in rows if "state_mismatch" in row),
        "determination_states": states,
    }
