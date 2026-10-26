"""Routing evaluation (routing-eval-v1): Act resolution and source identity on a small versioned question set.

Five engineering metrics, reported separately and never combined: Act-resolution accuracy, cross-Act contamination,
citation validity, helpful abstention and answer coverage. None of them is a measure of legal accuracy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from temporal_legal_drift.jsonio import load_json

EVAL_VERSION = "routing-eval-v1"


def run_routing_eval(root: Path, cases_path: Path, *, pipeline: Any = None) -> dict[str, Any]:
    from .audit import offline_extractive
    from .rag_pipeline import RagPipeline

    spec = load_json(cases_path)
    answering = set(spec["answering_routes"])
    rows = []
    with offline_extractive():
        pipeline = pipeline or RagPipeline(root)
        for case in spec["cases"]:
            result = pipeline.answer(case["question"], "specific")
            routing = result["routing"]
            cited = sorted({str(c.get("entry_id")) for key in ("citations", "evidence") for c in result.get(key) or [] if c.get("entry_id")})
            interpreted = [a["entry_id"] for a in routing["interpreted_acts"]]
            permitted = set(case["expected_acts"]) | set(routing["allowed_entry_ids"]) if case["expected_route"] in answering else set()
            gave_help = bool(routing["choices"] or routing.get("links") or "?" in result["answer"]["direct_answer"]
                             or "Ask " in result["answer"]["direct_answer"] or "ask " in result["answer"]["direct_answer"])
            rows.append({
                "case_id": case["case_id"], "question": case["question"], "expected_route": case["expected_route"], "route": routing["route"],
                "reason_code": routing["reason_code"], "expected_acts": case["expected_acts"], "interpreted_acts": interpreted,
                "resolved_correctly": routing["route"] == case["expected_route"] and interpreted == case["expected_acts"],
                "cited_entry_ids": cited, "contaminating_entry_ids": sorted(set(cited) - permitted),
                "citations_valid": sum(e in routing["allowed_entry_ids"] for e in cited), "citations_total": len(cited),
                "abstained_helpfully": (not cited and gave_help) if case["expected_route"] not in answering else None,
                "answered": (bool(cited) or bool((result.get("latest_records") or {}).get("sources")) or result["answer"]["answer_type"] == "version_abstention")
                if case["expected_route"] in answering else None,
            })
    total_citations = sum(r["citations_total"] for r in rows)
    abstain = [r for r in rows if r["abstained_helpfully"] is not None]
    answer = [r for r in rows if r["answered"] is not None]
    return {
        "version": EVAL_VERSION, "case_set": spec["case_set"], "cases_path": str(cases_path.relative_to(root) if cases_path.is_relative_to(root) else cases_path),
        "run_conditions": "offline: no live India Code lookup, no language model (extractive answers); latest records read from the local monitoring ledger",
        "metrics": {
            "act_resolution_accuracy": {"value": sum(r["resolved_correctly"] for r in rows) / len(rows), "count": len(rows),
                                        "definition": "route and interpreted Act ids both equal the expected ones"},
            "cross_act_contamination": {"value": sum(bool(r["contaminating_entry_ids"]) for r in rows), "count": len(rows),
                                        "definition": "cases citing a document outside the expected Acts and their recorded amending instruments (any citation, for a non-answering route)"},
            "citation_validity": {"value": (sum(r["citations_valid"] for r in rows) / total_citations) if total_citations else None, "count": total_citations,
                                  "definition": "citations whose document is in the route's allowed set"},
            "helpful_abstention": {"value": (sum(r["abstained_helpfully"] for r in abstain) / len(abstain)) if abstain else None, "count": len(abstain),
                                   "definition": "non-answering cases with no citation and a choice, link or narrower question offered"},
            "answer_coverage": {"value": (sum(r["answered"] for r in answer) / len(answer)) if answer else None, "count": len(answer),
                                "definition": "answering cases with cited evidence, a section choice, or monitored-source status"},
        },
        "not_measured": "legal accuracy, completeness of the answer, and whether a listed record is a change to law",
        "cases": rows,
    }
