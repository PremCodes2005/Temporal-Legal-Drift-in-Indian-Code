"""Build a traceable Phase 11 engineering reproducibility record."""

from __future__ import annotations

import gzip
import io
import os
import platform
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from temporal_legal_drift.jsonio import atomic_replace, atomic_write_new, canonical_json_bytes, load_json


ACTIVE_RELEASE = "data/releases/active_release.json"
# Gitignored local artifacts the tests, gates and graph builds read. A release
# ships them as hash-verified gzip inputs; raw PDF blobs are rebuilt from the
# tracked data/corpus/pdfs copies by content hash instead of being duplicated.
RELEASE_INPUT_GLOBS = (
    "data/normalized/doc_*.json",
    "data/raw/metadata/*.json",
    "data/raw/checkpoints/*.json",
    "data/interim/version_graph.v1.json",
    "data/interim/temporal_legal_knowledge_graph.v2.json",
    "data/interim/phase3_transition_validation_candidates.v1.json",
    "data/interim/temporal_legal_knowledge_graph.v3.json",
    "data/interim/phase3_transition_validation_candidates.v3.json",
    "data/interim/temporal_legal_knowledge_graph.v4.json",
    "data/interim/phase3_transition_validation_candidates.v4.json",
    "data/interim/temporal_fact_candidates.v1.json",
    "data/interim/cross_version_validation.v1.json",
)
# Write-once builders re-run in the fresh copy; each exits non-zero unless it
# regenerates byte-identical output.
REBUILD_COMMANDS = (
    ("build-amendment-extraction-version", "--version", "v2.2", "--previous", "v2.1"),
    ("build-amendment-silver-labels", "--extraction-version", "v2.1"),
    ("build-temporal-knowledge-graph", "--graph-version", "v3"),
    ("build-amendment-silver-labels", "--extraction-version", "v2.2"),
    ("build-temporal-knowledge-graph", "--graph-version", "v4"),
)


REQUIRED_ARTIFACTS = (
    "configs/research_contract.v1.json",
    "configs/corpus/pilot_v1.json",
    "reports/corpus/india-code-temporal-pilot-v1.lock.json",
    "data/processed/amendments/v1/extraction.json",
    "data/processed/amendments/v1/silver_labels.v1.json",
    "reports/phase2/amendment_extraction_checkpoint.v1.json",
    "reports/phase2/silver_label_checkpoint.v1.json",
    "reports/phase3/version_graph.lock.json",
    "data/interim/temporal_legal_knowledge_graph.v2.json",
    "data/interim/phase3_transition_validation_candidates.v1.json",
    "reports/phase3/temporal_graph_checkpoint.v2.json",
    "schemas/temporal/temporal_legal_knowledge_graph.v2.schema.json",
    "schemas/temporal/phase3_transition_validation_candidates.v1.schema.json",
    "protocols/temporal_graph_protocol.v2.md",
    "reports/phase4/cross_version_validation.lock.json",
    "reports/phase5/annotation_workload.lock.json",
    "data/annotations/materiality_annotation_round.v1.json",
    "reports/materiality/annotation_round.lock.json",
    "data/silver/materiality_silver_labels.v1.json",
    "reports/materiality/materiality_silver.lock.json",
    "reports/materiality/materiality_silver_frozen.lock.json",
    "reports/materiality/automated_silver_evaluation.v1.md",
    "reports/materiality/silver_disagreement_review.v1.md",
    "data/silver/materiality_disagreement_audit.v2.3.json",
    "reports/materiality/silver_disagreement_review.v2.3.md",
    "reports/materiality/none_coverage_search.v1.json",
    "reports/materiality/none_coverage_search.v1.md",
    "reports/materiality/implementation_status.md",
    "data/risk/obligation_registry.v1.json",
    "data/risk/compliance_scenarios.v1.json",
    "experiments/risk/baseline_results.v1.json",
    "reports/risk/checkpoint.v1.json",
    "reports/risk/checkpoint.v1.md",
    "reports/risk/phase4_preflight.v1.json",
    "reports/risk/phase4_audit.v1.md",
    "configs/annotation/proposed_materiality_rubric.v1.json",
    "schemas/annotation/materiality_llm_assessment.v1.schema.json",
    "schemas/annotation/materiality_llm_assessment_run.v1.schema.json",
    "schemas/annotation/materiality_ensemble.v1.schema.json",
    "configs/experiments/materiality_classifiers.v1.json",
    "reports/phase6/scenario_scaffolds.lock.json",
    "reports/phase7/release.lock.json",
    "reports/phase8/baseline_dry_run.lock.json",
    "reports/phase9/evaluation_plan.lock.json",
    "reports/phase10/explanation_plan.lock.json",
    "data/scenarios/temporal_drift_demo.v1.json",
    "data/processed/amendments/v2.1/extraction.json",
    "data/processed/amendments/v2.2/extraction.json",
    "data/manifests/amendment_extraction_v2.2.provenance.json",
    "data/processed/layout/v1/gazette_furniture.json",
    "data/processed/ocr/v1/it-amendment-act-2008.json",
    "data/processed/amendments/v2.1/silver_labels.v2.1.json",
    "data/manifests/amendment_extraction_v2.1.provenance.json",
    "reports/phase2/silver_label_checkpoint.v2.1.json",
    "data/silver/materiality_disagreement_audit.v2.4.json",
    "reports/materiality/silver_disagreement_review.v2.4.md",
    "data/interim/temporal_legal_knowledge_graph.v3.json",
    "data/interim/phase3_transition_validation_candidates.v3.json",
    "reports/phase3/temporal_graph_checkpoint.v3.json",
    "data/interim/temporal_legal_knowledge_graph.v4.json",
    "data/interim/phase3_transition_validation_candidates.v4.json",
    "reports/phase3/temporal_graph_checkpoint.v4.json",
    "data/processed/amendments/v2.2/silver_labels.v2.2.json",
    "reports/phase2/silver_label_checkpoint.v2.2.json",
    "experiments/phase9/temporal_drift_demo.v1.json",
    "experiments/phase9/temporal_drift_demo.results.v1.json",
    "reports/phase9/temporal_drift_demo.lock.json",
)


