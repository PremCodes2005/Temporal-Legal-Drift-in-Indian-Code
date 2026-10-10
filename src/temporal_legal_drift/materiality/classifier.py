"""Experimental supervised materiality model, gated on adjudicated gold only."""

from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Iterable

from temporal_legal_drift.metrics import classification_metrics

from .annotation import LABELS


_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?", re.I)
_CUES = {
    "obligation": re.compile(r"\b(?:shall|must|required|duty|obligation)\b", re.I),
    "prohibition": re.compile(r"\b(?:shall not|prohibit|forbid|unlawful)\b", re.I),
    "penalty": re.compile(r"\b(?:penalty|fine|imprisonment|liable|sanction)\b", re.I),
    "right": re.compile(r"\b(?:right|entitled|may|permitted)\b", re.I),
    "scope": re.compile(r"\b(?:means|includes|applies|person|company|authority)\b", re.I),
    "deadline": re.compile(r"\b(?:day|days|month|months|within|deadline|period)\b", re.I),
    "threshold": re.compile(r"\b(?:amount|threshold|percent|rupees?|₹)\b", re.I),
    "exception": re.compile(r"\b(?:except|provided that|exemption|notwithstanding)\b", re.I),
}
_OPERATIONS = ("INSERT", "SUBSTITUTE", "OMIT", "REPEAL", "RENUMBER", "REPLACE", "MODIFY", "UNKNOWN")


class ExperimentalMaterialityModel:
    """Dependency-free softmax linear model; not a validated legal classifier.

    The lexical feature set is a lexical baseline. The combined feature set adds
    operation and legal-cue deltas. Training rejects non-adjudicated rows and
    expects caller-controlled, group-disjoint train/test sets.
    """

    def __init__(self, feature_set: str = "combined", *, epochs: int = 350, learning_rate: float = 0.08, l2: float = 0.001) -> None:
        if feature_set not in {"lexical", "combined"}:
            raise ValueError("feature_set must be lexical or combined")
        if epochs < 1 or learning_rate <= 0 or l2 < 0:
            raise ValueError("Invalid optimizer configuration")
        self.feature_set = feature_set
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.l2 = l2
        self.vocabulary: tuple[str, ...] = ()
        self.weights: dict[str, dict[str, float]] = {}
        self.trained = False

    def fit(self, rows: Iterable[dict[str, Any]]) -> "ExperimentalMaterialityModel":
        values = tuple(rows)
        if not values:
            raise ValueError("Training requires adjudicated gold rows")
        if len({str(row.get("pair_id")) for row in values}) != len(values):
            raise ValueError("Training rows contain duplicate pair IDs")
        for row in values:
            if row.get("gold_status") != "ADJUDICATED_GOLD":
                raise ValueError("Training requires adjudicated gold; unadjudicated/non-gold rows are prohibited")
            label = row.get("materiality", {}).get("label")
            if label not in LABELS:
                raise ValueError("Every training row needs a canonical adjudicated label")
        feature_rows = [self._features(row) for row in values]
        self.vocabulary = tuple(sorted({name for row in feature_rows for name in row}))
        self.weights = {label: {name: 0.0 for name in self.vocabulary} for label in LABELS}
        labels = [str(row["materiality"]["label"]) for row in values]
        for _ in range(self.epochs):
            gradients = {label: {name: 0.0 for name in self.vocabulary} for label in LABELS}
            for features, gold in zip(feature_rows, labels):
                probabilities = self._probabilities(features)
                for label in LABELS:
                    error = probabilities[label] - float(label == gold)
                    for name, value in features.items():
                        gradients[label][name] += error * value
            scale = 1.0 / len(values)
            for label in LABELS:
                for name in self.vocabulary:
                    gradient = gradients[label][name] * scale + self.l2 * self.weights[label][name]
                    self.weights[label][name] -= self.learning_rate * gradient
        self.trained = True
        return self

    def predict(self, rows: Iterable[dict[str, Any]]) -> list[str]:
        if not self.trained:
            raise ValueError("Model must be fitted on adjudicated gold first")
        predictions = []
        for row in rows:
            probabilities = self._probabilities(self._features(row))
            predictions.append(min(LABELS, key=lambda label: (-probabilities[label], LABELS.index(label))))
        return predictions

    def evaluate(self, train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], *, group_key: str = "act_id") -> dict[str, Any]:
        if not train_rows or not test_rows:
            raise ValueError("Evaluation needs non-empty train and test partitions")
        train_groups = {str(row.get(group_key)) for row in train_rows}
        test_groups = {str(row.get(group_key)) for row in test_rows}
        if any(not row.get(group_key) for row in train_rows + test_rows) or train_groups & test_groups:
            raise ValueError(f"Train/test leakage detected across {group_key}")
        self.fit(train_rows)
        predictions = self.predict(test_rows)
        gold = [str(row["materiality"]["label"]) for row in test_rows]
        return {
            "status": "held_out_group_evaluation",
            "feature_set": self.feature_set,
            "group_key": group_key,
            "train_group_count": len(train_groups),
            "test_group_count": len(test_groups),
            "metrics": classification_metrics(gold, predictions, LABELS),
            "legal_validity_claimed": False,
        }

    def _features(self, row: dict[str, Any]) -> dict[str, float]:
        before = str(row.get("before_text") or "")
        after = str(row.get("after_text") or "")
        before_words = [word.casefold() for word in _WORD.findall(before)]
        after_words = [word.casefold() for word in _WORD.findall(after)]
        left, right = Counter(before_words), Counter(after_words)
        features: dict[str, float] = {
            "bias": 1.0,
            "token_similarity": SequenceMatcher(None, before_words, after_words, autojunk=False).ratio(),
            "before_length": math.log1p(len(before_words)),
            "after_length": math.log1p(len(after_words)),
            "token_delta": math.log1p(abs(len(after_words) - len(before_words))),
        }
        for word in set(left) | set(right):
            features[f"before:{word}"] = float(left[word] > 0)
            features[f"after:{word}"] = float(right[word] > 0)
            features[f"delta:{word}"] = float(right[word] > left[word]) - float(left[word] > right[word])
        if self.feature_set == "combined":
            operation = str(row.get("operation", "UNKNOWN")).upper()
            for value in _OPERATIONS:
                features[f"operation:{value}"] = float(operation == value)
            for cue_name, pattern in _CUES.items():
                old_hits = len(pattern.findall(before))
                new_hits = len(pattern.findall(after))
                features[f"cue_before:{cue_name}"] = float(old_hits > 0)
                features[f"cue_after:{cue_name}"] = float(new_hits > 0)
                features[f"cue_delta:{cue_name}"] = float(new_hits - old_hits)
        return {name: value for name, value in features.items() if value}

    def _probabilities(self, features: dict[str, float]) -> dict[str, float]:
        logits = {
            label: sum(self.weights.get(label, {}).get(name, 0.0) * value for name, value in features.items())
            for label in LABELS
        }
        maximum = max(logits.values(), default=0.0)
        exponents = {label: math.exp(max(-60.0, logits[label] - maximum)) for label in LABELS}
        denominator = sum(exponents.values()) or 1.0
        return {label: exponents[label] / denominator for label in LABELS}


