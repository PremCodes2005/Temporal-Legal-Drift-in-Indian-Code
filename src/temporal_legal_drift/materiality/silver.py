"""Transparent, deterministic silver labeling for materiality triage.

These rules produce machine-generated hypotheses, not legal gold labels. They
must not be used as ground truth for claiming legal accuracy.
"""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
from typing import Any

from temporal_legal_drift.jsonio import atomic_replace, canonical_json_bytes, load_json

from .annotation import LABELS


_TOKENS = re.compile(r"[a-z]+|\d+(?:\.\d+)?", re.I)
_CUES = {
    "obligation": re.compile(r"\b(?:shall|must|required|duty|obligation)\b", re.I),
    "right": re.compile(r"\b(?:right|entitled|may be entitled)\b", re.I),
    "prohibition": re.compile(r"\b(?:shall not|must not|prohibit(?:ed)?|forbidden|unlawful)\b", re.I),
    "scope": re.compile(r"\b(?:means|includes|every|any person|company|class of|applies to)\b", re.I),
    "definition": re.compile(r"\b(?:means|includes|defined as)\b", re.I),
    "threshold": re.compile(r"\b(?:rupees?|rs\.?|₹|amount|threshold|percent|percentage)\b", re.I),
    "time": re.compile(r"\b(?:day|days|month|months|year|years|within|period|deadline|time limit)\b", re.I),
    "liability": re.compile(r"\b(?:liable|liability|responsible)\b", re.I),
    "procedure": re.compile(r"\b(?:file|filing|submit|submission|report|notice|register|application|form)\b", re.I),
    "exemption": re.compile(r"\b(?:except|exempt(?:ion)?|provided that|notwithstanding)\b", re.I),
}
_SEVERE = frozenset({"obligation", "right", "prohibition", "scope", "liability", "exemption"})
_PROCEDURAL = frozenset({"threshold", "time", "procedure"})
_LABEL_RANK = {"None": 0, "Low": 1, "Medium": 2, "High": 3}


def build_materiality_silver(round_document: dict[str, Any]) -> dict[str, Any]:
    """Apply two distinct rule systems, report their agreement, and abstain on large conflicts."""
    tasks = round_document.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 50:
        raise ValueError("Automated silver-labeling requires the 50-case materiality round")
    labels_a: list[str] = []
    labels_b: list[str] = []
    outputs: list[dict[str, Any]] = []
    for task in tasks:
        _assert_evidence_anchors(task)
        a = _cue_transition_annotator(task)
        b = _operation_delta_annotator(task)
        labels_a.append(a["label"])
        labels_b.append(b["label"])
        disagreement = abs(_LABEL_RANK[a["label"]] - _LABEL_RANK[b["label"]])
        adjudicated = None if disagreement > 1 else max(
            (a["label"], b["label"]), key=lambda label: _LABEL_RANK[label]
        )
        disposition = "ABSTAINED_MATERIAL_DISAGREEMENT" if adjudicated is None else "PROVISIONAL_MACHINE_CONSENSUS"
        dimensions = sorted(set(a["dimensions"]) | set(b["dimensions"]))
        outputs.append({
            "pair_id": task["pair_id"],
            "transition_id": task["transition_id"],
            "operation": task["operation"],
            "source_evidence_ids": sorted({str(item["source_id"]) for item in task["source_evidence"]}),
            "before_version_id": task["before_version_id"],
            "after_version_id": task["after_version_id"],
            "annotator_a": a,
            "annotator_b": b,
            "automated_adjudication": {
                "label": adjudicated,
                "dimensions": dimensions,
                "status": disposition,
                "rule": "choose_higher_adjacent_label; abstain when ordinal disagreement exceeds one",
                "rationale": (
                    "Both labelers agreed or differed by one ordered category; the higher-impact label is kept as a conservative triage candidate."
                    if adjudicated is not None else
                    "Independent rule systems differed by more than one category; no automated label is assigned."
                ),
            },
            "silver_status": "PROVISIONAL_SILVER" if adjudicated is not None else "UNRESOLVED_MACHINE_DISAGREEMENT",
            "gold_status": "NOT_GOLD",
        })
    observed = sum(left == right for left, right in zip(labels_a, labels_b)) / len(tasks)
    kappa, expected = _cohens_kappa(labels_a, labels_b)
    resolved = [item for item in outputs if item["automated_adjudication"]["label"] is not None]
    all_dimensions = Counter(dimension for item in resolved for dimension in item["automated_adjudication"]["dimensions"])
    return {
        "schema_version": "1.0.0",
        "dataset_id": "materiality-silver-v1",
        "status": "automated_silver_labels_not_gold",
        "source_round_id": round_document.get("round_id"),
        "source_round_sha256": sha256(canonical_json_bytes(round_document)).hexdigest(),
        "guideline_version": round_document.get("guideline_version"),
        "label_order": list(LABELS),
        "labeling_method": "two deterministic, separately specified rule labelers plus conservative rule adjudicator",
        "annotator_independence": "distinct rule logic with a shared cue lexicon; not independent humans or statistically independent evidence",
        "agreement": {
            "item_count": len(tasks),
            "raw_agreement": observed,
            "cohens_kappa_between_automated_methods": kappa,
            "expected_agreement": expected,
            "confusion_matrix_method_a_rows_method_b_columns": _confusion(labels_a, labels_b),
            "classification_metrics_method_a_against_method_b": _method_agreement_metrics(labels_a, labels_b),
            "disagreement_pair_ids": [
                task["pair_id"] for task, left, right in zip(tasks, labels_a, labels_b) if left != right
            ],
            "method_a_distribution": dict(sorted(Counter(labels_a).items())),
            "method_b_distribution": dict(sorted(Counter(labels_b).items())),
            "not_human_inter_annotator_agreement": True,
        },
        "case_count": len(outputs),
        "provisional_label_count": len(resolved),
        "unresolved_disagreement_count": len(outputs) - len(resolved),
        "provisional_class_distribution": dict(sorted(Counter(item["automated_adjudication"]["label"] for item in resolved).items())),
        "provisional_dimension_distribution": dict(sorted(all_dimensions.items())),
        "rows": outputs,
        "legal_validation_status": "not_performed",
        "legal_correctness_claimed": False,
        "is_gold": False,
        "limitations": [
            "The labels are rule-generated silver hypotheses and may reflect rule bias.",
            "The two rule systems share a legal-cue lexicon and corpus cases, so their agreement is not evidence from independent sources.",
            "Source evidence proves text provenance, not legal interpretation or materiality.",
            "The conservative tie-break is not an independent legal adjudicator.",
            "Agreement and kappa measure only agreement between these two implemented rule systems.",
            "Do not train/evaluate a classifier against these labels and report the result as legal accuracy.",
        ],
    }