def release_paths(release_id: str) -> tuple[str, str]:
    """Manifest and lock paths for one release; v0.1.0 keeps its historical lock name."""
    lock = (
        "reports/phase11/reproducibility.lock.json" if release_id == "v0.1.0"
        else f"reports/phase11/reproducibility-{release_id}.lock.json"
    )
    return f"data/releases/reproducibility-{release_id}/manifest.json", lock


def release_input_paths(root: Path) -> tuple[str, ...]:
    return tuple(sorted({
        str(path.relative_to(root))
        for pattern in RELEASE_INPUT_GLOBS for path in root.glob(pattern) if path.is_file()
    }))


def restore_release_inputs(root: Path) -> dict[str, object]:
    """Materialize the active release's declared inputs; never overwrite differing files."""
    root = root.resolve()
    active = load_json(root / ACTIVE_RELEASE)
    manifest = load_json(root / str(active["manifest_path"]))
    release_dir = (root / str(active["manifest_path"])).parent
    inputs = manifest["release_inputs"]
    for relative, expected in inputs.items():
        payload = gzip.decompress((release_dir / "inputs" / f"{relative}.gz").read_bytes())
        if sha256(payload).hexdigest() != expected:
            raise ValueError(f"Release input does not match its declared hash: {relative}")
        atomic_write_new(root / relative, payload)
    pdf_by_hash = {
        sha256(path.read_bytes()).hexdigest(): path
        for path in (root / "data/corpus/pdfs").glob("*.pdf")
    }
    blobs = 0
    for metadata_path in sorted((root / "data/raw/metadata").glob("*.json")):
        metadata = load_json(metadata_path)
        source = pdf_by_hash.get(str(metadata["sha256"]))
        if source is None:
            raise ValueError(f"No tracked PDF matches raw artifact {metadata_path.name}")
        atomic_write_new(root / "data/raw" / str(metadata["blob_path"]), source.read_bytes())
        blobs += 1
    return {"release_id": active["release_id"], "restored_inputs": len(inputs), "rebuilt_raw_blobs": blobs}


