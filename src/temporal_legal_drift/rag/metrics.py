"""Auditable split-up drift and retrieval-alignment metrics."""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from hashlib import sha256


TOKEN_RE = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?")
CUES = {
    "obligation": ("shall", "must", "required", "duty"),
    "permission": ("may", "permitted", "authorised", "entitled"),
    "prohibition": ("shall not", "must not", "prohibited"),
    "penalty": ("penalty", "fine", "imprisonment", "punishable", "liable"),
    "scope": ("means", "includes", "applies to", "notwithstanding"),
}
DRIFT_LEVEL_THRESHOLDS = {
    "Low": "0.0-33.3",
    "Medium": "33.4-66.6",
    "High": "66.7-100.0",
}
DRIFT_WEIGHTS = {"semantic": 0.40, "lexical": 0.30, "conceptual": 0.30}
DRIFT_DISAGREEMENT_THRESHOLD = 60.0
METRICS_CONTRACT_VERSION = "drift-metrics-v3"  # configs/metrics/drift_score.v3.json


def calculate_drift_metrics(
    pre_chunk: str,
    post_chunk: str,
    *,
    pre_vector: list[float] | None = None,
    post_vector: list[float] | None = None,
    conceptual_override: float | None = None,
    conceptual_method: str = "legal_cue_proxy",
    retrieval_scores: tuple[float, float] = (0.0, 0.0),
    metadata_coverage: float = 0.0,
) -> dict[str, object]:
    """Return distinct drift and grounding metrics on a 0–100 scale."""
    pre_tokens = _tokens(pre_chunk)
    post_tokens = _tokens(post_chunk)
    pre_set, post_set = set(pre_tokens), set(post_tokens)
    jaccard_similarity = len(pre_set & post_set) / max(1, len(pre_set | post_set))
    sequence_similarity = SequenceMatcher(None, pre_tokens, post_tokens, autojunk=False).ratio()
    lexical_drift = (1 - (jaccard_similarity * 0.55 + sequence_similarity * 0.45)) * 100

    unavailable: dict[str, str] = {}
    if pre_vector is not None and post_vector is not None and len(pre_vector) == len(post_vector):
        cosine_similarity: float | None = max(0.0, min(1.0, sum(a * b for a, b in zip(pre_vector, post_vector))))
        semantic_drift: float | None = (1 - cosine_similarity) * 100
    else:
        # v2: no hidden substitute (v1 silently reused Jaccard similarity here).
        cosine_similarity = semantic_drift = None
        unavailable["semantic"] = "feature vectors were not supplied for both texts"
    if not pre_chunk.strip() or not post_chunk.strip():
        unavailable["pair"] = "before or after text is missing; no drift is computed"

    conceptual = conceptual_override if conceptual_override is not None else _conceptual_proxy(pre_chunk, post_chunk)
    conceptual = max(0.0, min(100.0, conceptual))
    component_scores = {
        "semantic": semantic_drift,
        "lexical": lexical_drift,
        "conceptual": conceptual,
    }
    if "pair" in unavailable:
        component_scores = {name: None for name in component_scores}
    available = {name: value for name, value in component_scores.items() if value is not None}
    # The overall score exists only when every weighted component does; otherwise it is unavailable.
    overall_drift = _aggregate_drift(available, DRIFT_WEIGHTS) if len(available) == len(component_scores) else None
    component_spread = (max(available.values()) - min(available.values())) if available else 0.0

    retrieval = max(0.0, min(1.0, sum(retrieval_scores) / 2))
    evidence_completeness = 1.0 if pre_chunk.strip() and post_chunk.strip() else 0.5 if pre_chunk.strip() or post_chunk.strip() else 0.0
    alignment = (retrieval * 0.50 + evidence_completeness * 0.30 + max(0.0, min(1.0, metadata_coverage)) * 0.20) * 100
    metric_values = {**component_scores, "overall": overall_drift}
    weight_total = sum(DRIFT_WEIGHTS.values())
    weighted_square_contributions = {
        name: round(DRIFT_WEIGHTS[name] * score * score / weight_total, 2) if score is not None else None
        for name, score in component_scores.items()
    }
    rounded = lambda value: round(value, 1) if value is not None else None  # noqa: E731
    return {
        "metrics_contract_version": METRICS_CONTRACT_VERSION,
        "semantic_drift_percent": rounded(component_scores["semantic"]),
        "lexical_drift_percent": rounded(component_scores["lexical"]),
        "conceptual_drift_percent": rounded(component_scores["conceptual"]),
        "overall_drift_percent": rounded(overall_drift),
        "availability": {name: ("unavailable" if value is None else "available") for name, value in metric_values.items()},
        "unavailable_reasons": unavailable,
        "evidence_alignment_quality_percent": round(alignment, 1),
        "alignment_accuracy_percent": round(alignment, 1),
        "deprecated_fields": {
            "alignment_accuracy_percent": "renamed evidence_alignment_quality_percent in drift-metrics-v2; it never measured accuracy",
        },
        "compared_text_sha256": {
            "pre": sha256(pre_chunk.encode("utf-8")).hexdigest(),
            "post": sha256(post_chunk.encode("utf-8")).hexdigest(),
        },
        "changed_spans": _changed_spans(pre_tokens, post_tokens),
        "weights": DRIFT_WEIGHTS,
        "aggregation_method": "weighted_root_mean_square",
        "component_spread_percent": round(component_spread, 1),
        "component_disagreement": component_spread >= DRIFT_DISAGREEMENT_THRESHOLD,
        "aggregation_note": (
            "Weighted RMS preserves strong drift signals instead of allowing a low component "
            "to cancel a high component. Component scores remain visible and must be interpreted separately."
        ),
        "levels": {name: _drift_level(value) for name, value in metric_values.items() if value is not None},
        "level_thresholds": DRIFT_LEVEL_THRESHOLDS,
        "conceptual_method": conceptual_method,
        "accuracy_definition": "evidence-alignment quality: retrieval confidence, paired-evidence completeness and metadata coverage; not answer accuracy, legal correctness or a probability",
        "calculation_trace": {
            "semantic": {
                "method": "cosine of deterministic 256-dimension feature-hash token vectors; not a pretrained semantic encoder",
                "cosine_similarity_percent": round(cosine_similarity * 100, 1) if cosine_similarity is not None else None,
                "formula": "100 × (1 - cosine similarity)",
            },
            "lexical": {
                "pre_token_count": len(pre_tokens),
                "post_token_count": len(post_tokens),
                "jaccard_similarity_percent": round(jaccard_similarity * 100, 1),
                "sequence_similarity_percent": round(sequence_similarity * 100, 1),
                "formula": "100 × (1 - (0.55 × Jaccard similarity + 0.45 × sequence similarity))",
            },
            "conceptual": {
                "method": conceptual_method,
                "pre_legal_cues": _present_cues(pre_chunk),
                "post_legal_cues": _present_cues(post_chunk),
                "pre_numbers": sorted(set(re.findall(r"\b\d+(?:\.\d+)?\b", pre_chunk))),
                "post_numbers": sorted(set(re.findall(r"\b\d+(?:\.\d+)?\b", post_chunk))),
                "formula": "Evidence-bound LLM score when available; otherwise deterministic legal-cue, numeric and polarity changes",
            },
            "overall": {
                "formula": "sqrt(0.40 × semantic² + 0.30 × lexical² + 0.30 × conceptual²)",
                "weighted_square_contributions": weighted_square_contributions,
                "sum_of_weighted_squares": round(sum(weighted_square_contributions.values()), 2)
                if overall_drift is not None else None,
            },
            "alignment": {
                "average_retrieval_confidence_percent": round(retrieval * 100, 1),
                "paired_evidence_completeness_percent": round(evidence_completeness * 100, 1),
                "metadata_coverage_percent": round(max(0.0, min(1.0, metadata_coverage)) * 100, 1),
                "formula": "0.50 × retrieval confidence + 0.30 × evidence completeness + 0.20 × metadata coverage",
            },
        },
    }