def evaluate_materiality_gold(
    gold_document: dict[str, Any],
    split: dict[str, Any],
    *,
    epochs: int = 350,
) -> dict[str, Any]:
    """Compare implemented non-neural baselines on an explicit leakage-checked split."""
    from temporal_legal_drift.baselines import ClassPriorBaseline, MajorityBaseline, OperationPriorBaseline

    rows = gold_document.get("rows")
    if gold_document.get("status") != "adjudicated_gold" or not isinstance(rows, list):
        raise ValueError("Evaluation requires a frozen adjudicated materiality gold dataset")
    if gold_document.get("pair_count") != 50 or len(rows) != 50:
        raise ValueError("Evaluation requires the complete 50-pair materiality gold release")
    train_ids = split.get("train_pair_ids")
    test_ids = split.get("test_pair_ids")
    group_key = str(split.get("group_key", ""))
    split_method = str(split.get("split_method", ""))
    if not isinstance(train_ids, list) or not isinstance(test_ids, list) or not group_key:
        raise ValueError("Split must provide train/test pair IDs and a group key")
    if split_method not in {"act_held_out", "amendment_event_held_out", "provision_lineage_held_out", "source_held_out", "temporal_holdout", "domain_held_out"}:
        raise ValueError("Unsupported or ungrouped split method")
    ids = [str(value) for value in train_ids + test_ids]
    row_by_id = {str(row["pair_id"]): row for row in rows}
    if len(ids) != len(set(ids)) or set(ids) != set(row_by_id):
        raise ValueError("Split must assign every unique gold pair exactly once")
    train = [row_by_id[str(value)] for value in train_ids]
    test = [row_by_id[str(value)] for value in test_ids]
    if not train or not test:
        raise ValueError("Split must contain non-empty train and test groups")
    _assert_no_group_leakage(train, test, group_key)
    train_labels = [str(row["materiality"]["label"]) for row in train]
    test_labels = [str(row["materiality"]["label"]) for row in test]
    train_operations = [str(row["operation"]) for row in train]
    test_operations = [str(row["operation"]) for row in test]

    majority = MajorityBaseline().fit(train_labels).predict(len(test))
    class_prior = ClassPriorBaseline().fit(train_labels).predict(len(test))
    operation = OperationPriorBaseline().fit(train_operations, train_labels).predict(test_operations)
    lexical = ExperimentalMaterialityModel("lexical", epochs=epochs).fit(train).predict(test)
    combined = ExperimentalMaterialityModel("combined", epochs=epochs).fit(train).predict(test)
    predictions = {
        "majority": majority,
        "class_prior": class_prior,
        "operation_prior": operation,
        "lexical_softmax": lexical,
        "combined_lexical_operation_cue_softmax": combined,
    }
    return {
        "schema_version": "1.0.0",
        "status": "experimental_group_held_out_evaluation",
        "split_id": split.get("split_id"),
        "split_method": split_method,
        "group_key": group_key,
        "train_pair_count": len(train),
        "test_pair_count": len(test),
        "leakage_checks": {"no_group_overlap": True, "checked_group_keys": sorted(_LEAKAGE_KEYS | {group_key})},
        "results": {
            model_id: classification_metrics(test_labels, predicted, LABELS)
            for model_id, predicted in predictions.items()
        },
        "error_analysis": {
            model_id: _error_analysis(test, test_labels, predicted)
            for model_id, predicted in predictions.items()
        },
        "embedding_model": {"status": "not_run_model_not_selected"},
        "llm_model": {"status": "not_run_gold_first_policy"},
        "legal_validity_claimed": False,
        "classifier_validated": False,
    }