def verify_release(root: Path, release_id: str, *, timeout_seconds: int = 900) -> dict[str, object]:
    """Reproduce a new release from a clean commit and write it once; prior releases are never touched.

    The release binds to HEAD by commit SHA and is committed separately afterwards,
    so no manifest has to hash the commit that contains it.
    """
    root = root.resolve()
    manifest_relative, lock_relative = release_paths(release_id)
    if (root / manifest_relative).exists() or (root / lock_relative).exists():
        raise FileExistsError(f"Release {release_id} already exists; choose a new release ID")
    if _git_state(root)["working_tree_dirty"]:
        raise ValueError("Release verification requires a clean working tree; commit source changes first")
    if (root / ACTIVE_RELEASE).is_file():
        previous = load_json(root / ACTIVE_RELEASE)
    else:  # before any registry existed, v0.1.0 was the implicit active release
        manifest_v010, lock_v010 = release_paths("v0.1.0")
        previous = {
            "release_id": "phase11-reproducibility-engineering-v0.1.0",
            "manifest_path": manifest_v010,
            "lock_path": lock_v010,
            "manifest_sha256": load_json(root / lock_v010)["manifest_sha256"],
        }
    paths = _reproducibility_paths(root)
    missing = [relative for relative in paths if not (root / relative).is_file()]
    if missing:
        raise ValueError(f"Required reproducibility artifacts are missing: {missing}")
    inputs = {relative: sha256((root / relative).read_bytes()).hexdigest() for relative in release_input_paths(root)}
    git = _git_state(root)
    commands = [
        ["<python>", "-m", "venv", "<fresh-venv>"],
        ["<fresh-python>", "-m", "temporal_legal_drift.cli", "restore-release-inputs"],
        *(["<fresh-python>", "-m", "temporal_legal_drift.cli", *command] for command in REBUILD_COMMANDS),
        ["<fresh-python>", "-m", "temporal_legal_drift.cli", "check-gates"],
        ["<fresh-python>", "-m", "unittest", "discover", "-s", "tests", "-v"],
    ]
    with TemporaryDirectory(prefix="tldrift-release-") as temporary_directory:
        temporary = Path(temporary_directory)
        clean = temporary / "checkout"
        archive = subprocess.run(["git", "archive", "--format=tar", git["head"]], cwd=root, capture_output=True, check=True)
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as handle:
            handle.extractall(clean, filter="data")
        release_dir = clean / manifest_relative
        for relative in inputs:
            target = release_dir.parent / "inputs" / f"{relative}.gz"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(gzip.compress((root / relative).read_bytes(), mtime=0))
        document = _release_document(release_id, root, paths, inputs, git, previous)
        # Provisional record exists only inside the throwaway copy so its own
        # Phase 11 gate can run; the real record is written only after success.
        document["executions"] = [{"step": index + 1, "command": command, "exit_code": 0, "provisional": True}
                                  for index, command in enumerate(commands)]
        _write_release(clean, release_id, document, overwrite=True)
        environment = temporary / "venv"
        executions: list[dict[str, object]] = []
        for index, command in enumerate(commands):
            concrete = [
                {"<python>": sys.executable, "<fresh-venv>": str(environment),
                 "<fresh-python>": str(environment / "bin" / "python")}.get(value, value)
                for value in command
            ]
            completed = subprocess.run(
                concrete, cwd=clean, capture_output=True, text=True, timeout=timeout_seconds, check=False,
                env={"PATH": os.environ.get("PATH", ""), "HOME": str(temporary), "PYTHONDONTWRITEBYTECODE": "1",
                     "PYTHONPATH": str(clean / "src")},
            )
            output = completed.stdout + completed.stderr
            executions.append({
                "step": index + 1,
                "command": command,
                "exit_code": completed.returncode,
                "stdout_sha256": sha256(completed.stdout.encode("utf-8")).hexdigest(),
                "stderr_sha256": sha256(completed.stderr.encode("utf-8")).hexdigest(),
                "output_tail": output[-2000:].replace(str(clean), "<clean-checkout>").replace(str(temporary), "<tmp>"),
            })
            if completed.returncode != 0:
                raise ValueError(f"Fresh-environment verification failed at step {index + 1}: {output[-3000:]}")
        document["executions"] = executions
        document["verified_at"] = datetime.now(timezone.utc).isoformat()
        for relative in inputs:
            source = release_dir.parent / "inputs" / f"{relative}.gz"
            target = root / Path(manifest_relative).parent / "inputs" / f"{relative}.gz"
            atomic_write_new(target, source.read_bytes())
    return _write_release(root, release_id, document, overwrite=False)


