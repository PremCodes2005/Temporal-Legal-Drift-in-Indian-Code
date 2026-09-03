"""Auditable split-up drift and retrieval-alignment metrics."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


TOKEN_RE = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?")
CUES = {
    "obligation": ("shall", "must", "required", "duty"),
    "permission": ("may", "permitted", "authorised", "entitled"),
    "prohibition": ("shall not", "must not", "prohibited"),
    "penalty": ("penalty", "fine", "imprisonment", "punishable", "liable"),
    "scope": ("means", "includes", "applies to", "notwithstanding"),
}


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

    if pre_vector is not None and post_vector is not None and len(pre_vector) == len(post_vector):
        cosine_similarity = max(0.0, min(1.0, sum(a * b for a, b in zip(pre_vector, post_vector))))
    else:
        cosine_similarity = jaccard_similarity
    semantic_drift = (1 - cosine_similarity) * 100

    conceptual = conceptual_override if conceptual_override is not None else _conceptual_proxy(pre_chunk, post_chunk)
    conceptual = max(0.0, min(100.0, conceptual))
    overall_drift = semantic_drift * 0.40 + lexical_drift * 0.30 + conceptual * 0.30

    retrieval = max(0.0, min(1.0, sum(retrieval_scores) / 2))
    evidence_completeness = 1.0 if pre_chunk.strip() and post_chunk.strip() else 0.5 if pre_chunk.strip() or post_chunk.strip() else 0.0
    alignment = (retrieval * 0.50 + evidence_completeness * 0.30 + max(0.0, min(1.0, metadata_coverage)) * 0.20) * 100
    return {
        "semantic_drift_percent": round(semantic_drift, 1),
        "lexical_drift_percent": round(lexical_drift, 1),
        "conceptual_drift_percent": round(conceptual, 1),
        "overall_drift_percent": round(overall_drift, 1),
        "alignment_accuracy_percent": round(alignment, 1),
        "weights": {"semantic": 0.40, "lexical": 0.30, "conceptual": 0.30},
        "conceptual_method": conceptual_method,
        "accuracy_definition": "retrieval confidence, paired-evidence completeness and metadata coverage; not legal correctness",
    }


def _tokens(value: str) -> list[str]:
    return [item.lower() for item in TOKEN_RE.findall(value)]


def _conceptual_proxy(pre: str, post: str) -> float:
    before = pre.lower()
    after = post.lower()
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
    category_shift = 0
    if ("digital signature" in before and "electronic signature" in after) or (
        "electronic signature" in before and "digital signature" in after
    ):
        category_shift = 65
    return min(100.0, max(category_shift, cue_score + numeric_score + polarity_score))
