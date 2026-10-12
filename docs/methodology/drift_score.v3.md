# Drift score methodology — `drift-metrics-v3`

Machine-readable configuration: `configs/metrics/drift_score.v3.json`. A test asserts that it matches `rag/metrics.py`. v3 adds reliability indicators and a question-relevance statement; **the numbers are unchanged from v2**.

## What is scored

One **provision-aligned before/after pair** chosen for the question. Pairs come from one of:
- the before/after fragments of a strongly corroborated graph-v4 transition;
- an India Code consolidated-text substitution footnote **in the same section the question names**.

Nothing else is scored. Two excerpts that are not shown to be the same provision get **no score**: `PAIR_UNALIGNED`, `SCORING_UNAVAILABLE`.

## Components (each 0–100)

| Component | Inputs | Formula | Meaning / limits |
| --- | --- | --- | --- |
| Lexical | Tokens of the exact compared texts | `100 × (1 − (0.55·J + 0.45·S))`; J = token-set Jaccard, S = token-sequence ratio | Wording movement. A 10→15-day edit scores low here, even though it may matter legally. |
| Vector (`semantic_drift_percent`) | 256-dimension feature-hash token vectors | `100 × (1 − cosine)` | Bag-of-tokens representation movement. **Not** a trained semantic model. |
| Conceptual | Cue groups, numbers, negation; or a validated model score | Proxy: `70 × changed cue groups / 5 + 20·[numbers changed] + 10·[“shall not” changed]`, capped at 100 | Signals legal-effect cues. It is not a legal judgment. The method that ran is always shown. |

## Aggregation

**Formula:** `overall = sqrt((0.40·V² + 0.30·L² + 0.30·C²) / 1.0)`.

**Why weighted RMS rather than a mean:** with equal weights, a mean turns opposing 0 and 100 components into "50 %, moderate". RMS keeps the strong signal (70.7). Whenever the component spread is ≥ 60 points, an explicit **disagreement warning** is shown.

**Weights:** the 40/30/30 split is a versioned baseline, not a calibrated choice. Sensitivity analysis against independent reference judgements is future work.

**Missing components:** if any component is missing, the overall score is **unavailable**, with the reason.

## Bands

Low 0–33.3, Medium 33.4–66.6, High 66.7–100. Bands describe text movement **only**. They are not the materiality classes, a compliance outcome, urgency or risk.

## Reliability indicators (reported separately, never folded into drift)

| Indicator | Values |
| --- | --- |
| `evidence_coverage` | Both sides present / one side / none |
| `pairing` | `GRAPH_TRANSITION_FRAGMENTS`, `CONSOLIDATED_FOOTNOTE_RECONSTRUCTION`, `UNALIGNED_EXCERPTS` |
| `temporal_certainty` | `EFFECTIVE_DATE_EVIDENCED` (graph, Act-wide basis); `FOOTNOTE_STATED_DATE_UNVERIFIED` (the "w.e.f." date printed in India Code); or `UNRESOLVED` |
| `retrieval_relevance` | Mean retrieval score of the two selected chunks: a ranking signal, not correctness |

`evidence_alignment_quality_percent` (v2) remains, combining retrieval, completeness and metadata. It is not answer accuracy or a probability; `alignment_accuracy_percent` is a deprecated alias.

## Question relevance

Each score states whether the compared clause is the section the question named (`MATCHES_REQUESTED_SECTION`, `NO_SECTION_IN_QUESTION`, `DIFFERENT_SECTION`). It also states that **the score does not decide whether the user's situation is answered differently**. That needs applicable-version, scenario-fact and consequence analysis, which remain separate.

## Verification

- `tests/unit/test_drift_scoring.py`: frozen synthetic fixtures. They cover identical text, spelling-only, 10→15 days, negation, added penalty, long insertion, large cosmetic renumbering, short fragments, OCR corruption, missing sides and opposing components. They check determinism, bounds, recomputation from returned components, and the disagreement rule.
- `tests/unit/test_rag.py`: unaligned and wrong-section pairs get no score.