def _release_document(
    release_id: str, root: Path, paths: tuple[str, ...], inputs: dict[str, str],
    git: dict[str, object], previous: dict[str, object] | None,
) -> dict[str, object]:
    previous_manifest = load_json(root / str(previous["manifest_path"])) if previous else {}
    old_inputs = previous_manifest.get("release_inputs", {})
    old_checksums = previous_manifest.get("artifact_checksums", {})
    checksums = {relative: sha256((root / relative).read_bytes()).hexdigest() for relative in paths}
    return {
        "schema_version": "2.0.0",
        "release_id": f"phase11-reproducibility-engineering-{release_id}",
        "status": "fresh_clean_checkout_engineering_reproduction_passed_expert_review_unavailable",
        "verified_at": "provisional",
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "fresh_virtual_environment": True,
            "system_site_packages": False,
            "clean_checkout_copy": "git archive of the source commit",
            "pdf_extraction_dependency": "pypdf==6.16.2 declared; not installed during verification because normalized text is a frozen release input",
            "package_execution": "isolated_interpreter_with_explicit_project_src_path",
            "network_required": False,
        },
        "git": git,
        "artifact_checksums": checksums,
        "release_inputs": inputs,
        "release_input_policy": (
            "Gitignored local artifacts are shipped as gzip files under inputs/ and restored by "
            "restore-release-inputs only when their SHA-256 matches; raw PDF blobs are rebuilt "
            "from tracked data/corpus/pdfs by content hash."
        ),
        "supersedes": {
            "release_id": previous.get("release_id") if previous else None,
            "manifest_path": previous.get("manifest_path") if previous else None,
            "manifest_sha256": previous.get("manifest_sha256") if previous else None,
            "changed_artifacts": sorted(
                relative for relative in set(old_checksums) & set(checksums)
                if old_checksums[relative] != checksums[relative]
            ),
            "added_artifacts": sorted(set(checksums) - set(old_checksums)),
            "removed_artifacts": sorted(set(old_checksums) - set(checksums)),
            "previous_release_declared_inputs": len(old_inputs),
            "newly_declared_inputs": sorted(set(inputs) - set(old_inputs)),
        },
        "fresh_environment_reproduction_passed": True,
        "independent_expert_validation": {
            "status": "not_performed_reviewer_unavailable",
            "legal_correctness_claimed": False,
        },
        "research_gate_passed": False,
        "limitations": [
            "Engineering reproduction does not replace independent legal-expert validation.",
            "Normalized text is a frozen input: regenerating it from the PDFs with pypdf 6.16.2 matches 99/100 documents; it-amendment-act-2008 differs by one whitespace character.",
            "Graph v2 and extractions v1 and v2.1 are frozen historical artifacts that current code no longer regenerates byte-for-byte.",
            "Layout furniture (pypdf 6.16.2) and the IT 2008 OCR candidate (tesseract 5.5.3) are frozen inputs; their builders need tools not installed in the verification environment.",
            "The benchmark remains unfrozen because materiality and scenario gold are unavailable.",
        ],
    }


def _write_release(root: Path, release_id: str, document: dict[str, object], *, overwrite: bool) -> dict[str, object]:
    manifest_relative, lock_relative = release_paths(release_id)
    payload = canonical_json_bytes(document)
    executions = document["executions"]
    lock = {
        "schema_version": "2.0.0",
        "release_id": document.get("release_id"),
        "manifest_path": manifest_relative,
        "manifest_sha256": sha256(payload).hexdigest(),
        "artifact_count": len(document.get("artifact_checksums", {})),
        "release_input_count": len(document.get("release_inputs", {})),
        "execution_step_count": len(executions),
        "all_execution_steps_passed": bool(executions) and all(item.get("exit_code") == 0 for item in executions),
        "fresh_environment_reproduction_passed": document.get("fresh_environment_reproduction_passed") is True,
        "independent_expert_validation_status": document["independent_expert_validation"]["status"],
        "legal_correctness_claimed": document["independent_expert_validation"]["legal_correctness_claimed"],
        "engineering_gate_passed": True,
        "research_gate_passed": False,
    }
    active = {
        "release_id": document.get("release_id"),
        "manifest_path": manifest_relative,
        "lock_path": lock_relative,
        "manifest_sha256": lock["manifest_sha256"],
    }
    write = atomic_replace if overwrite else atomic_write_new
    write(root / manifest_relative, payload)
    write(root / lock_relative, canonical_json_bytes(lock))
    # The registry is a pointer: activating a release replaces it, never a release.
    atomic_replace(root / ACTIVE_RELEASE, canonical_json_bytes(active))
    return lock


def _git_state(root: Path) -> dict[str, object]:
    def git(*arguments: str) -> str:
        return subprocess.run(["git", *arguments], cwd=root, capture_output=True, text=True, check=True).stdout
    status = git("status", "--porcelain")
    return {
        "head": git("rev-parse", "HEAD").strip(),
        "source_commit_binding": "release artifacts are committed after, and separately from, this commit",
        "working_tree_dirty": bool(status.strip()),
        "status_porcelain_sha256": sha256(status.encode()).hexdigest(),
    }


def _portable_command(command: list[str], root: Path, environment: Path) -> list[str]:
    return [
        value.replace(str(environment), "<fresh-venv>").replace(str(root), "<project-root>")
        for value in command
    ]


def _reproducibility_paths(root: Path) -> tuple[str, ...]:
    values = set(REQUIRED_ARTIFACTS)
    values.add("pyproject.toml")
    for directory in ("configs", "schemas", "src", "tests", "protocols", "frontend", "web"):
        for path in (root / directory).rglob("*"):
            if "node_modules" in path.parts:
                continue
            if path.is_file() and path.suffix in {".py", ".jsx", ".json", ".md", ".html", ".css", ".js"}:
                values.add(str(path.relative_to(root)))
    return tuple(sorted(values))