def write_materiality_silver(
    document: dict[str, Any], output_path: Any, lock_path: Any, report_path: Any | None = None
) -> dict[str, Any]:
    payload = canonical_json_bytes(document)
    output_path = Path(output_path)
    lock_path = Path(lock_path)
    if output_path.exists() and sha256(output_path.read_bytes()).digest() != sha256(payload).digest():
        raise ValueError("Refusing to overwrite an existing silver dataset; write a new dataset version instead")
    frozen_lock_path = lock_path.with_name("materiality_silver_frozen.lock.json")
    if frozen_lock_path.exists():
        frozen = load_json(frozen_lock_path)
        if sha256(payload).hexdigest() != frozen.get("source_file_sha256"):
            raise ValueError("Frozen silver dataset is immutable; create a new version rather than replacing it")
    lock = {
        "schema_version": "1.0.0",
        "status": document.get("status"),
        "dataset_sha256": sha256(payload).hexdigest(),
        "case_count": document.get("case_count"),
        "provisional_label_count": document.get("provisional_label_count"),
        "unresolved_disagreement_count": document.get("unresolved_disagreement_count"),
        "agreement_is_human_annotation": False,
        "legal_correctness_claimed": False,
        "is_gold": False,
        "research_gate_passed": False,
    }
    atomic_replace(output_path, payload)
    atomic_replace(lock_path, canonical_json_bytes(lock))
    if report_path is not None:
        atomic_replace(report_path, render_materiality_silver_report(document).encode("utf-8"))
    return lock