def _aggregate_drift(
    scores: dict[str, float], weights: dict[str, float]
) -> float:
    """Aggregate drift without cancellation between opposing component scores.

    A weighted arithmetic mean maps equally weighted 0 and 100 signals to 50,
    which can misleadingly imply moderate agreement. Weighted RMS retains the
    magnitude of the high signal while keeping every component independently
    auditable.
    """
    active = [
        (max(0.0, min(100.0, float(value))), float(weights.get(name, 0.0)))
        for name, value in scores.items()
        if float(weights.get(name, 0.0)) > 0
    ]
    total_weight = sum(weight for _, weight in active)
    if total_weight <= 0:
        return 0.0
    return math.sqrt(sum(weight * value * value for value, weight in active) / total_weight)


def _drift_level(value: float) -> str:
    """Map a 0-100 drift score to a stable descriptive band."""
    if value <= 33.3:
        return "Low"
    if value <= 66.6:
        return "Medium"
    return "High"


def _tokens(value: str) -> list[str]:
    return [item.lower() for item in TOKEN_RE.findall(value)]


def _spelling_normalised(text: str) -> str:
    """Treat -ize/-ise spellings alike so a spelling-only edit is not a legal-cue change."""
    return re.sub(r"\b(\w+?)iz(e|ed|es|ing|ation|ations)\b", r"\1is\2", text.lower())


def _conceptual_proxy(pre: str, post: str) -> float:
    before = _spelling_normalised(pre)
    after = _spelling_normalised(post)
    changed_groups = 0
    for values in CUES.values():
        left = {cue for cue in values if cue in before}
        right = {cue for cue in values if cue in after}
        changed_groups += left != right
    cue_score = changed_groups / len(CUES) * 70
    before_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", before))
    after_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", after))
    numeric_score = 20 if before_numbers != after_numbers else 0
    polarity_score = 10 if (" shall not " in f" {before} ") != (" shall not " in f" {after} ") else 0
    # v2 removed a hard-coded "digital/electronic signature" score of 65: it was a
    # corpus-specific term pair, not a general legal-cue method.
    return min(100.0, cue_score + numeric_score + polarity_score)


def _changed_spans(before: list[str], after: list[str], limit: int = 40) -> list[dict[str, object]]:
    """Token-level edits between the exact compared texts, for display and audit."""
    spans = []
    for operation, a0, a1, b0, b1 in SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
        if operation != "equal":
            spans.append({"operation": operation, "before": " ".join(before[a0:a1]), "after": " ".join(after[b0:b1])})
    return spans[:limit]


def _present_cues(text: str) -> list[str]:
    lowered = _spelling_normalised(text)
    return sorted(
        f"{group}:{cue}"
        for group, values in CUES.items()
        for cue in values
        if cue in lowered
    )
