# Legal Change Fingerprint v1.2 (`legal-change-fingerprint-v1.2`, `rule-drift-v1.2`)

This document lists only the changes from v1.1 (`legal_change_fingerprint.v1.1.md`), which in turn amends v1. Earlier documents and configs are unchanged. Weights: `configs/metrics/rule_drift.v1.2.json` (total 100). Decision: ADR 0017. Evidence: `reports/fingerprint/heldout_transitions.v2.json` (86 transitions, 0 invariant violations).

## Rule fields

| Field (v1.2 key) | Label | Weight | Change in v1.2 |
| --- | --- | --- | --- |
| modality | Duty, permission or prohibition | 25 | "shall not be less than" is a minimum, not a prohibition |
| penalty | Penalty | 15 | "fine (upon him) not exceeding / of", "impose a fine", "penalty which shall…". An amount or term inside a penalty counts here only |
| threshold | Amount or numeric limit | 15 | Renamed from `monetary_threshold`; values are `amount: …` or `count: …` ("not exceeding four") |
| deadline | Deadline or period | 15 | "three hundred and thirty days", "twenty-one days", "seven consecutive years" parse |
| exception | Exception or proviso | 10 | unchanged |
| scope | Scope (what the rule covers) | 10 | An inserted or removed list item ("(ia) …") or Explanation is a scope change; modal verbs inside it are not counted as new duties |
| actor | Person or body named | 5 | Persons or bodies named *within the changed words* (Tribunal → Central Government; "or a District Authority" added). Plurals are equal; mentions inside "discretion of the court" belong to modality |
| action | What must be done | 5 | The first verb from a fixed operative-verb list after the modal, for a named person or body |

## Score and abstention

- **Score:** the sum of the weights of fields added, removed or changed. Every number has its field spans (offsets into the scored clauses), which the UI marks in Compare Evidence.
- **0/100:** only when the normalised clauses are identical.
- **Not scored:** a non-identical change that no supported field captures, with a reason that quotes the changed words:
  - `CROSS_REFERENCE_ONLY`: only provision numbers or labels changed ("149" → "150", "clause (e)" → "clause (b)");
  - `TERM_SUBSTITUTED`: content words were replaced by content words, and their effect depends on definitions this method does not compare ("Digital Signature" → "electronic signature");
  - `UNSUPPORTED_RULE_FIELD`: anything else, including added connectives ("or") whose effect can be large.

## Reading

`fingerprint.reading` turns the components' details into sentences:
- wording: how much changed and where;
- rule: each changed field, before → after, and why it matters (from the config);
- disagreement: wording under 10% with a key field changed (duty, penalty, amount or limit, deadline, exception), or wording of 30% or more with no rule score;
- outcome: present only when evaluated.

These are change diagnostics, never averaged: they are not legal correctness, confidence probabilities, materiality labels or risk scores.

## Outcome drift

Without facts, outcome drift asks only for facts that could decide a changed field (for example elapsed days for a day deadline). If none could, it reports a `method` limit instead of an empty facts request. Hypothetical boundary values are labelled as such and are never presented as the user's facts.

## Materiality triage input (determinations-v4)

On-the-fly triage converts number words to digits before applying the frozen rule-cue-transition-v1 and operation-delta-v1 rules ("not exceeding five hundred rupees" → "not exceeding 500 rupees"). Frozen silver labels are unchanged.

## Known limits

- The actor stop-list is a shortcut ("Government lodges").
- Action extraction is heuristic, and its weight is 5.
- A cross-reference renumbering still triages as Medium materiality, because the frozen rules see a numeric change.
- Detections were spot-checked by the developer, not reviewed by a lawyer.

Legal validation: UNVERIFIED.

## Why the rule-field weights are 25 / 15 / 15 / 15 / 10 / 10 / 5 / 5 (2026-10-20)

These are the **rule-drift field weights** (a 0–100 rule score). They are not the 0.2 / 0.3 / 0.4 / 0.1 weights of the combined indicator (TLDS); those are explained in `tlds.v1.md`.

- **Stated rationale (v1 methodology):** "the weights rank legal function". That is the only recorded reasoning. The exact numbers inside the tier order were not justified anywhere, so the text below is a **proposed rationale** for the existing tiers. The weights were not learned from data, not optimised, and not reviewed or approved by a legal expert.
- **Tiers:**
  1. Duty, permission or prohibition, 25: whether conduct is required, allowed or forbidden.
  2. Penalty, amount or numeric limit, and deadline, 15 each: the consequence, the trigger and the timing.
  3. Exception and scope, 10 each: coverage.
  4. Actor and action, 5 each: also legally relevant, but detected heuristically (a phrase list and a verb list), so a low weight limits the effect of extraction errors.
- **Total 100:** a score reads as the share of the fields' combined weight that changed. It is not a percentage of legal importance.
- **Counting:** each changed field counts once. Fields marked uncertain are excluded, so the score is then a lower bound. A change outside every field is Not scored, never 0.
- **Sensitivity** (`reports/fingerprint/rule_weights_sensitivity.v1.json`, 59 scored held-out changes): tiered alternatives keep the order (Spearman ≥ 0.952; ≥ 99.9% of strictly ordered pairs keep their order). Equal weights mostly change ties (614 pairs; Spearman 0.812). Actor is the most often changed field (31 of 59), which supports keeping the heuristic fields low. This checks stability only; no weighting is shown to be more correct.