def freeze_materiality_silver(
    dataset_path: Path, lock_path: Path, project_root: Path | None = None
) -> dict[str, Any]:
    """Create a write-once checksum lock over the existing silver dataset."""
    if not dataset_path.is_file():
        raise ValueError(f"Silver dataset is missing: {dataset_path}")
    document = load_json(dataset_path)
    rows = document.get("rows")
    if document.get("status") != "automated_silver_labels_not_gold" or not isinstance(rows, list):
        raise ValueError("Only the existing explicitly non-gold silver artifact can be frozen here")
    if len(rows) != 50 or len({str(row.get("pair_id")) for row in rows}) != 50:
        raise ValueError("The silver dataset freeze requires 50 unique records")
    if any(
        not row.get("annotator_a", {}).get("method_id")
        or not row.get("annotator_b", {}).get("method_id")
        or not row.get("source_evidence_ids")
        or row.get("gold_status") != "NOT_GOLD"
        for row in rows
    ):
        raise ValueError("Silver freeze requires all existing predictions and provenance to be present")
    digest = sha256(dataset_path.read_bytes()).hexdigest()
    dataset_reference = (
        dataset_path.resolve().relative_to(project_root.resolve()).as_posix()
        if project_root is not None else dataset_path.name
    )
    lock = {
        "schema_version": "1.0.0",
        "freeze_id": "materiality-silver-v1-frozen",
        "dataset_id": document.get("dataset_id"),
        "dataset_path": dataset_reference,
        "source_file_sha256": digest,
        "source_round_sha256": document.get("source_round_sha256"),
        "case_count": len(rows),
        "preserves_rule_system_predictions": True,
        "preserves_source_evidence_links": True,
        "preserves_provisional_tie_breaks": True,
        "legal_correctness_claimed": False,
        "is_gold": False,
        "immutable": True,
    }
    lock_path = Path(lock_path)
    if lock_path.exists():
        existing = load_json(lock_path)
        if any(existing.get(key) != value for key, value in lock.items() if key != "dataset_path"):
            raise ValueError("A different materiality silver dataset is already frozen; do not overwrite it")
        if existing != lock:
            atomic_replace(lock_path, canonical_json_bytes(lock))
    else:
        atomic_replace(lock_path, canonical_json_bytes(lock))
    return lock


def search_potential_none_cases(graph: dict[str, Any]) -> dict[str, Any]:
    """Search only real graph transitions; text equality is a candidate, never a None gold label."""
    versions = {str(item["version_id"]): item for item in graph.get("provision_versions", [])}
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for transition in graph.get("transitions", []):
        before = versions.get(str(transition.get("before_version_id")))
        after = versions.get(str(transition.get("after_version_id")))
        if before is None or after is None:
            continue
        before_text, after_text = str(before.get("text") or ""), str(after.get("text") or "")
        if not before_text.strip() or not after_text.strip() or _normalized(before_text) != _normalized(after_text):
            continue
        transition_id = str(transition.get("transition_id"))
        if transition_id in seen:
            continue
        seen.add(transition_id)
        source_ids = set(map(str, before.get("source_ids", []))) | set(map(str, after.get("source_ids", [])))
        corroborated = (
            transition.get("validation_status") == "MACHINE_CROSS_SOURCE_CORROBORATED"
            and transition.get("validation_checks", {}).get("after_fragment_matches_consolidated_principal_act") is True
            and len(source_ids) >= 2
        )
        results.append({
            "transition_id": transition_id,
            "pair_id": None,
            "operation": transition.get("operation"),
            "before_version_id": before.get("version_id"),
            "after_version_id": after.get("version_id"),
            "normalized_text_equal": True,
            "source_ids": sorted(source_ids),
            "machine_cross_source_corroborated": corroborated,
            "candidate_status": "POTENTIAL_NONE_REVIEW_CANDIDATE" if corroborated else "REJECTED_INSUFFICIENT_INDEPENDENT_PROVENANCE",
            "reason": (
                "Text is normalized-identical and has multiple corroborating source documents; legal review is still needed to establish no legal effect."
                if corroborated else
                "Normalized-identical text is not enough: this record lacks independent cross-source corroboration or a successful reconstruction check."
            ),
            "label": None,
            "gold_status": "NOT_GOLD",
        })
    accepted = [item for item in results if item["candidate_status"] == "POTENTIAL_NONE_REVIEW_CANDIDATE"]
    return {
        "schema_version": "1.0.0",
        "status": "potential_none_candidates_found_pending_review" if accepted else "none_category_unevaluated",
        "graph_id": graph.get("graph_id"),
        "graph_sha256": sha256(canonical_json_bytes(graph)).hexdigest(),
        "transition_count_scanned": len(graph.get("transitions", [])),
        "normalized_text_match_count": len(results),
        "reviewable_candidate_count": len(accepted),
        "rejected_candidate_count": len(results) - len(accepted),
        "none_gold_labels_created": 0,
        "results": results,
        "legal_correctness_claimed": False,
        "interpretation": "Textual equality is a search heuristic only. None requires supported absence of legal/compliance effect and remains unassigned without independent validation.",
    }


