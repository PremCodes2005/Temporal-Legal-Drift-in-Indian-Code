"""Phase 8 baselines and feature preparation without unsupported evaluation."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes


CANONICAL_LABELS = ("High", "Medium", "Low", "None")
CUE_PATTERNS = {
    "duty": re.compile(r"\b(?:shall|must|required|duty|obligation)\b", re.IGNORECASE),
    "prohibition": re.compile(r"\b(?:shall not|prohibit|forbid|unlawful)\b", re.IGNORECASE),
    "right": re.compile(r"\b(?:right|entitled|may)\b", re.IGNORECASE),
    "threshold": re.compile(r"\b(?:threshold|amount|percent|rupees?)\b", re.IGNORECASE),
    "time": re.compile(r"\b(?:day|month|year|deadline|within|w\.e\.f\.)\b", re.IGNORECASE),
    "definition": re.compile(r"\b(?:means|includes|definition)\b", re.IGNORECASE),
    "exception": re.compile(r"\b(?:except|provided that|exemption)\b", re.IGNORECASE),
    "penalty": re.compile(r"\b(?:penalty|fine|imprisonment|liable)\b", re.IGNORECASE),
}


class MajorityBaseline:
    def __init__(self) -> None:
        self.label: str | None = None

    def fit(self, labels: list[str]) -> "MajorityBaseline":
        _validate_labels(labels)
        counts = Counter(labels)
        self.label = min(CANONICAL_LABELS, key=lambda label: (-counts[label], CANONICAL_LABELS.index(label)))
        return self

    def predict(self, count: int) -> list[str]:
        if self.label is None:
            raise ValueError("MajorityBaseline must be fitted")
        if count < 0:
            raise ValueError("Prediction count cannot be negative")
        return [self.label] * count


class ClassPriorBaseline:
    def __init__(self) -> None:
        self.probabilities: dict[str, float] | None = None

    def fit(self, labels: list[str]) -> "ClassPriorBaseline":
        _validate_labels(labels)
        counts = Counter(labels)
        self.probabilities = {
            label: counts[label] / len(labels) for label in CANONICAL_LABELS
        }
        return self

    def predict_proba(self, count: int) -> list[dict[str, float]]:
        if self.probabilities is None:
            raise ValueError("ClassPriorBaseline must be fitted")
        if count < 0:
            raise ValueError("Prediction count cannot be negative")
        return [dict(self.probabilities) for _ in range(count)]

    def predict(self, count: int) -> list[str]:
        probabilities = self.predict_proba(1)[0]
        label = min(
            CANONICAL_LABELS,
            key=lambda value: (-probabilities[value], CANONICAL_LABELS.index(value)),
        )
        return [label] * count


class OperationPriorBaseline:
    def __init__(self) -> None:
        self.global_label: str | None = None
        self.operation_labels: dict[str, str] = {}

    def fit(self, operations: list[str], labels: list[str]) -> "OperationPriorBaseline":
        if len(operations) != len(labels) or not labels:
            raise ValueError("Operations and labels must have equal non-zero length")
        _validate_labels(labels)
        self.global_label = MajorityBaseline().fit(labels).label
        grouped: dict[str, list[str]] = defaultdict(list)
        for operation, label in zip(operations, labels):
            grouped[operation].append(label)
        self.operation_labels = {
            operation: MajorityBaseline().fit(values).label or "None"
            for operation, values in grouped.items()
        }
        return self

    def predict(self, operations: list[str]) -> list[str]:
        if self.global_label is None:
            raise ValueError("OperationPriorBaseline must be fitted")
        return [self.operation_labels.get(operation, self.global_label) for operation in operations]


def build_baseline_dry_run(
    workload: dict[str, object], release: dict[str, object], config: dict[str, object]
) -> dict[str, object]:
    tasks = workload.get("tasks")
    baselines = config.get("baselines")
    labels = config.get("canonical_labels")
    if not isinstance(tasks, list) or not isinstance(baselines, list):
        raise ValueError("Baseline preparation requires tasks and baseline registry")
    if labels != list(CANONICAL_LABELS):
        raise ValueError("Baseline labels must match the canonical materiality order")
    if release.get("benchmark_frozen") is not False:
        raise ValueError("Dry-run preparation expects the explicitly non-frozen release")

    rows: list[dict[str, object]] = []
    gold_count = 0
    complete_pair_count = 0
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Annotation tasks must be objects")
        before = task.get("before_text")
        after = task.get("after_text")
        instruction = str(task.get("amendment_instruction_text", ""))
        materiality = task.get("materiality")
        label = materiality.get("label") if isinstance(materiality, dict) else None
        gold_count += label in CANONICAL_LABELS
        complete = isinstance(before, str) and isinstance(after, str)
        complete_pair_count += complete
        rows.append(
            {
                "pair_id": task.get("pair_id"),
                "operation": task.get("operation"),
                "has_complete_before_after": complete,
                "before_character_count": len(before) if isinstance(before, str) else None,
                "after_character_count": len(after) if isinstance(after, str) else None,
                "normalized_edit_ratio": _edit_ratio(before, after) if complete else None,
                "instruction_character_count": len(instruction),
                "cue_counts": {
                    name: len(pattern.findall(instruction)) for name, pattern in CUE_PATTERNS.items()
                },
                "gold_label": label,
            }
        )
    status = (
        "ready_for_baseline_evaluation"
        if gold_count == len(rows) and complete_pair_count == len(rows)
        else "features_prepared_evaluation_blocked_no_gold"
    )
    if status != "features_prepared_evaluation_blocked_no_gold":
        raise ValueError("This command is the non-gold dry-run path only")
    return {
        "schema_version": "1.0.0",
        "experiment_id": config.get("experiment_id"),
        "status": status,
        "input_fingerprints": {
            "annotation_workload_sha256": sha256(canonical_json_bytes(workload)).hexdigest(),
            "release_sha256": sha256(canonical_json_bytes(release)).hexdigest(),
            "baseline_config_sha256": sha256(canonical_json_bytes(config)).hexdigest(),
        },
        "baseline_registry": baselines,
        "feature_rows": rows,
        "metrics": None,
        "limitations": [
            "No materiality gold labels are present.",
            "No complete historical before/after pairs are present.",
            "No baseline was trained, tuned, or evaluated on the technical preview.",
            "No prior-paper reproduction or model-performance claim is made.",
        ],
    }


def write_baseline_dry_run_and_lock(
    document: dict[str, object], output_path: Path, lock_path: Path
) -> dict[str, object]:
    payload = canonical_json_bytes(document)
    rows = document.get("feature_rows")
    registry = document.get("baseline_registry")
    if not isinstance(rows, list) or not isinstance(registry, list):
        raise ValueError("Baseline dry run requires features and registry")
    lock = {
        "schema_version": "1.0.0",
        "status": document.get("status"),
        "run_sha256": sha256(payload).hexdigest(),
        "input_fingerprints": document.get("input_fingerprints"),
        "feature_row_count": len(rows),
        "registered_baseline_count": len(registry),
        "non_neural_feature_families_present": all(
            family in {item.get("family") for item in registry if isinstance(item, dict)}
            for family in (
                "majority",
                "class_prior",
                "lexical_features",
                "amendment_operation",
                "rule_legal_cues",
            )
        ),
        "metrics_reported": document.get("metrics") is not None,
        "unsupported_performance_claims_absent": document.get("metrics") is None,
        "research_gate_passed": False,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _validate_labels(labels: list[str]) -> None:
    if not labels or any(label not in CANONICAL_LABELS for label in labels):
        raise ValueError("Labels must be non-empty canonical materiality labels")


def _edit_ratio(before: object, after: object) -> float:
    before_tokens = str(before).split()
    after_tokens = str(after).split()
    denominator = max(len(before_tokens), len(after_tokens), 1)
    previous = list(range(len(after_tokens) + 1))
    for left_index, left_token in enumerate(before_tokens, start=1):
        current = [left_index]
        for right_index, right_token in enumerate(after_tokens, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + int(left_token != right_token),
                )
            )
        previous = current
    return previous[-1] / denominator
