"""Command-line entry point for the Phase 0-11 research foundation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .acquisition import AcquisitionService, RawArtifactStore, SourcePolicy, SourceRequest
from .acquisition.models import SourceArtifact
from .amendment_extraction.checkpoint import build_phase2_checkpoint
from .amendment_extraction.pipeline import AmendmentExtractionPipeline
from .amendment_extraction.silver_checkpoint import build_silver_label_checkpoint
from .applicability import ApplicabilityQuery, ApplicabilityResolver, TemporalFact
from .applicability.candidates import extract_temporal_candidates, write_candidates_and_lock
from .applicability.cross_validation import (
    validate_cross_source_consistency,
    write_cross_validation_and_lock,
)
from .benchmark import build_technical_release, write_technical_release_and_lock
from .baselines import build_baseline_dry_run, write_baseline_dry_run_and_lock
from .corpus import CorpusDownloader, CorpusManifest, materialize_corpus
from .corpus.normalize import normalize_corpus
from .corpus.report import build_corpus_report, write_corpus_report
from .errors import TemporalLegalDriftError
from .explanations import build_explanation_evaluation_plan, write_explanation_plan_and_lock
from .evaluation_agent import ProjectEvaluationAgent
from .gates import check_engineering_gates
from .ingestion.checkpoint import build_phase1_checkpoint
from .jsonio import load_json
from .materiality import (
    build_annotation_workload,
    build_materiality_round,
    build_materiality_silver,
    assess_materiality_with_llm,
    build_disagreement_report,
    build_disagreement_audit_v2,
    render_disagreement_audit_v2,
    build_materiality_ensemble,
    compute_annotation_agreement,
    evaluate_materiality_gold,
    freeze_materiality_gold,
    freeze_materiality_silver,
    render_none_coverage_report,
    search_potential_none_cases,
    write_annotation_workload_and_lock,
    write_materiality_round,
    write_materiality_silver,
    write_llm_assessments,
    write_ensemble,
)
from .llm_evaluation import (
    build_drift_evaluation_from_executed_plan,
    build_llm_evaluation_plan,
    execute_controlled_plan_with_codex_cli,
    score_paired_assertions,
    write_llm_plan_and_lock,
)
from .parsing.service import NormalizationService
from .parsing.store import NormalizedDocumentStore, QuarantineStore
from .phase0 import validate_contract_file
from .reproducibility import verify_fresh_environment, write_reproducibility_manifest_and_lock
from .reproducibility.builder import stage_current_artifact_checksums
from .scenarios import build_scenario_scaffolds, write_scenarios_and_lock
from .risk.builder import write_risk_checkpoint
from .risk.service import RiskService
from .versioning import TemporalGraph, TemporalGraphBuilder, VersionGraph, VersionGraphBuilder
from .versioning.builder import write_graph_and_lock
from .versioning.temporal_graph import write_temporal_graph_and_checkpoint
from .webapp import serve_dashboard


def _project_root() -> Path:
    return Path.cwd()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tldrift")
    parser.add_argument("--project-root", type=Path, default=_project_root())
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-contract")
    validate.add_argument("--contract", type=Path, default=Path("configs/research_contract.v1.json"))

    acquire = subparsers.add_parser("acquire")
    acquire.add_argument("--url", required=True)
    acquire.add_argument("--official-id", required=True)
    acquire.add_argument("--instrument-type", required=True)
    acquire.add_argument("--notes")
    acquire.add_argument("--policy", type=Path, default=Path("configs/source_policy.v1.json"))

    subparsers.add_parser("build-ingestion-checkpoint")
    subparsers.add_parser("build-amendment-extraction-checkpoint")
    subparsers.add_parser("build-amendment-silver-labels")
    subparsers.add_parser("build-risk-checkpoint")
    assess_risk = subparsers.add_parser("assess-risk")
    assess_risk.add_argument("--scenario", type=Path, required=True)

    normalize = subparsers.add_parser("normalize")
    normalize.add_argument("--metadata", type=Path, required=True)

    download_corpus = subparsers.add_parser("download-corpus")
    download_corpus.add_argument(
        "--manifest", type=Path, default=Path("configs/corpus/pilot_v1.json")
    )
    download_corpus.add_argument(
        "--policy", type=Path, default=Path("configs/source_policy.v1.json")
    )
    download_corpus.add_argument("--refresh", action="store_true")

    materialize = subparsers.add_parser("materialize-corpus")
    materialize.add_argument(
        "--manifest", type=Path, default=Path("configs/corpus/pilot_v1.json")
    )
    materialize.add_argument(
        "--output", type=Path, default=Path("data/corpus/pdfs")
    )

    normalize_corpus_parser = subparsers.add_parser("normalize-corpus")
    normalize_corpus_parser.add_argument(
        "--manifest", type=Path, default=Path("configs/corpus/pilot_v1.json")
    )

    corpus_report = subparsers.add_parser("corpus-report")
    corpus_report.add_argument(
        "--manifest", type=Path, default=Path("configs/corpus/pilot_v1.json")
    )
    corpus_report.add_argument(
        "--output",
        type=Path,
        default=Path("reports/corpus/india-code-temporal-pilot-v1.lock.json"),
    )

    check_gates = subparsers.add_parser("check-gates")
    check_gates.add_argument("--through-phase", type=int)

    audit = subparsers.add_parser("audit-project")
    audit.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report path. The audit is printed even when this is omitted.",
    )

    build_graph = subparsers.add_parser("build-version-graph")
    build_graph.add_argument(
        "--manifest", type=Path, default=Path("configs/corpus/pilot_v1.json")
    )
    build_graph.add_argument(
        "--corpus-report",
        type=Path,
        default=Path("reports/corpus/india-code-temporal-pilot-v1.lock.json"),
    )
    build_graph.add_argument(
        "--relations",
        type=Path,
        default=Path("configs/versioning/instrument_relations.v1.json"),
    )
    build_graph.add_argument(
        "--output", type=Path, default=Path("data/interim/version_graph.v1.json")
    )
    build_graph.add_argument(
        "--lock", type=Path, default=Path("reports/phase3/version_graph.lock.json")
    )

    subparsers.add_parser("build-temporal-knowledge-graph")
    point_query = subparsers.add_parser("get-provision-version")
    point_query.add_argument(
        "--graph", type=Path, default=Path("data/interim/temporal_legal_knowledge_graph.v2.json")
    )
    point_query.add_argument("--act", required=True)
    point_query.add_argument("--section", required=True)
    point_query.add_argument("--date", required=True)

    resolve = subparsers.add_parser("resolve-applicability")
    resolve.add_argument(
        "--graph", type=Path, default=Path("data/interim/version_graph.v1.json")
    )
    resolve.add_argument("--facts", type=Path, required=True)
    resolve.add_argument("--scenario-id", required=True)
    resolve.add_argument("--lineage-id", required=True)
    resolve.add_argument("--reference-date", required=True)
    resolve.add_argument("--attributes-json", default="{}")

    temporal_candidates = subparsers.add_parser("build-temporal-candidates")
    temporal_candidates.add_argument(
        "--graph", type=Path, default=Path("data/interim/version_graph.v1.json")
    )
    temporal_candidates.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/temporal_fact_candidates.v1.json"),
    )
    temporal_candidates.add_argument(
        "--lock",
        type=Path,
        default=Path("reports/phase4/temporal_candidates.lock.json"),
    )

    cross_validation = subparsers.add_parser("validate-cross-version")
    cross_validation.add_argument(
        "--graph", type=Path, default=Path("data/interim/version_graph.v1.json")
    )
    cross_validation.add_argument(
        "--facts", type=Path, default=Path("data/interim/temporal_fact_candidates.v1.json")
    )
    cross_validation.add_argument(
        "--config", type=Path, default=Path("configs/validation/cross_version.v1.json")
    )
    cross_validation.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/cross_version_validation.v1.json"),
    )
    cross_validation.add_argument(
        "--lock",
        type=Path,
        default=Path("reports/phase4/cross_version_validation.lock.json"),
    )

    phase5 = subparsers.add_parser("build-annotation-workload")
    phase5.add_argument(
        "--graph", type=Path, default=Path("data/interim/version_graph.v1.json")
    )
    phase5.add_argument(
        "--cross-validation",
        type=Path,
        default=Path("data/interim/cross_version_validation.v1.json"),
    )
    phase5.add_argument(
        "--taxonomy",
        type=Path,
        default=Path("configs/annotation/materiality_taxonomy.v1.json"),
    )
    phase5.add_argument("--pilot-size", type=int, default=50)
    phase5.add_argument(
        "--output", type=Path, default=Path("data/annotations/phase5_workload.v1.json")
    )
    phase5.add_argument(
        "--lock", type=Path, default=Path("reports/phase5/annotation_workload.lock.json")
    )

    materiality_round = subparsers.add_parser("build-materiality-annotation-round")
    materiality_round.add_argument(
        "--graph", type=Path, default=Path("data/interim/temporal_legal_knowledge_graph.v2.json")
    )
    materiality_round.add_argument(
        "--taxonomy", type=Path, default=Path("configs/annotation/materiality_taxonomy.v1.json")
    )
    materiality_round.add_argument("--pilot-size", type=int, default=50)
    materiality_round.add_argument(
        "--output", type=Path, default=Path("data/annotations/materiality_annotation_round.v1.json")
    )
    materiality_round.add_argument(
        "--lock", type=Path, default=Path("reports/materiality/annotation_round.lock.json")
    )

    materiality_silver = subparsers.add_parser("build-materiality-silver")
    materiality_silver.add_argument(
        "--round", type=Path, default=Path("data/annotations/materiality_annotation_round.v1.json")
    )
    materiality_silver.add_argument(
        "--output", type=Path, default=Path("data/silver/materiality_silver_labels.v1.json")
    )
    materiality_silver.add_argument(
        "--lock", type=Path, default=Path("reports/materiality/materiality_silver.lock.json")
    )
    materiality_silver.add_argument(
        "--report", type=Path, default=Path("reports/materiality/automated_silver_evaluation.v1.md")
    )
    materiality_silver.add_argument(
        "--disagreements", type=Path, default=Path("reports/materiality/silver_disagreement_review.v1.md")
    )

    none_search = subparsers.add_parser("search-materiality-none")
    none_search.add_argument(
        "--graph", type=Path, default=Path("data/interim/temporal_legal_knowledge_graph.v2.json")
    )
    none_search.add_argument(
        "--output", type=Path, default=Path("reports/materiality/none_coverage_search.v1.json")
    )
    none_search.add_argument(
        "--report", type=Path, default=Path("reports/materiality/none_coverage_search.v1.md")
    )

    llm_assessment = subparsers.add_parser("assess-materiality-with-llm")
    llm_assessment.add_argument(
        "--silver", type=Path, default=Path("data/silver/materiality_silver_labels.v1.json")
    )
    llm_assessment.add_argument(
        "--round", type=Path, default=Path("data/annotations/materiality_annotation_round.v1.json")
    )
    llm_assessment.add_argument(
        "--graph", type=Path, default=Path("data/interim/temporal_legal_knowledge_graph.v2.json")
    )
    llm_assessment.add_argument(
        "--rubric", type=Path, default=Path("configs/annotation/proposed_materiality_rubric.v1.json")
    )
    llm_assessment.add_argument(
        "--output", type=Path, default=Path("data/assessments/materiality_llm_assessments.v1.json")
    )
    llm_assessment.add_argument(
        "--lock", type=Path, default=Path("reports/materiality/materiality_llm_assessments.lock.json")
    )

    materiality_ensemble = subparsers.add_parser("build-materiality-ensemble")
    materiality_ensemble.add_argument(
        "--silver", type=Path, default=Path("data/silver/materiality_silver_labels.v1.json")
    )
    materiality_ensemble.add_argument(
        "--assessments", type=Path, default=Path("data/assessments/materiality_llm_assessments.v1.json")
    )
    materiality_ensemble.add_argument(
        "--output", type=Path, default=Path("data/assessments/materiality_ensemble.v1.json")
    )
    materiality_ensemble.add_argument(
        "--lock", type=Path, default=Path("reports/materiality/materiality_ensemble.lock.json")
    )

    freeze_silver = subparsers.add_parser("freeze-materiality-silver")
    freeze_silver.add_argument(
        "--dataset", type=Path, default=Path("data/silver/materiality_silver_labels.v1.json")
    )
    freeze_silver.add_argument(
        "--lock", type=Path, default=Path("reports/materiality/materiality_silver_frozen.lock.json")
    )

    disagreement_audit = subparsers.add_parser("audit-materiality-disagreements")
    disagreement_audit.add_argument("--round", type=Path, default=Path("data/annotations/materiality_annotation_round.v1.json"))
    disagreement_audit.add_argument("--silver", type=Path, default=Path("data/silver/materiality_silver_labels.v1.json"))
    disagreement_audit.add_argument("--graph", type=Path, default=Path("data/interim/temporal_legal_knowledge_graph.v2.json"))
    disagreement_audit.add_argument("--output", type=Path, default=Path("data/silver/materiality_disagreement_audit.v2.3.json"))
    disagreement_audit.add_argument("--report", type=Path, default=Path("reports/materiality/silver_disagreement_review.v2.3.md"))

    agreement = subparsers.add_parser("calculate-materiality-agreement")
    agreement.add_argument(
        "--round", type=Path, default=Path("data/annotations/materiality_annotation_round.v1.json")
    )
    agreement.add_argument("--annotations", type=Path, required=True)
    agreement.add_argument(
        "--output", type=Path, default=Path("reports/materiality/agreement.v1.json")
    )

    freeze_gold = subparsers.add_parser("freeze-materiality-gold")
    freeze_gold.add_argument(
        "--round", type=Path, default=Path("data/annotations/materiality_annotation_round.v1.json")
    )
    freeze_gold.add_argument("--annotations", type=Path, required=True)
    freeze_gold.add_argument("--adjudications", type=Path, required=True)
    freeze_gold.add_argument(
        "--taxonomy", type=Path, default=Path("configs/annotation/materiality_taxonomy.v1.json")
    )
    freeze_gold.add_argument(
        "--output", type=Path, default=Path("data/gold/materiality_gold_v1.json")
    )
    freeze_gold.add_argument(
        "--lock", type=Path, default=Path("reports/materiality/materiality_gold.lock.json")
    )

    materiality_evaluation = subparsers.add_parser("evaluate-materiality-gold")
    materiality_evaluation.add_argument(
        "--gold", type=Path, default=Path("data/gold/materiality_gold_v1.json")
    )
    materiality_evaluation.add_argument("--split", type=Path, required=True)
    materiality_evaluation.add_argument("--epochs", type=int, default=350)
    materiality_evaluation.add_argument(
        "--output", type=Path, default=Path("experiments/materiality/materiality_models.v1.json")
    )

    phase6 = subparsers.add_parser("build-scenario-scaffolds")
    phase6.add_argument(
        "--workload", type=Path, default=Path("data/annotations/phase5_workload.v1.json")
    )
    phase6.add_argument(
        "--cross-validation",
        type=Path,
        default=Path("data/interim/cross_version_validation.v1.json"),
    )
    phase6.add_argument(
        "--coverage",
        type=Path,
        default=Path("configs/scenarios/coverage_requirements.v1.json"),
    )
    phase6.add_argument(
        "--output", type=Path, default=Path("data/scenarios/phase6_scaffolds.v1.json")
    )
    phase6.add_argument(
        "--lock", type=Path, default=Path("reports/phase6/scenario_scaffolds.lock.json")
    )

    phase7 = subparsers.add_parser("build-technical-release")
    phase7.add_argument(
        "--workload", type=Path, default=Path("data/annotations/phase5_workload.v1.json")
    )
    phase7.add_argument(
        "--scenarios", type=Path, default=Path("data/scenarios/phase6_scaffolds.v1.json")
    )
    phase7.add_argument(
        "--graph", type=Path, default=Path("data/interim/version_graph.v1.json")
    )
    phase7.add_argument(
        "--config", type=Path, default=Path("configs/benchmark/release.v1.json")
    )
    phase7.add_argument(
        "--output",
        type=Path,
        default=Path("data/releases/tech-preview-v0.1.0/manifest.json"),
    )
    phase7.add_argument(
        "--lock", type=Path, default=Path("reports/phase7/release.lock.json")
    )

    phase8 = subparsers.add_parser("prepare-baselines")
    phase8.add_argument(
        "--workload", type=Path, default=Path("data/annotations/phase5_workload.v1.json")
    )
    phase8.add_argument(
        "--release",
        type=Path,
        default=Path("data/releases/tech-preview-v0.1.0/manifest.json"),
    )
    phase8.add_argument(
        "--config", type=Path, default=Path("configs/experiments/baselines.v1.json")
    )
    phase8.add_argument(
        "--output", type=Path, default=Path("experiments/phase8/baseline_dry_run.v1.json")
    )
    phase8.add_argument(
        "--lock", type=Path, default=Path("reports/phase8/baseline_dry_run.lock.json")
    )

    phase9 = subparsers.add_parser("build-llm-evaluation-plan")
    phase9.add_argument(
        "--scenarios", type=Path, default=Path("data/scenarios/phase6_scaffolds.v1.json")
    )
    phase9.add_argument(
        "--release",
        type=Path,
        default=Path("data/releases/tech-preview-v0.1.0/manifest.json"),
    )
    phase9.add_argument(
        "--baseline-run",
        type=Path,
        default=Path("experiments/phase8/baseline_dry_run.v1.json"),
    )
    phase9.add_argument(
        "--config", type=Path, default=Path("configs/experiments/temporal_llm.v1.json")
    )
    phase9.add_argument(
        "--prompt", type=Path, default=Path("configs/prompts/compliance_reasoning.v1.json")
    )
    phase9.add_argument(
        "--output", type=Path, default=Path("experiments/phase9/evaluation_plan.v1.json")
    )
    phase9.add_argument(
        "--lock", type=Path, default=Path("reports/phase9/evaluation_plan.lock.json")
    )

    execute_phase9 = subparsers.add_parser("execute-llm-evaluation")
    execute_phase9.add_argument(
        "--plan", type=Path, default=Path("experiments/phase9/evaluation_plan.v1.json")
    )
    execute_phase9.add_argument(
        "--scenarios", type=Path, default=Path("data/scenarios/phase6_scaffolds.v1.json")
    )
    execute_phase9.add_argument(
        "--graph", type=Path, default=Path("data/interim/version_graph.v1.json")
    )
    execute_phase9.add_argument(
        "--config", type=Path, default=Path("configs/experiments/temporal_llm.v1.json")
    )
    execute_phase9.add_argument(
        "--prompt", type=Path, default=Path("configs/prompts/compliance_reasoning.v1.json")
    )
    execute_phase9.add_argument(
        "--codex-command", default="codex"
    )
    execute_phase9.add_argument("--timeout-seconds", type=int, default=1800)
    execute_phase9.add_argument(
        "--output", type=Path, default=Path("experiments/phase9/evaluation_plan.v1.json")
    )
    execute_phase9.add_argument(
        "--lock", type=Path, default=Path("reports/phase9/evaluation_plan.lock.json")
    )

    score_drift = subparsers.add_parser("score-drift-pairs")
    score_drift.add_argument("--pairs", type=Path, required=True)

    score_executed = subparsers.add_parser("score-executed-drift")
    score_executed.add_argument("--plan", type=Path, required=True)
    score_executed.add_argument("--scenarios", type=Path, required=True)
    score_executed.add_argument("--output", type=Path, required=True)

    phase10 = subparsers.add_parser("build-explanation-evaluation-plan")
    phase10.add_argument(
        "--llm-plan", type=Path, default=Path("experiments/phase9/evaluation_plan.v1.json")
    )
    phase10.add_argument(
        "--scenarios", type=Path, default=Path("data/scenarios/phase6_scaffolds.v1.json")
    )
    phase10.add_argument(
        "--workload", type=Path, default=Path("data/annotations/phase5_workload.v1.json")
    )
    phase10.add_argument(
        "--graph", type=Path, default=Path("data/interim/version_graph.v1.json")
    )
    phase10.add_argument(
        "--rubric",
        type=Path,
        default=Path("configs/experiments/explanation_rubric.v1.json"),
    )
    phase10.add_argument(
        "--output", type=Path, default=Path("experiments/phase10/explanation_plan.v1.json")
    )
    phase10.add_argument(
        "--lock", type=Path, default=Path("reports/phase10/explanation_plan.lock.json")
    )

    phase11 = subparsers.add_parser("verify-reproducibility")
    phase11.add_argument("--timeout-seconds", type=int, default=900)
    phase11.add_argument(
        "--output",
        type=Path,
        default=Path("data/releases/reproducibility-v0.1.0/manifest.json"),
    )
    phase11.add_argument(
        "--lock", type=Path, default=Path("reports/phase11/reproducibility.lock.json")
    )

    dashboard = subparsers.add_parser("serve-dashboard")
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8765)
    return parser


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def run(args: argparse.Namespace) -> int:
    root = args.project_root.resolve()
    if args.command == "validate-contract":
        result = validate_contract_file(_resolve(root, args.contract))
        print(
            json.dumps(
                {
                    "structurally_valid": result.structurally_valid,
                    "engineering_check_passed": result.structurally_valid,
                    "research_legal_gate_passed": result.gate_passed,
                    "errors": list(result.errors),
                    "human_review_blockers": list(result.blockers),
                },
                indent=2,
            )
        )
        return 0 if result.structurally_valid else 2

    if args.command == "acquire":
        policy = SourcePolicy.from_file(_resolve(root, args.policy))
        store = RawArtifactStore(root / "data" / "raw")
        artifact = AcquisitionService(policy, store).acquire(
            SourceRequest(args.url, args.official_id, args.instrument_type, args.notes)
        )
        print(json.dumps(artifact.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-ingestion-checkpoint":
        result = build_phase1_checkpoint(root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-amendment-extraction-checkpoint":
        result = build_phase2_checkpoint(root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-amendment-silver-labels":
        result = build_silver_label_checkpoint(root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "normalize":
        value = load_json(_resolve(root, args.metadata))
        artifact = SourceArtifact(**value)
        service = NormalizationService(
            NormalizedDocumentStore(root / "data" / "normalized"),
            QuarantineStore(root / "data" / "quarantine"),
        )
        document = service.normalize(artifact, root / "data" / "raw")
        print(json.dumps(document.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "download-corpus":
        manifest = CorpusManifest.from_file(_resolve(root, args.manifest))
        policy = SourcePolicy.from_file(_resolve(root, args.policy))
        store = RawArtifactStore(root / "data" / "raw")
        summary = CorpusDownloader(
            AcquisitionService(policy, store),
            store,
        ).download(manifest, refresh=args.refresh)
        print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "materialize-corpus":
        manifest = CorpusManifest.from_file(_resolve(root, args.manifest))
        summary = materialize_corpus(
            manifest,
            RawArtifactStore(root / "data" / "raw"),
            _resolve(root, args.output),
        )
        print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "normalize-corpus":
        manifest = CorpusManifest.from_file(_resolve(root, args.manifest))
        raw_store = RawArtifactStore(root / "data" / "raw")
        service = NormalizationService(
            NormalizedDocumentStore(root / "data" / "normalized"),
            QuarantineStore(root / "data" / "quarantine"),
        )
        summary = normalize_corpus(manifest, raw_store, service)
        print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "corpus-report":
        manifest = CorpusManifest.from_file(_resolve(root, args.manifest))
        report = build_corpus_report(
            manifest,
            RawArtifactStore(root / "data" / "raw"),
            root / "data" / "normalized",
        )
        output = _resolve(root, args.output)
        write_corpus_report(output, report)
        print(json.dumps({"output": str(output), **report}, indent=2, ensure_ascii=False))
        return 0

    if args.command == "check-gates":
        results = check_engineering_gates(root, through_phase=args.through_phase)
        passed = all(result.engineering_passed for result in results)
        print(
            json.dumps(
                {
                    "engineering_gates_passed": passed,
                    "qualified_review_complete": all(
                        result.review_status == "approved" for result in results
                    ),
                    "phases": [result.to_dict() for result in results],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if passed else 2

    if args.command == "audit-project":
        result = ProjectEvaluationAgent(root).evaluate()
        if args.output:
            from .jsonio import atomic_replace, canonical_json_bytes

            atomic_replace(_resolve(root, args.output), canonical_json_bytes(result))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-version-graph":
        manifest = CorpusManifest.from_file(_resolve(root, args.manifest))
        graph = VersionGraphBuilder().build(
            manifest,
            load_json(_resolve(root, args.corpus_report)),
            root / "data" / "normalized",
            load_json(_resolve(root, args.relations)),
        )
        summary = write_graph_and_lock(
            graph,
            _resolve(root, args.output),
            _resolve(root, args.lock),
        )
        print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-temporal-knowledge-graph":
        graph = TemporalGraphBuilder().build(root)
        checkpoint = write_temporal_graph_and_checkpoint(graph, root)
        print(json.dumps(checkpoint, indent=2, ensure_ascii=False))
        return 0

    if args.command == "get-provision-version":
        graph = TemporalGraph.from_dict(load_json(_resolve(root, args.graph)))
        result = graph.get_provision_version(args.act, args.section, args.date)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "resolve-applicability":
        graph = VersionGraph.from_dict(load_json(_resolve(root, args.graph)))
        fact_document = load_json(_resolve(root, args.facts))
        raw_facts = fact_document.get("facts")
        if not isinstance(raw_facts, list) or not all(isinstance(item, dict) for item in raw_facts):
            raise ValueError("Temporal fact document must contain an array of objects")
        attributes = json.loads(args.attributes_json)
        if not isinstance(attributes, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in attributes.items()
        ):
            raise ValueError("--attributes-json must be an object with string keys and values")
        determination = ApplicabilityResolver(
            graph,
            tuple(TemporalFact.from_dict(item) for item in raw_facts),
        ).resolve(
            ApplicabilityQuery(
                args.scenario_id,
                args.lineage_id,
                date.fromisoformat(args.reference_date),
                attributes,
            )
        )
        print(json.dumps(determination.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-temporal-candidates":
        graph = VersionGraph.from_dict(load_json(_resolve(root, args.graph)))
        facts = extract_temporal_candidates(graph)
        lock = write_candidates_and_lock(
            facts,
            _resolve(root, args.output),
            _resolve(root, args.lock),
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "validate-cross-version":
        graph = VersionGraph.from_dict(load_json(_resolve(root, args.graph)))
        fact_document = load_json(_resolve(root, args.facts))
        raw_facts = fact_document.get("facts")
        if not isinstance(raw_facts, list) or not all(isinstance(item, dict) for item in raw_facts):
            raise ValueError("Temporal fact document must contain an array of objects")
        validation = validate_cross_source_consistency(
            graph,
            tuple(TemporalFact.from_dict(item) for item in raw_facts),
            load_json(_resolve(root, args.config)),
        )
        lock = write_cross_validation_and_lock(
            validation,
            _resolve(root, args.output),
            _resolve(root, args.lock),
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-annotation-workload":
        workload = build_annotation_workload(
            VersionGraph.from_dict(load_json(_resolve(root, args.graph))),
            load_json(_resolve(root, args.cross_validation)),
            load_json(_resolve(root, args.taxonomy)),
            pilot_size=args.pilot_size,
        )
        lock = write_annotation_workload_and_lock(
            workload, _resolve(root, args.output), _resolve(root, args.lock)
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-materiality-annotation-round":
        document = build_materiality_round(
            load_json(_resolve(root, args.graph)),
            load_json(_resolve(root, args.taxonomy)),
            pilot_size=args.pilot_size,
        )
        lock = write_materiality_round(
            document,
            _resolve(root, args.output),
            _resolve(root, args.lock),
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-materiality-silver":
        silver = build_materiality_silver(load_json(_resolve(root, args.round)))
        lock = write_materiality_silver(
            silver, _resolve(root, args.output), _resolve(root, args.lock), _resolve(root, args.report)
        )
        disagreement_report = build_disagreement_report(silver, load_json(_resolve(root, args.round)))
        from .jsonio import atomic_replace

        atomic_replace(_resolve(root, args.disagreements), disagreement_report.encode("utf-8"))
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "freeze-materiality-silver":
        lock = freeze_materiality_silver(_resolve(root, args.dataset), _resolve(root, args.lock), root)
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "audit-materiality-disagreements":
        from .jsonio import atomic_write_new, canonical_json_bytes

        extraction_v2 = AmendmentExtractionPipeline(root).run()
        result = build_disagreement_audit_v2(
            load_json(_resolve(root, args.silver)),
            load_json(_resolve(root, args.round)),
            load_json(_resolve(root, args.graph)),
            extraction_v2["events"],
        )
        atomic_write_new(_resolve(root, args.output), canonical_json_bytes(result))
        atomic_write_new(_resolve(root, args.report), render_disagreement_audit_v2(result).encode("utf-8"))
        print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2, ensure_ascii=False))
        return 0

    if args.command == "search-materiality-none":
        result = search_potential_none_cases(load_json(_resolve(root, args.graph)))
        from .jsonio import atomic_replace, canonical_json_bytes

        atomic_replace(_resolve(root, args.output), canonical_json_bytes(result))
        atomic_replace(_resolve(root, args.report), render_none_coverage_report(result).encode("utf-8"))
        print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2, ensure_ascii=False))
        return 0

    if args.command == "assess-materiality-with-llm":
        result = assess_materiality_with_llm(
            load_json(_resolve(root, args.silver)),
            load_json(_resolve(root, args.round)),
            load_json(_resolve(root, args.graph)),
            load_json(_resolve(root, args.rubric)),
            progress_callback=lambda current, total, pair_id, status: print(
                f"LLM materiality assessment {current}/{total}: {pair_id} [{status}]",
                file=sys.stderr,
                flush=True,
            ),
        )
        lock = write_llm_assessments(result, _resolve(root, args.output), _resolve(root, args.lock))
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-materiality-ensemble":
        result = build_materiality_ensemble(
            load_json(_resolve(root, args.silver)),
            load_json(_resolve(root, args.assessments)),
        )
        lock = write_ensemble(result, _resolve(root, args.output), _resolve(root, args.lock))
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "calculate-materiality-agreement":
        agreement_result = compute_annotation_agreement(
            load_json(_resolve(root, args.round)),
            load_json(_resolve(root, args.annotations)),
        )
        from .jsonio import atomic_replace, canonical_json_bytes

        atomic_replace(_resolve(root, args.output), canonical_json_bytes(agreement_result))
        print(json.dumps(agreement_result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "freeze-materiality-gold":
        gold = freeze_materiality_gold(
            load_json(_resolve(root, args.round)),
            load_json(_resolve(root, args.annotations)),
            load_json(_resolve(root, args.adjudications)),
            load_json(_resolve(root, args.taxonomy)),
        )
        from hashlib import sha256

        from .jsonio import atomic_replace, canonical_json_bytes

        gold_bytes = canonical_json_bytes(gold)
        lock = {
            "schema_version": "1.0.0",
            "status": gold["status"],
            "pair_count": gold["pair_count"],
            "unique_pair_count": len({row["pair_id"] for row in gold["rows"]}),
            "gold_sha256": sha256(gold_bytes).hexdigest(),
            "gold_labels_created": gold["pair_count"],
            "agreement": gold["agreement"],
            "legal_validation_status": gold["legal_validation_status"],
            "legal_correctness_claimed": False,
        }
        atomic_replace(_resolve(root, args.output), gold_bytes)
        atomic_replace(_resolve(root, args.lock), canonical_json_bytes(lock))
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "evaluate-materiality-gold":
        result = evaluate_materiality_gold(
            load_json(_resolve(root, args.gold)),
            load_json(_resolve(root, args.split)),
            epochs=args.epochs,
        )
        from .jsonio import atomic_replace, canonical_json_bytes

        atomic_replace(_resolve(root, args.output), canonical_json_bytes(result))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-risk-checkpoint":
        print(json.dumps(write_risk_checkpoint(root), indent=2))
        return 0

    if args.command == "assess-risk":
        print(json.dumps(RiskService(root).assess(load_json(root / args.scenario)), indent=2))
        return 0

    if args.command == "build-scenario-scaffolds":
        scenarios = build_scenario_scaffolds(
            load_json(_resolve(root, args.workload)),
            load_json(_resolve(root, args.cross_validation)),
            load_json(_resolve(root, args.coverage)),
        )
        lock = write_scenarios_and_lock(
            scenarios, _resolve(root, args.output), _resolve(root, args.lock)
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-technical-release":
        release = build_technical_release(
            load_json(_resolve(root, args.workload)),
            load_json(_resolve(root, args.scenarios)),
            VersionGraph.from_dict(load_json(_resolve(root, args.graph))),
            load_json(_resolve(root, args.config)),
        )
        lock = write_technical_release_and_lock(
            release, _resolve(root, args.output), _resolve(root, args.lock)
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "prepare-baselines":
        document = build_baseline_dry_run(
            load_json(_resolve(root, args.workload)),
            load_json(_resolve(root, args.release)),
            load_json(_resolve(root, args.config)),
        )
        lock = write_baseline_dry_run_and_lock(
            document, _resolve(root, args.output), _resolve(root, args.lock)
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-llm-evaluation-plan":
        document = build_llm_evaluation_plan(
            load_json(_resolve(root, args.scenarios)),
            load_json(_resolve(root, args.release)),
            load_json(_resolve(root, args.baseline_run)),
            load_json(_resolve(root, args.config)),
            load_json(_resolve(root, args.prompt)),
        )
        lock = write_llm_plan_and_lock(
            document, _resolve(root, args.output), _resolve(root, args.lock)
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "execute-llm-evaluation":
        config = load_json(_resolve(root, args.config))
        model = config.get("model")
        if config.get("execution_enabled") is not True or not isinstance(model, str):
            raise ValueError("Phase 9 execution must be enabled with a selected model")
        document = execute_controlled_plan_with_codex_cli(
            load_json(_resolve(root, args.plan)),
            load_json(_resolve(root, args.scenarios)),
            VersionGraph.from_dict(load_json(_resolve(root, args.graph))),
            load_json(_resolve(root, args.prompt)),
            model=model,
            codex_command=args.codex_command,
            timeout_seconds=args.timeout_seconds,
        )
        lock = write_llm_plan_and_lock(
            document, _resolve(root, args.output), _resolve(root, args.lock)
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "score-drift-pairs":
        document = load_json(_resolve(root, args.pairs))
        pairs = document.get("pairs")
        if not isinstance(pairs, list) or not all(isinstance(item, dict) for item in pairs):
            raise ValueError("Drift scoring input requires an array of pair objects")
        print(json.dumps(score_paired_assertions(pairs), indent=2, ensure_ascii=False))
        return 0

    if args.command == "score-executed-drift":
        result = build_drift_evaluation_from_executed_plan(
            load_json(_resolve(root, args.plan)),
            load_json(_resolve(root, args.scenarios)),
        )
        output = _resolve(root, args.output)
        from .jsonio import atomic_replace, canonical_json_bytes

        atomic_replace(output, canonical_json_bytes(result))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.command == "build-explanation-evaluation-plan":
        document = build_explanation_evaluation_plan(
            load_json(_resolve(root, args.llm_plan)),
            load_json(_resolve(root, args.scenarios)),
            load_json(_resolve(root, args.workload)),
            VersionGraph.from_dict(load_json(_resolve(root, args.graph))),
            load_json(_resolve(root, args.rubric)),
        )
        lock = write_explanation_plan_and_lock(
            document, _resolve(root, args.output), _resolve(root, args.lock)
        )
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "verify-reproducibility":
        manifest_path = _resolve(root, args.output)
        lock_path = _resolve(root, args.lock)
        original_manifest, original_lock = stage_current_artifact_checksums(
            root, manifest_path, lock_path
        )
        try:
            document = verify_fresh_environment(root, timeout_seconds=args.timeout_seconds)
            lock = write_reproducibility_manifest_and_lock(document, manifest_path, lock_path)
        except Exception:
            from .jsonio import atomic_replace

            atomic_replace(manifest_path, original_manifest)
            atomic_replace(lock_path, original_lock)
            raise
        print(json.dumps(lock, indent=2, ensure_ascii=False))
        return 0

    if args.command == "serve-dashboard":
        serve_dashboard(root, host=args.host, port=args.port)
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (TemporalLegalDriftError, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
