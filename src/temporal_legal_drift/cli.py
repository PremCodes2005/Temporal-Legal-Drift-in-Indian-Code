"""Command-line entry point for the Phase 0-4 foundation."""

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
from .corpus import CorpusDownloader, CorpusManifest, materialize_corpus
from .corpus.normalize import normalize_corpus
from .corpus.report import build_corpus_report, write_corpus_report
from .errors import TemporalLegalDriftError
from .gates import check_engineering_gates
from .jsonio import load_json
from .parsing.service import NormalizationService
from .parsing.store import NormalizedDocumentStore, QuarantineStore
from .phase0 import validate_contract_file
from .versioning import VersionGraph, VersionGraphBuilder
from .versioning.builder import write_graph_and_lock


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

    subparsers.add_parser("check-gates")

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
        results = check_engineering_gates(root)
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
