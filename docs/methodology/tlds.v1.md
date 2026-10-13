# Hybrid Temporal Legal Drift Score (`tlds-v1`)

`fingerprint.tlds` in every rag-answer-v5 response. Config: `configs/metrics/tlds.v1.json`. Code: `rag/fingerprint.py` (`tlds`, `composite` and the four `*_component` functions). Decision: ADR 0018. Evidence: `reports/fingerprint/tlds_heldout.v1.json` (generator alongside it).

TLDS is added alongside wording, rule and outcome drift (legal-change-fingerprint-v1.2), which are unchanged.

## Formula

D = 100 × (0.20·T + 0.30·S + 0.40·L + 0.10·R), each component in [0, 1]. TLDP is the same value read as a percentage (`tldp_percent`).

TLDS is an indicator of change between two versions of one clause. It is **not**:
- the share of a statute that changed;
- legal correctness;
- a probability;
- materiality;
- risk.

The weights are research parameters. `tlds(..., weights=...)` and `composite(values, weights)` accept alternatives. The weights must:
- name exactly the four components;
- be finite and non-negative;
- sum to 1.

Anything else raises `ValueError`.

## Components

| | Method | Value | Missing (null, never 0) when |
|---|---|---|---|
| T | `token-levenshtein-v1` | Token edit distance ÷ the longer clause's token count | Both clauses have no tokens |
| S | `embedding-cosine-v1` | 1 − cosine of the clause embeddings, with cosine clipped to [0, 1] | The embedding fails, or a vector is missing, non-numeric, non-finite, zero or of a different length |
| L | `legal-effect-rubric-v1` | Most severe detected rule-field change, by the rubric below | Rule drift is "Not scored" (a cross-reference, a term substitution or an unsupported field) |
| R | `rule-element-edit-v1` | (only-before + only-after − substitutions) ÷ (distinct elements − substitutions) | The text changed but neither clause has an extracted element |

**Common to all four components:**
- Text is normalised first, as for wording drift: case and spacing, amendment markers, punctuation, and -ise/-ize spellings. "not", modal verbs and numbers stay as tokens.
- Identical normalised clauses score 0 on every component.
- A pair that is unsupported, or that fails the text-quality gate, has all four components missing.

**S (semantic):**
- The default embedding is the retriever's deterministic 256-dimension feature-hash vector. It reflects shared words, not meaning, so it largely tracks T.
- Its model is recorded in `components.semantic.details.model`.
- A real semantic model would be a new local dependency. That was considered and not adopted (ADR 0018).

**L (legal effect):**
- L reuses the rule-drift v1.2 fields and their text positions.
- Each detected change is listed in `components.legal_effect.details.changes` with its score and before/after spans.

**R (rule structure):**
- The elements are the field values from every sentence, plus list items, Explanations and cross-references.
- List items are keyed by their content, so relabelling an item does not count.
- A renumbered cross-reference counts as one substituted dependency.
- A removed and an added element of the same kind count as one substitution.

## Legal-effect rubric

| Score | Meaning | Detected change |
|---|---|---|
| 1.00 | Fundamental change or reversal | A duty or permission is replaced by a prohibition in the same aligned sentences, or the reverse |
| 0.75 | Substantial change to an obligation, entitlement or restriction | A duty or permission is added, removed or changed; a penalty is added or removed |
| 0.50 | Material change to a condition, procedure or scope | A penalty, amount or numeric limit, deadline, exception, scope, or person or body changed |
| 0.25 | Limited change | Action verb changed |
| 0.00 | No detected change | Identical after normalisation |

Aggregation takes the maximum, so the most severe change counts once and every change remains listed.

## Missing components and partial scores

- **COMPLETE:** all four components exist; `value` is D.
- **INCOMPLETE:** `value` is null, and `missing_components` lists what is missing.
- **`partial_value`:** 100 × Σ_available w·x ÷ Σ_available w. It is labelled "not comparable with complete scores" and is never placed in `value`.
- **NOT_APPLICABLE:** the question is not about a change.
- **Precision:** values are stored unrounded. Labels round to 1 decimal, and bands use the rounded value.

## Bands (provisional, not empirically validated)

| Score | Band |
|---|---|
| 0–9 | Very low |
| 10–29 | Low |
| 30–49 | Moderate |
| 50–74 | High |
| 75–100 | Very high |

## Held-out run (86 transitions)

- **States:** 59 COMPLETE and 27 INCOMPLETE.
  - 24 are missing L only, because rule drift is "Not scored".
  - 3 are missing everything: the wording abstained, so no clause pair exists.
- **Invariants:** 0 violations, and the v1.2 wording and rule values are unchanged for all 86.
- **Default weights:** median 22.3 (range 20.2–51.2).
- **The composite understates legal effect.** 42 of 59 complete scores are "Low" although L ≥ 0.5. Amendments are usually short, so T, S and R are small, and D is roughly 40 × L plus a few points.
  - This is why the Drift Explanation view shows L beside D, with a note whenever L ≥ 0.5 but the band is Low or Very low.
  - With legal-heavy weights (0.1 / 0.1 / 0.6 / 0.2) none are Low; with wording-heavy weights, 58 are.
  - Rank order hardly depends on the weights (Spearman ≥ 0.976 against the default), but the bands depend on them heavily.

## Known limits

- S is a stand-in for meaning, not a semantic model.
- L reads only the rule-drift v1.2 fields:
  - a changed date outside a deadline phrase, a term substitution or a cross-reference leaves L missing;
  - the size of a change is ignored, so 500 → 5,000 counts the same as 500 → 501;
  - "file" vs "be filed" reads as an action change (L = 0.25).
- R uses the same extractors, so it shares their misses. With few elements it is coarse: a single changed element out of one gives R = 1.
- The weights, rubric and bands have no expert-labelled ground truth. The tests check that the software behaves as specified, not that the legal judgements are right.

Legal validation: UNVERIFIED.
