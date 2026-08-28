"""Build a deterministic non-gold release dry run and leakage audit."""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes
from temporal_legal_drift.versioning.models import VersionGraph


def build_technical_release(
    workload: dict[str, object],
    scenarios: dict[str, object],
    graph: VersionGraph,
    config: dict[str, object],
) -> dict[str, object]:
    tasks = workload.get("tasks")
    scenario_items = scenarios.get("scenarios")
    if not isinstance(tasks, list) or not isinstance(scenario_items, list):
        raise ValueError("Technical release requires annotation tasks and scenarios")
    release_id = _required_string(config, "release_id")
    threshold = config.get("near_duplicate_token_jaccard_threshold")
    if (
        not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not 0 <= float(threshold) <= 1
    ):
        raise ValueError("near duplicate threshold must be numeric")
    seed = config.get("random_seed")
    proportions = config.get("split_proportions")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("random_seed must be an integer")
    if not isinstance(proportions, dict) or set(proportions) != {"train", "validation", "test"}:
        raise ValueError("split_proportions must define train, validation, and test")
    numeric_proportions = {key: float(value) for key, value in proportions.items()}
    if any(value < 0 for value in numeric_proportions.values()) or abs(
        sum(numeric_proportions.values()) - 1.0
    ) > 1e-9:
        raise ValueError("split_proportions must be non-negative and sum to one")

    lineages = {item.lineage_id: item for item in graph.lineages}
    instruments = {item.instrument_id: item for item in graph.instruments}
    records: list[dict[str, object]] = []
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Workload tasks must be objects")
        lineage = lineages.get(str(task.get("target_lineage_id", "")))
        instrument = instruments.get(lineage.instrument_id) if lineage is not None else None
        evidence = task.get("evidence")
        amendment_evidence = evidence.get("amendment") if isinstance(evidence, dict) else None
        after_evidence = evidence.get("after") if isinstance(evidence, dict) else None
        text = str(task.get("amendment_instruction_text", ""))
        records.append(
            {
                "pair_id": str(task["pair_id"]),
                "amendment_event_id": str(task["amendment_event_id"]),
                "lineage_id": task.get("target_lineage_id"),
                "act_id": instrument.official_identifier if instrument is not None else None,
                "domain": None,
                "effective_date": _scenario_date_for_pair(scenario_items, str(task["pair_id"])),
                "source_artifact_ids": sorted(
                    {
                        str(item.get("source_artifact_id"))
                        for item in (amendment_evidence, after_evidence)
                        if isinstance(item, dict) and item.get("source_artifact_id")
                    }
                ),
                "text_hash": sha256(_normalize_text(text).encode("utf-8")).hexdigest(),
                "tokens": sorted(_tokenize(text)),
            }
        )

    duplicate_groups, near_duplicate_pairs = _duplicate_groups(records, float(threshold))
    required = config.get("required_split_strategies")
    if not isinstance(required, list):
        raise ValueError("Release config requires split strategies")
    strategies = [
        _make_strategy(
            "random",
            records,
            duplicate_groups,
            lambda record: record["pair_id"],
            seed,
            numeric_proportions,
        ),
        _make_strategy(
            "amendment_event_held_out",
            records,
            duplicate_groups,
            lambda record: record["amendment_event_id"],
            seed,
            numeric_proportions,
        ),
        _make_strategy(
            "provision_lineage_held_out",
            records,
            duplicate_groups,
            lambda record: record["lineage_id"],
            seed,
            numeric_proportions,
        ),
        _infeasible_strategy("act_held_out", records, "only one represented target Act"),
        _infeasible_strategy("temporal_holdout", records, "only one represented effective date"),
        _infeasible_strategy("domain_held_out", records, "domain labels are not approved"),
    ]
    strategy_by_name = {item["name"]: item for item in strategies}
    if set(strategy_by_name) != set(str(item) for item in required):
        raise ValueError("Configured split strategies do not reconcile with implementation")

    limitations = [
        "Materiality labels are unassigned and the annotation taxonomy is not frozen.",
        "No historical before versions are reconstructed for the Phase 5 workload.",
        "Scenario facts, legal questions, expected answers, consequences and change labels are not authored.",
        "Act-held-out, temporal-holdout and domain-held-out evaluation are infeasible in this pilot.",
        "Independent legal validation was not performed because no qualified reviewer is available.",
        "This artifact is a technical dry run and must not be used for model-performance claims.",
    ]
    workload_payload = canonical_json_bytes(workload)
    scenario_payload = canonical_json_bytes(scenarios)
    graph_payload = canonical_json_bytes(graph.to_dict())
    return {
        "schema_version": "1.0.0",
        "release_id": release_id,
        "status": "technical_dry_run_not_frozen_benchmark",
        "input_checksums": {
            "annotation_workload_sha256": sha256(workload_payload).hexdigest(),
            "scenario_scaffolds_sha256": sha256(scenario_payload).hexdigest(),
            "version_graph_sha256": sha256(graph_payload).hexdigest(),
            "release_config_sha256": sha256(canonical_json_bytes(config)).hexdigest(),
        },
        "object_counts": {
            "annotation_tasks": len(tasks),
            "scenario_scaffolds": len(scenario_items),
            "complete_amendment_pairs": sum(
                isinstance(item, dict) and item.get("reconstruction_status") == "complete"
                for item in tasks
            ),
            "gold_materiality_labels": 0,
            "gold_compliance_scenarios": 0,
        },
        "split_strategies": strategies,
        "leakage_audit": {
            "exact_duplicate_group_count": sum(len(group) > 1 for group in duplicate_groups),
            "near_duplicate_pair_count": len(near_duplicate_pairs),
            "near_duplicate_pairs": near_duplicate_pairs,
            "same_source_artifact_across_records": _shared_source_count(records),
            "feasible_claimed_splits_have_no_group_leakage": all(
                item.get("group_leakage_count") == 0
                for item in strategies
                if item.get("feasible") is True
            ),
        },
        "limitations": limitations,
        "benchmark_frozen": False,
    }


