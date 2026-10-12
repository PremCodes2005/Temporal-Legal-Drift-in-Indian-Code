"""Run one case through source → graph → applicability → materiality → risk → explanation → review.

Stages communicate only through versioned interfaces (graph-consumer-v1, the
risk service, structured-explanation-v1). The correlation ID is derived from
the case and every input fingerprint, so a rerun is idempotent and a restart
reproduces the same record. A failing stage never aborts silently: it is
recorded, later stages are skipped, and the case ends escalated for review.
"""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from temporal_legal_drift.corpus import CorpusManifest
from temporal_legal_drift.explanations.contract import build_explanation, validate_explanation
from temporal_legal_drift.jsonio import atomic_write_new, canonical_json_bytes, load_json
from temporal_legal_drift.risk.service import RiskService
from temporal_legal_drift.versioning.consumer import GraphConsumer

PIPELINE_VERSION = "case-orchestration-v1"
GRAPH_VERSION = "v4"
MATERIALITY_ARTIFACT = "data/silver/materiality_reassessment.v2.5.json"
STAGES = ("source", "graph", "applicability", "materiality", "risk", "explanation")


def run_case(root: Path, case: dict[str, Any], *, write: bool = True) -> dict[str, Any]:
    root = root.resolve()
    _validate_case(case)
    inputs = {
        relative: sha256((root / relative).read_bytes()).hexdigest()
        for relative in (
            f"reports/phase3/temporal_graph_checkpoint.{GRAPH_VERSION}.json", MATERIALITY_ARTIFACT,
            "configs/corpus/pilot_v1.json", "data/risk/obligation_registry.v1.json",
        )
    }
    correlation_id = "run_" + sha256(canonical_json_bytes(
        {"pipeline": PIPELINE_VERSION, "case": case, "inputs": inputs})).hexdigest()[:24]
    trace: dict[str, Any] = {"correlation_id": correlation_id, "case": case, "stages": {}}
    context: dict[str, Any] = {}
    failed = False
    for name in STAGES[:-1]:
        if failed:
            trace["stages"][name] = {"status": "SKIPPED_UPSTREAM_FAILURE", "output": None}
            continue
        try:
            trace["stages"][name] = STAGE_FUNCTIONS[name](root, case, context)
        except Exception as error:  # fail safe: record, skip downstream, escalate
            trace["stages"][name] = {"status": "FAILED", "output": None, "error": f"{type(error).__name__}: {error}"}
            failed = True
    if failed:
        explanation, errors = None, ["upstream stage failed"]
        trace["stages"]["explanation"] = {"status": "SKIPPED_UPSTREAM_FAILURE", "output": None}
    else:
        explanation = build_explanation(trace)
        errors = validate_explanation(explanation, trace)
        trace["stages"]["explanation"] = {"status": "OK" if not errors else "INVALID", "output": explanation, "errors": errors}
    unresolved = [name for name, stage in trace["stages"].items() if stage["status"] not in {"OK", "NOT_REQUESTED"}]
    record = {
        "schema_version": "1.0.0",
        "pipeline_version": PIPELINE_VERSION,
        "correlation_id": correlation_id,
        "case": case,
        "input_sha256": inputs,
        "interfaces": {"graph": f"graph-consumer-v1/{GRAPH_VERSION}", "risk": "compliance-risk-baseline-v1",
                       "explanation": "structured-explanation-v1"},
        "stages": trace["stages"],
        "review_state": "ESCALATED_UNRESOLVED" if unresolved else "PENDING_REVIEW",
        "unresolved_stages": unresolved,
        "legal_validation": "UNVERIFIED",
    }
    if write:
        atomic_write_new(root / f"data/runs/{correlation_id}.json", canonical_json_bytes(record))
    return record


def _validate_case(case: dict[str, Any]) -> None:
    for key in ("case_id", "act", "section", "reference_date"):
        if not isinstance(case.get(key), str) or not case[key].strip():
            raise ValueError(f"case requires a non-empty string {key}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", case["reference_date"]):
        raise ValueError("reference_date must be YYYY-MM-DD")
    if set(case) - {"case_id", "act", "section", "reference_date", "question", "scenario"}:
        raise ValueError("case contains unsupported fields")