def render_materiality_silver_report(document: dict[str, Any]) -> str:
    agreement = document["agreement"]
    matrix = agreement["confusion_matrix_method_a_rows_method_b_columns"]
    metrics = agreement["classification_metrics_method_a_against_method_b"]
    rows = [
        "# Automated Materiality Labeler Agreement — Silver Diagnostics",
        "",
        "> This is agreement between two deterministic rule systems, not human inter-annotator agreement, legal validation, or classifier accuracy.",
        "",
        f"- Cases processed: {document['case_count']}",
        f"- Provisional higher-label outputs: {document['provisional_label_count']}",
        f"- Unresolved large disagreements: {document['unresolved_disagreement_count']}",
        f"- Exact rule-system agreement: {agreement['raw_agreement']:.1%}",
        f"- Cohen's kappa between algorithms: {agreement['cohens_kappa_between_automated_methods']:.3f}",
        f"- Proxy method-comparison accuracy (method A reference): {metrics['accuracy']:.1%}",
        f"- Proxy method-comparison macro F1: {metrics['macro_f1']:.3f}",
        "",
        "## Provisional label distribution",
        "",
        "| Label | Cases |",
        "| --- | ---: |",
    ]
    rows.extend(f"| {label} | {count} |" for label, count in document["provisional_class_distribution"].items())
    rows.extend([
        "",
        "## Confusion matrix",
        "",
        "Rows are cue-transition rules; columns are operation-delta rules.",
        "",
        "| Cue rules \\ Operation-delta | High | Medium | Low | None |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for label in LABELS:
        rows.append("| " + label + " | " + " | ".join(str(matrix[label][other]) for other in LABELS) + " |")
    rows.extend([
        "",
        "## Reading this result",
        "",
        "The disagreement is substantial (38% of cases). The rules share a cue lexicon and source cases, so they are not statistically independent labelers. They tend to differ on whether an operative but weakly cued fragment is Low or Medium. The conservative tie-break stores provisional labels, but does not resolve legal ambiguity. `None` has no cases in this amendment-positive sample, so that category has no observed coverage. The displayed precision/recall/F1 treat one automated rule as a proxy reference and must not be cited as real-corpus materiality-classifier performance.",
        "",
        "Source citations establish the origin of the quoted wording only. They do not prove that an automatically inferred legal effect is correct. Each record remains `NOT_GOLD`; taxonomy approval, independent legal review, and an independently validated benchmark are still outstanding.",
        "",
    ])
    return "\n".join(rows)


def _cue_transition_annotator(task: dict[str, Any]) -> dict[str, Any]:
    """Labeler A: compare legal-effect cue presence and numeric/time signals."""
    before, after = str(task.get("before_text") or ""), str(task.get("after_text") or "")
    before_hits, after_hits = _cue_hits(before), _cue_hits(after)
    changed = {name for name in _CUES if before_hits[name] != after_hits[name]}
    dimensions = sorted(changed)
    if _normalized(before) == _normalized(after):
        label, reason = "None", "Normalized before/after wording is identical."
    elif changed & _SEVERE:
        label, reason = "High", "The wording changes the presence of one or more high-impact legal-effect cues: " + ", ".join(sorted(changed & _SEVERE)) + "."
    elif changed & _PROCEDURAL:
        label, reason = "Medium", "The wording changes an operative time, threshold, or procedure cue: " + ", ".join(sorted(changed & _PROCEDURAL)) + "."
    elif _numeric_tokens(before) != _numeric_tokens(after):
        label, reason = "Medium", "Numeric tokens changed; rule-based labeling cannot determine their legal importance."
        dimensions = sorted(set(dimensions) | _numeric_dimensions(before, after))
    else:
        label, reason = "Low", "Text changed without a detected high-impact or procedural cue transition."
    return _automated_rater("rule-cue-transition-v1", label, dimensions, reason)


def _operation_delta_annotator(task: dict[str, Any]) -> dict[str, Any]:
    """Labeler B: combine edit magnitude, operation class, and focused text cues."""
    before, after = str(task.get("before_text") or ""), str(task.get("after_text") or "")
    op = str(task.get("operation", "UNKNOWN")).upper()
    similarity = SequenceMatcher(None, _TOKENS.findall(before.casefold()), _TOKENS.findall(after.casefold()), autojunk=False).ratio()
    before_hits, after_hits = _cue_hits(before), _cue_hits(after)
    changed = {name for name in _CUES if before_hits[name] != after_hits[name]}
    present = {name for name in _CUES if before_hits[name] or after_hits[name]}
    if _normalized(before) == _normalized(after):
        label, reason = "None", "Normalized text is identical and the operation yielded no wording delta."
    elif changed & _SEVERE:
        label, reason = "High", "The operation changes a detected duty, right, prohibition, scope, liability, or exception cue: " + ", ".join(sorted(changed & _SEVERE)) + "."
    elif changed & _PROCEDURAL or _numeric_tokens(before) != _numeric_tokens(after):
        label, reason = "Medium", "The operation changes a detected time, threshold, procedure, or numeric value."
    elif op in {"INSERT", "OMIT", "REPEAL"} and present & _SEVERE:
        label, reason = "High", "An insertion/removal operation affects text with a high-impact legal-effect cue."
    elif op in {"INSERT", "OMIT", "REPEAL"} and present:
        label, reason = "Medium", "An insertion/removal changes operative statutory wording; its full legal effect is not inferred."
    elif similarity < 0.65:
        label, reason = "Medium", "The operation changes a large fraction of the controlled fragment without a detected severe cue transition."
    else:
        label, reason = "Low", "A limited lexical delta is detected without an explicit legal-effect or procedural cue change."
    dimensions = sorted(changed if changed else present)
    if _numeric_tokens(before) != _numeric_tokens(after):
        dimensions = sorted(set(dimensions) | _numeric_dimensions(before, after))
    return _automated_rater("operation-delta-v1", label, dimensions, reason, similarity=round(similarity, 4))


def _automated_rater(method: str, label: str, dimensions: list[str], rationale: str, **extra: Any) -> dict[str, Any]:
    return {"method_id": method, "label": label, "dimensions": dimensions, "rationale": rationale,
            "confidence": None, "confidence_status": "not_calibrated", **extra}


def _cue_hits(text: str) -> dict[str, bool]:
    return {name: bool(pattern.search(text)) for name, pattern in _CUES.items()}


def _normalized(text: str) -> str:
    return " ".join(_TOKENS.findall(text.casefold()))


def _numeric_tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\d+(?:\.\d+)?", text))


def _numeric_dimensions(before: str, after: str) -> set[str]:
    combined = f"{before}\n{after}"
    dimensions: set[str] = set()
    if _CUES["time"].search(combined):
        dimensions.add("time")
    if _CUES["threshold"].search(combined):
        dimensions.add("threshold")
    return dimensions or {"threshold"}


def _confusion(left: list[str], right: list[str]) -> dict[str, dict[str, int]]:
    return {a: {b: sum(x == a and y == b for x, y in zip(left, right)) for b in LABELS} for a in LABELS}


def _cohens_kappa(left: list[str], right: list[str]) -> tuple[float | None, float]:
    n = len(left)
    matrix = _confusion(left, right)
    observed = sum(matrix[label][label] for label in LABELS) / n
    left_counts = Counter(left)
    right_counts = Counter(right)
    expected = sum(left_counts[label] * right_counts[label] for label in LABELS) / (n * n)
    return (None if expected == 1 else (observed - expected) / (1 - expected)), expected


def _method_agreement_metrics(reference: list[str], candidate: list[str]) -> dict[str, Any]:
    """Precision/recall/F1 with one ruleset as a proxy reference, never legal gold."""
    matrix = _confusion(reference, candidate)
    per_class: dict[str, dict[str, float | int | None]] = {}
    f1_values: list[float] = []
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in LABELS if other != label)
        fn = sum(matrix[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else None
        if f1 is not None:
            f1_values.append(f1)
        per_class[label] = {"support": sum(value == label for value in reference), "precision": precision, "recall": recall, "f1": f1}
    return {
        "reference_method": "legal-cue-transition-rules-v1",
        "compared_method": "operation-delta-rules-v1",
        "accuracy": sum(left == right for left, right in zip(reference, candidate)) / len(reference),
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else None,
        "per_class": per_class,
        "confusion_matrix": matrix,
        "interpretation": "Inter-method agreement only; method A is not human-verified ground truth.",
    }


def _assert_evidence_anchors(task: dict[str, Any]) -> None:
    sources = task.get("source_evidence")
    if not isinstance(sources, list) or len({str(item.get("source_id")) for item in sources}) < 2:
        raise ValueError(f"Silver labeling requires two source anchors for {task.get('pair_id')}")
    for source in sources:
        quote = str(source.get("evidence_text") or "").strip()
        if not quote or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
            raise ValueError(f"Silver labeling requires quote and SHA-256 provenance for {task.get('pair_id')}")
