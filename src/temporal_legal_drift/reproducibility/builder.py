"""Build a traceable Phase 11 engineering reproducibility record."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes


REQUIRED_ARTIFACTS = (
    "configs/research_contract.v1.json",
    "configs/corpus/pilot_v1.json",
    "reports/corpus/india-code-temporal-pilot-v1.lock.json",
    "reports/phase3/version_graph.lock.json",
    "reports/phase4/cross_version_validation.lock.json",
    "reports/phase5/annotation_workload.lock.json",
    "reports/phase6/scenario_scaffolds.lock.json",
    "reports/phase7/release.lock.json",
    "reports/phase8/baseline_dry_run.lock.json",
    "reports/phase9/evaluation_plan.lock.json",
    "reports/phase10/explanation_plan.lock.json",
)


def verify_fresh_environment(root: Path, *, timeout_seconds: int = 900) -> dict[str, object]:
    reproducibility_paths = _reproducibility_paths(root)
    missing = [relative for relative in reproducibility_paths if not (root / relative).is_file()]
    if missing:
        raise ValueError(f"Required reproducibility artifacts are missing: {missing}")
    checksums = {
        relative: sha256((root / relative).read_bytes()).hexdigest()
        for relative in reproducibility_paths
    }
    with TemporaryDirectory(prefix="tldrift-phase11-") as temporary_directory:
        environment = Path(temporary_directory) / "venv"
        commands = [
            [sys.executable, "-m", "venv", "--system-site-packages", str(environment)],
            [
                str(environment / "bin" / "python"),
                "-m",
                "temporal_legal_drift.cli",
                "--project-root",
                str(root),
                "check-gates",
                "--through-phase",
                "10",
            ],
            [
                str(environment / "bin" / "python"),
                "-m",
                "unittest",
                "tests.unit.test_acquisition",
                "tests.unit.test_applicability",
                "tests.unit.test_corpus",
                "tests.unit.test_cross_validation",
                "tests.unit.test_parsers",
                "tests.unit.test_phase0",
                "tests.unit.test_phases_5_7",
                "tests.unit.test_phases_8_10",
                "tests.unit.test_versioning",
                "tests.integration.test_normalization_pipeline",
                "-v",
            ],
        ]
        executions: list[dict[str, object]] = []
        for index, command in enumerate(commands):
            command_environment = {
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(root / "src"),
            }
            completed = subprocess.run(
                command,
                cwd=root,
                env=command_environment,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            executions.append(
                {
                    "step": index + 1,
                    "command": _portable_command(command, root, environment),
                    "exit_code": completed.returncode,
                    "stdout_sha256": sha256(completed.stdout.encode("utf-8")).hexdigest(),
                    "stderr_sha256": sha256(completed.stderr.encode("utf-8")).hexdigest(),
                    "output_tail": (completed.stdout + completed.stderr)[-2000:],
                }
            )
            if completed.returncode != 0:
                raise ValueError(
                    f"Fresh-environment verification failed at step {index + 1}: "
                    f"{(completed.stdout + completed.stderr)[-2000:]}"
                )
    return {
        "schema_version": "1.0.0",
        "release_id": "phase11-reproducibility-engineering-v0.1.0",
        "status": "fresh_environment_engineering_reproduction_passed_expert_review_unavailable",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "fresh_virtual_environment": True,
            "package_execution": "isolated_interpreter_with_explicit_project_src_path",
            "network_required": False,
        },
        "artifact_checksums": checksums,
        "executions": executions,
        "fresh_environment_reproduction_passed": True,
        "independent_expert_validation": {
            "status": "not_performed_reviewer_unavailable",
            "legal_correctness_claimed": False,
        },
        "research_gate_passed": False,
        "limitations": [
            "Engineering reproduction does not replace independent legal-expert validation.",
            "Phase 9 is an executed non-gold smoke run and has no performance metrics.",
            "The benchmark remains unfrozen because materiality and scenario gold are unavailable.",
        ],
    }


def write_reproducibility_manifest_and_lock(
    document: dict[str, object], output_path: Path, lock_path: Path
) -> dict[str, object]:
    payload = canonical_json_bytes(document)
    executions = document.get("executions")
    if not isinstance(executions, list):
        raise ValueError("Reproducibility manifest requires executions")
    lock = {
        "schema_version": "1.0.0",
        "release_id": document.get("release_id"),
        "manifest_sha256": sha256(payload).hexdigest(),
        "artifact_count": len(document.get("artifact_checksums", {})),
        "execution_step_count": len(executions),
        "all_execution_steps_passed": bool(executions)
        and all(isinstance(item, dict) and item.get("exit_code") == 0 for item in executions),
        "fresh_environment_reproduction_passed": document.get(
            "fresh_environment_reproduction_passed"
        )
        is True,
        "independent_expert_validation_status": document.get(
            "independent_expert_validation", {}
        ).get("status"),
        "legal_correctness_claimed": document.get("independent_expert_validation", {}).get(
            "legal_correctness_claimed"
        ),
        "engineering_gate_passed": True,
        "research_gate_passed": False,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _portable_command(command: list[str], root: Path, environment: Path) -> list[str]:
    return [
        value.replace(str(environment), "<fresh-venv>").replace(str(root), "<project-root>")
        for value in command
    ]


def _reproducibility_paths(root: Path) -> tuple[str, ...]:
    values = set(REQUIRED_ARTIFACTS)
    values.add("pyproject.toml")
    for directory in ("configs", "schemas", "src", "tests", "protocols"):
        for path in (root / directory).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".md"}:
                values.add(str(path.relative_to(root)))
    return tuple(sorted(values))
