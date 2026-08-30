"""Command-line entry point for the Phase 0-11 research foundation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .acquisition import AcquisitionService, RawArtifactStore, SourcePolicy, SourceRequest
from .acquisition.models import SourceArtifact
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
from .gates import check_engineering_gates
from .jsonio import load_json
from .materiality import build_annotation_workload, write_annotation_workload_and_lock
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
from .scenarios import build_scenario_scaffolds, write_scenarios_and_lock
from .versioning import VersionGraph, VersionGraphBuilder
from .versioning.builder import write_graph_and_lock
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
        document = verify_fresh_environment(root, timeout_seconds=args.timeout_seconds)
        lock = write_reproducibility_manifest_and_lock(
            document, _resolve(root, args.output), _resolve(root, args.lock)
        )
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