def _error_analysis(
    rows: list[dict[str, Any]], gold: list[str], predictions: list[str]
) -> dict[str, Any]:
    """Expose auditable held-out mistakes without generating legal explanations."""
    errors = [
        {
            "pair_id": str(row["pair_id"]),
            "gold": actual,
            "predicted": predicted,
            "operation": row.get("operation"),
            "act_id": row.get("act_id"),
            "provision_id": row.get("provision_id"),
            "amendment_event_id": row.get("amendment_event_id"),
            "adjudication_rationale": row.get("adjudication", {}).get("rationale"),
        }
        for row, actual, predicted in zip(rows, gold, predictions)
        if actual != predicted
    ]
    by_gold_label = Counter(item["gold"] for item in errors)
    by_operation = Counter(str(item.get("operation") or "UNKNOWN") for item in errors)
    return {
        "misclassified_count": len(errors),
        "misclassified_pair_ids": [item["pair_id"] for item in errors],
        "errors_by_gold_label": dict(sorted(by_gold_label.items())),
        "errors_by_operation": dict(sorted(by_operation.items())),
        "items": errors,
        "interpretation": "Inspect adjudication rationale and cited source evidence; this is a review queue, not an automated legal error diagnosis.",
    }


_LEAKAGE_KEYS = frozenset({"act_id", "amendment_event_id", "provision_id", "source_id"})


def _assert_no_group_leakage(
    train: list[dict[str, Any]], test: list[dict[str, Any]], primary_key: str
) -> None:
    keys = _LEAKAGE_KEYS | {primary_key}
    for key in keys:
        if key == "source_id":
            train_values = {
                str(source.get("source_id"))
                for row in train for source in row.get("source_evidence", [])
            }
            test_values = {
                str(source.get("source_id"))
                for row in test for source in row.get("source_evidence", [])
            }
        else:
            train_values = {str(row.get(key)) for row in train if row.get(key) is not None}
            test_values = {str(row.get(key)) for row in test if row.get(key) is not None}
        overlap = train_values & test_values
        if overlap:
            raise ValueError(f"Train/test leakage across {key}: {sorted(overlap)[:3]}")