def _source(root: Path, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    consumer = GraphConsumer(root, GRAPH_VERSION)
    context["consumer"] = consumer
    act = next((item for item in consumer.graph.acts if case["act"] in {item["corpus_entry_id"], item["act_id"], item["title"]}), None)
    if act is None:
        return {"status": "UNRESOLVED", "output": {"reason": "act_not_in_corpus"}}
    source = next(item for item in consumer.graph.legal_sources if item["source_id"] == act["source_id"])
    risks = {entry.entry_id: entry.known_extraction_risk for entry in CorpusManifest.from_file(root / "configs/corpus/pilot_v1.json").entries}
    context["risk_by_source_id"] = {
        item["source_id"]: risks.get(item["corpus_entry_id"]) for item in consumer.graph.legal_sources
    }
    return {"status": "OK", "output": {
        "corpus_entry_id": source["corpus_entry_id"], "source_id": source["source_id"], "source_url": source["source_url"],
        "sha256": source["sha256"], "integrity_verified": source["source_integrity_verified"],
        "known_extraction_risk": risks.get(source["corpus_entry_id"]),
    }}


def _graph(root: Path, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    result = context["consumer"].provision_at(case["act"], case["section"], case["reference_date"])
    context["graph"] = result
    if result["status"] == "FRAGMENT_SUPPORTED":
        # A fragment from an amending instrument with a known text-fidelity risk stays unresolved.
        risky = [item["source_id"] for item in result["source_evidence"] if context["risk_by_source_id"].get(item["source_id"])]
        return {"status": "UNRESOLVED" if risky else "OK", "output": {**result, "source_text_unreliable": risky}}
    return {"status": "UNRESOLVED", "output": result}


def _applicability(root: Path, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    # The resolver requires approved temporal facts; none exist for the real corpus yet.
    return {"status": "UNRESOLVED", "output": {
        "status": "NOT_DETERMINED_NO_APPROVED_TEMPORAL_FACTS",
        "graph_effective_date_basis": context["graph"].get("effective_date_basis"),
    }}


def _materiality(root: Path, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    graph = context["graph"]
    if graph["status"] != "FRAGMENT_SUPPORTED":
        return {"status": "NOT_REQUESTED", "output": {"status": "NOT_ASSESSED", "reason": "no supported transition"}}
    fragment = _normal(str(graph["text"] or ""))
    rows = [
        row for row in load_json(root / MATERIALITY_ARTIFACT)["rows"]
        if row["source_id"] == graph["source_evidence"][0]["source_id"]
        and fragment and fragment in {_normal(str(row["v2"]["after_text"] or "")), _normal(str(row["v2"]["before_text"] or ""))}
    ]
    if len(rows) != 1:
        return {"status": "UNRESOLVED", "output": {"status": "NOT_ASSESSED", "reason": f"{len(rows)} matching silver cases"}}
    row = rows[0]
    labels = {"rule_a": row["v2"]["rule_a"], "rule_b": row["v2"]["rule_b"]}
    summary = ", ".join(f"{name} {value.get('label') or 'abstain'} ({value['status']})" for name, value in labels.items())
    return {"status": "OK", "output": {"status": "SILVER_ASSESSED", "pair_id": row["pair_id"], "labels": labels,
                                       "summary": summary, "is_gold": False}}


def _risk(root: Path, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if not case.get("scenario"):
        return {"status": "NOT_REQUESTED", "output": None}
    result = RiskService(root).assess(case["scenario"])
    return {"status": "OK" if result["risk_level"] is not None else "UNRESOLVED", "output": result}


def _normal(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


STAGE_FUNCTIONS: dict[str, Callable[[Path, dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "source": _source, "graph": _graph, "applicability": _applicability, "materiality": _materiality, "risk": _risk,
}
