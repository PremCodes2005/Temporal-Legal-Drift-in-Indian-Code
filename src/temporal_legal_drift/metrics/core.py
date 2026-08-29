"""Deterministic metrics with explicit denominators and undefined values."""

from __future__ import annotations

from collections import Counter
from typing import Iterable


def classification_metrics(
    gold: Iterable[str], predictions: Iterable[str], labels: tuple[str, ...]
) -> dict[str, object]:
    gold_values = tuple(gold)
    prediction_values = tuple(predictions)
    if len(gold_values) != len(prediction_values):
        raise ValueError("Gold and prediction lengths differ")
    if not gold_values:
        raise ValueError("Classification metrics require at least one item")
    allowed = set(labels)
    if any(value not in allowed for value in gold_values + prediction_values):
        raise ValueError("Classification values must use canonical labels")

    confusion = {
        gold_label: {
            predicted_label: sum(
                actual == gold_label and predicted == predicted_label
                for actual, predicted in zip(gold_values, prediction_values)
            )
            for predicted_label in labels
        }
        for gold_label in labels
    }
    per_class: dict[str, dict[str, float | int | None]] = {}
    f1_values: list[float] = []
    for label in labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[other][label] for other in labels if other != label)
        false_negative = sum(confusion[label][other] for other in labels if other != label)
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        f1 = (
            None
            if precision is None or recall is None or precision + recall == 0
            else 2 * precision * recall / (precision + recall)
        )
        if f1 is not None:
            f1_values.append(f1)
        per_class[label] = {
            "support": sum(value == label for value in gold_values),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    high_total = sum(value == "High" for value in gold_values)
    high_false_negatives = sum(
        actual == "High" and predicted != "High"
        for actual, predicted in zip(gold_values, prediction_values)
    )
    return {
        "item_count": len(gold_values),
        "accuracy": sum(a == b for a, b in zip(gold_values, prediction_values))
        / len(gold_values),
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else None,
        "per_class": per_class,
        "confusion_matrix": confusion,
        "high_materiality_false_negative_count": high_false_negatives,
        "high_materiality_denominator": high_total,
        "high_materiality_false_negative_rate": _ratio(high_false_negatives, high_total),
        "gold_distribution": dict(sorted(Counter(gold_values).items())),
    }


def temporal_drift_metrics(records: Iterable[dict[str, object]]) -> dict[str, object]:
    values = tuple(records)
    if not values:
        raise ValueError("Temporal drift metrics require at least one paired record")
    for record in values:
        if record.get("expected_change") not in {0, 1} or record.get("model_change") not in {
            0,
            1,
        }:
            raise ValueError("expected_change and model_change must be binary")
    expected_change = sum(record["expected_change"] == 1 for record in values)
    expected_stability = sum(record["expected_change"] == 0 for record in values)
    false_stability = sum(
        record["expected_change"] == 1 and record["model_change"] == 0
        for record in values
    )
    false_instability = sum(
        record["expected_change"] == 0 and record["model_change"] == 1
        for record in values
    )
    correct = sum(record["expected_change"] == record["model_change"] for record in values)
    return {
        "paired_item_count": len(values),
        "false_stability_count": false_stability,
        "false_stability_denominator": expected_change,
        "false_stability_rate": _ratio(false_stability, expected_change),
        "false_instability_count": false_instability,
        "false_instability_denominator": expected_stability,
        "false_instability_rate": _ratio(false_instability, expected_stability),
        "change_decision_accuracy": correct / len(values),
    }


def multiclass_brier_score(
    gold: Iterable[str], probabilities: Iterable[dict[str, float]], labels: tuple[str, ...]
) -> dict[str, object]:
    gold_values = tuple(gold)
    probability_values = tuple(probabilities)
    if not gold_values or len(gold_values) != len(probability_values):
        raise ValueError("Brier score requires equal non-empty gold and probability rows")
    scores: list[float] = []
    for actual, row in zip(gold_values, probability_values):
        if actual not in labels or set(row) != set(labels):
            raise ValueError("Brier inputs must use exactly the canonical labels")
        if any(not isinstance(value, (int, float)) or value < 0 for value in row.values()):
            raise ValueError("Probabilities must be non-negative numbers")
        if abs(sum(row.values()) - 1.0) > 1e-9:
            raise ValueError("Probabilities must sum to one")
        scores.append(
            sum((float(row[label]) - float(label == actual)) ** 2 for label in labels)
            / len(labels)
        )
    return {"item_count": len(scores), "multiclass_brier_score": sum(scores) / len(scores)}


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
