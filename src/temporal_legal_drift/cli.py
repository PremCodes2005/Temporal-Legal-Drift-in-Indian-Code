"""Command-line entry point for the Phase 0-2 foundation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .acquisition import AcquisitionService, RawArtifactStore, SourcePolicy, SourceRequest
from .acquisition.models import SourceArtifact
from .corpus import CorpusDownloader, CorpusManifest
from .corpus.normalize import normalize_corpus
from .corpus.report import build_corpus_report, write_corpus_report
from .errors import TemporalLegalDriftError
from .gates import check_engineering_gates
from .jsonio import load_json
from .parsing.service import NormalizationService
from .parsing.store import NormalizedDocumentStore, QuarantineStore
from .phase0 import validate_contract_file


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
