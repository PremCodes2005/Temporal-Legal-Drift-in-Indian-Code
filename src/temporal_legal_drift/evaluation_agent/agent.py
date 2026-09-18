"""Agentic audit of the Temporal Legal Drift research implementation.

The agent selects and executes read-only evaluators, reconciles their evidence,
and emits explicit limitations.  It never fabricates legal approval or modifies
research data in order to make a gate pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..gates import check_engineering_gates
from ..jsonio import load_json
from ..rag.metrics import _aggregate_drift


@dataclass(frozen=True)
class ComponentFinding:
    component: str
    status: str
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "component": self.component,
            "status": self.status,
            "evidence": list(self.evidence),
            "limitations": list(self.limitations),
        }


class ProjectEvaluationAgent:
    """Run a deterministic audit plan over repository evidence.

    This is deliberately a bounded agent: it can inspect, classify and
    recommend, but cannot grant legal validation or silently change artefacts.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._evaluators: tuple[Callable[[], ComponentFinding], ...] = (
            self._materiality,
            self._version_graph,
            self._compliance_drift,
            self._hallucination_detection,
            self._benchmark,
            self._metrics,
            self._collection_pipeline,
        )

    def evaluate(self) -> dict[str, object]:
        findings = [evaluator() for evaluator in self._evaluators]
        try:
            gates = check_engineering_gates(self.root)
            gate_payload = [gate.to_dict() for gate in gates]
        except (OSError, ValueError, KeyError) as error:
            gate_payload = []
            gate_error = f"{type(error).__name__}: {error}"
        else:
            gate_error = None

        counts = {
            status: sum(item.status == status for item in findings)
            for status in ("implemented_prototype", "partial", "not_implemented")
        }
        return {
            "audit_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "engineering evidence only; not a patentability or legal-correctness opinion",
            "agent_policy": {
                "read_only_evaluation": True,
                "autonomous_legal_approval": False,
                "unsupported_claims_forbidden": True,
            },
            "summary": counts,
            "components": [item.to_dict() for item in findings],
            "phase_gates": gate_payload,
            "gate_evaluation_error": gate_error,
            "overall_status": (
                "complete" if all(item.status == "implemented_prototype" for item in findings)
                else "incomplete_research_prototype"
            ),
        }

    def _exists(self, relative: str) -> bool:
        return (self.root / relative).is_file()

    def _materiality(self) -> ComponentFinding:
        workload_path = self.root / "data/annotations/phase5_workload.v1.json"
        workload = load_json(workload_path) if workload_path.is_file() else {}
        tasks = workload.get("tasks", []) if isinstance(workload, dict) else []
        gold = sum(
            isinstance(task, dict)
            and isinstance(task.get("materiality"), dict)
            and task["materiality"].get("label") in {"High", "Medium", "Low", "None"}
            for task in tasks if isinstance(task, dict)
        )
        evidence = (
            "configs/annotation/materiality_taxonomy.v1.json",
            "src/temporal_legal_drift/materiality/builder.py",
            f"gold materiality labels observed: {gold}",
        )
        return ComponentFinding(
            "regulatory_amendment_materiality_classifier",
            "implemented_prototype" if gold > 0 else "partial",
            evidence,
            (() if gold > 0 else ("No expert-labelled gold materiality examples are available.",)),
        )

    def _version_graph(self) -> ComponentFinding:
        graph = self.root / "data/interim/version_graph.v1.json"
        return ComponentFinding(
            "temporal_legal_knowledge_graph",
            "implemented_prototype" if graph.is_file() else "not_implemented",
            ("data/interim/version_graph.v1.json", "schemas/temporal/version_graph.schema.json"),
            ("Historical reconstruction and applicability still require qualified legal validation.",),
        )

    def _compliance_drift(self) -> ComponentFinding:
        present = self._exists("src/temporal_legal_drift/llm_evaluation/runner.py")
        return ComponentFinding(
            "compliance_drift_detection_engine",
            "implemented_prototype" if present else "not_implemented",
            ("src/temporal_legal_drift/llm_evaluation/runner.py", "src/temporal_legal_drift/metrics/core.py"),
            ("Publishable performance cannot be calculated without frozen scenario gold labels.",),
        )

    def _hallucination_detection(self) -> ComponentFinding:
        return ComponentFinding(
            "llm_temporal_hallucination_detector",
            "partial",
            ("src/temporal_legal_drift/explanations/evaluator.py", "schemas/evaluation/explanation_evaluation.schema.json"),
            ("Detects version, citation and explanation inconsistencies; it is not a universal hallucination detector.",),
        )

    def _benchmark(self) -> ComponentFinding:
        release = self.root / "data/releases/tech-preview-v0.1.0/manifest.json"
        payload = load_json(release) if release.is_file() else {}
        frozen = payload.get("benchmark_frozen") is True if isinstance(payload, dict) else False
        return ComponentFinding(
            "benchmark_dataset",
            "implemented_prototype" if frozen else "partial",
            ("data/releases/tech-preview-v0.1.0/manifest.json", "reports/phase7/data_card.md"),
            (() if frozen else ("The technical preview is not a frozen, expert-validated benchmark.",)),
        )

    def _metrics(self) -> ComponentFinding:
        extreme = _aggregate_drift(
            {"semantic": 0.0, "conceptual": 100.0},
            {"semantic": 0.5, "conceptual": 0.5},
        )
        valid = round(extreme, 1) == 70.7
        return ComponentFinding(
            "evaluation_metrics",
            "implemented_prototype" if valid else "partial",
            ("src/temporal_legal_drift/rag/metrics.py", f"0/100 aggregation self-check: {extreme:.1f}, not 50.0"),
            ("Metric scores are technical diagnostics, not probabilities or legal-correctness scores.",),
        )

    def _collection_pipeline(self) -> ComponentFinding:
        manifest_path = self.root / "configs/corpus/pilot_v1.json"
        manifest = load_json(manifest_path) if manifest_path.is_file() else {}
        entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
        return ComponentFinding(
            "data_collection_pipeline",
            "implemented_prototype" if entries else "not_implemented",
            ("src/temporal_legal_drift/acquisition/fetch.py", f"bounded manifest entries: {len(entries)}"),
            ("The bounded corpus is not complete coverage of every India Code Act and amendment.",),
        )
