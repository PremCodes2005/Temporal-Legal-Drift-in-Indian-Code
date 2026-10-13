# Legal Change Fingerprint (`legal-change-fingerprint-v1`)

This method answers three separate questions about one amendment of one provision. The three values are shown side by side and are **never averaged**. ADR 0015 records the design decision; the configs are `configs/metrics/wording_drift.v1.json` and `configs/metrics/rule_drift.v1.json`.

| Question | Component | Unit | Output |
| --- | --- | --- | --- |
| How much did the clause's wording change? | Wording drift | Whole aligned clause | 0–100% plus added, removed and substituted spans |
| What changed in the legal instruction? | Rule drift | Operative sentence(s) containing the change | Field-by-field rule delta plus a 0–100 weighted score |
| Does the answer change for your scenario? | Outcome drift | Your facts, applied to both rules | Changed, Unchanged or Cannot determine; a percentage only over a stated set of controlled scenarios |

## Gates that apply to all three

Each gate must pass first; otherwise the component abstains and gives its reason.
- **Same provision and amendment:** the clauses must be the same provision, with a supported amendment relationship. That means a corroborated graph-v4 transition, or the consolidated Act's own numbered footnote whose amending Act number is verified.
- **Text quality:** text-quality-v1 and the corpus extraction-risk list must pass. Unreliable OCR is never scored as law.
- **Kinds of version text:** these are always labelled and never conflated:
  - a verbatim current consolidated clause;
  - a derived earlier clause (this amendment reverted in today's text);
  - graph amendment fragments;
  - a footnote reconstruction.
- **Dates:** publication, commencement and scenario applicability remain separate fields (`determinations.applicability`).
- **Missing values:** a missing component is `null` with a reason, never 0.

## Wording drift (wording-drift-v1)

1. **Before clause.** The after clause is the verbatim current consolidated text of the section, with footnotes removed. The before clause is derived by replacing this amendment's words (located by its footnote marker, or by a unique exact match) with the earlier words. For an insertion, the inserted words are removed. A footnote reconstruction is already clause-level.
2. **Normalisation.** Case, whitespace, amendment markers, punctuation and -ise/-ize spelling are normalised. If nothing differs after that, the score is 0 and the change is flagged `FORMATTING_ONLY`.
3. **Score.** wording drift = 0.5 × lexical drift + 0.5 × feature-vector drift, both from drift-metrics-v3 and both computed on the normalised clauses. The feature vector is a deterministic token hash, not a semantic embedding. The arithmetic mean is used because both inputs measure surface wording.
4. **Spans.** Every added, removed or substituted span is returned with character offsets into the exact compared clauses, and each clause cites its evidence item (hash, page, line).

## Rule drift (rule-drift-v1)

- **Rule delta.** A deterministic extractor reads eight fields from the operative sentence(s) of each clause: modality, penalty, monetary threshold, deadline, exception, scope, actor and action.
- **Per field it returns:** the before value, the after value, the operation (ADDED, REMOVED, CHANGED, UNCHANGED or ABSENT), character spans in each clause, and an extraction status (EXTRACTED, NOT_PRESENT or UNCERTAIN).
- **Score.** The score is the sum of the weights of the changed fields: modality 25, penalty 15, monetary threshold 15, deadline 15, exception 10, scope 10, actor 5, action 5 (total 100). The weights rank legal function: whether conduct is required, allowed or forbidden comes first; then consequence, trigger and timing; then coverage. Actor and action are weighted low because their extraction is heuristic.
- **Uncertainty.** UNCERTAIN fields are excluded, and the score is labelled a lower bound.
- **What the score is not:** it does not depend on text length, token overlap or materiality.
- **LLM proposals:** an LLM may propose field values. A proposal is kept only if it passes the schema and the verbatim-span checks.

## Outcome drift (outcome-drift-v1)

- **Method.** The same facts are applied to the before rule and the after rule:
  - **deadline:** `days_elapsed` is compared with the period;
  - **monetary threshold:** `amount` is compared with the limit;
  - **exception:** `exception_conditions_met`;
  - **penalty:** `contravention`;
  - **modality:** `within_scope`;
  - **modelled obligation rules:** the obligation registry.
- **Result.** Each evaluated field gives a before answer and an after answer. The outcome is **Changed** when a supported answer flips, and **Unchanged** when every changed field was evaluated and none flipped.
- **Cannot determine.** Otherwise the result is Cannot determine, with the missing facts listed.
- **Compatibility percentage.** If shown, 0 means no supported answer flip and 100 means a supported flip.
- **Controlled sets.** For deadlines and thresholds, a controlled set of boundary scenarios is generated from the rule values. Its percentage is flips divided by scenarios evaluated, with the denominator shown.
- **Not risk.** Outcome drift is not risk. Risk stays with the obligation registry and engine, and neither wording drift nor rule drift is ever an input to it.

## Legacy

`metrics.overall_drift_percent` (drift-metrics-v3) is unchanged and is labelled a **legacy diagnostic**. It blends wording and legal-cue signals and was computed on fragments, so the new wording drift is not expected to equal it.