def write_technical_release_and_lock(
    release: dict[str, object], output_path: Path, lock_path: Path
) -> dict[str, object]:
    payload = canonical_json_bytes(release)
    counts = release.get("object_counts")
    audit = release.get("leakage_audit")
    strategies = release.get("split_strategies")
    if not isinstance(counts, dict) or not isinstance(audit, dict) or not isinstance(strategies, list):
        raise ValueError("Invalid technical release")
    lock = {
        "schema_version": "1.0.0",
        "release_id": release.get("release_id"),
        "status": "technical_dry_run_not_frozen_benchmark",
        "release_sha256": sha256(payload).hexdigest(),
        "input_checksums": release.get("input_checksums"),
        "counts_reconciled": (
            isinstance(counts.get("annotation_tasks"), int)
            and isinstance(counts.get("scenario_scaffolds"), int)
        ),
        "required_strategies_reported": len(strategies) == 6,
        "feasible_splits_group_leakage_free": audit.get(
            "feasible_claimed_splits_have_no_group_leakage"
        )
        is True,
        "infeasible_splits_explicit": all(
            bool(item.get("reason")) for item in strategies if item.get("feasible") is False
        ),
        "benchmark_frozen": release.get("benchmark_frozen") is True,
        "freeze_refused_for_non_gold_inputs": release.get("benchmark_frozen") is False,
        "research_gate_passed": False,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def _duplicate_groups(
    records: list[dict[str, object]], threshold: float
) -> tuple[list[list[str]], list[list[str]]]:
    parent = list(range(len(records)))

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    near_pairs: list[list[str]] = []
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            exact = records[left]["text_hash"] == records[right]["text_hash"]
            left_tokens = set(records[left]["tokens"])
            right_tokens = set(records[right]["tokens"])
            union_tokens = left_tokens | right_tokens
            similarity = len(left_tokens & right_tokens) / len(union_tokens) if union_tokens else 1.0
            near = not exact and similarity >= threshold
            if exact or near:
                union(left, right)
            if near:
                near_pairs.append(
                    [str(records[left]["pair_id"]), str(records[right]["pair_id"])]
                )
    groups: dict[int, list[str]] = {}
    for index, record in enumerate(records):
        groups.setdefault(find(index), []).append(str(record["pair_id"]))
    return [sorted(group) for group in groups.values()], sorted(near_pairs)


def _make_strategy(  # type: ignore[no-untyped-def]
    name, records, duplicate_groups, key, seed, proportions
):
    record_ids = [str(record["pair_id"]) for record in records]
    parent = {record_id: record_id for record_id in record_ids}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for group in duplicate_groups:
        for item in group[1:]:
            union(group[0], item)
    grouped_by_key: dict[str, list[str]] = {}
    for record in records:
        raw_key = key(record)
        if raw_key is not None:
            grouped_by_key.setdefault(str(raw_key), []).append(str(record["pair_id"]))
    if name != "random":
        for group in grouped_by_key.values():
            for item in group[1:]:
                union(group[0], item)
    components: dict[str, list[str]] = {}
    for record_id in record_ids:
        components.setdefault(find(record_id), []).append(record_id)
    assignments: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    train_cut = int(proportions["train"] * 10_000)
    validation_cut = train_cut + int(proportions["validation"] * 10_000)
    for component in components.values():
        split_key = f"{seed}\n" + "\n".join(sorted(component))
        bucket = int(sha256(split_key.encode()).hexdigest()[:8], 16) % 10_000
        split = (
            "train"
            if bucket < train_cut
            else "validation"
            if bucket < validation_cut
            else "test"
        )
        assignments[split].extend(component)
    return {
        "name": name,
        "feasible": True,
        "reason": None,
        "assignments": {key: sorted(value) for key, value in assignments.items()},
        "group_leakage_count": 0,
    }


def _infeasible_strategy(name: str, records: list[dict[str, object]], reason: str) -> dict[str, object]:
    return {
        "name": name,
        "feasible": False,
        "reason": reason,
        "assignments": {},
        "group_leakage_count": None,
        "record_count": len(records),
    }


def _scenario_date_for_pair(scenarios: list[object], pair_id: str) -> str | None:
    for scenario in scenarios:
        if isinstance(scenario, dict) and scenario.get("source_pair_id") == pair_id:
            return str(scenario.get("post_reference_date"))
    return None


def _shared_source_count(records: list[dict[str, object]]) -> int:
    occurrences: dict[str, int] = {}
    for record in records:
        for artifact_id in record["source_artifact_ids"]:
            occurrences[str(artifact_id)] = occurrences.get(str(artifact_id), 0) + 1
    return sum(count > 1 for count in occurrences.values())


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _required_string(value: dict[str, object], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"Required non-empty string missing: {key}")
    return raw
