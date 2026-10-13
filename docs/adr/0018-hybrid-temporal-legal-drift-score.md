# ADR 0018: Hybrid Temporal Legal Drift Score (tlds-v1)

Status: **accepted 2026-10-13**. Method: `docs/methodology/tlds.v1.md`. Evidence: `reports/fingerprint/tlds_heldout.v1.json`.

## Context

The project owner asked for one transparent drift score built from four components: textual (T), semantic (S), legal-effect (L) and rule-structure (R). ADRs 0015 and 0017 had rejected a combined change score because it hides a small wording change with a large legal effect.

## Decision

- **Combined score, added alongside the fingerprint:** `fingerprint.tlds` = 100 × (0.2T + 0.3S + 0.4L + 0.1R), stored with all four components.
  - Wording, rule and outcome drift (v1.2) are unchanged.
  - This partly reverses the "one combined change score" rejection: the composite exists, but L is always shown separately, with a note when the composite band understates it.
- **Weights:** set in `configs/metrics/tlds.v1.json`; alternatives can be passed in and are compared in the held-out report.
- **Missing components:** the score is complete only when all four exist. Otherwise it is INCOMPLETE, with a separately named partial value.
- **S stand-in:** S uses the existing deterministic feature-hash embedding, labelled as a word-overlap stand-in. No local embedding model is installed (Ollama has only `qwen3:4b`), and adding one would bring a download and nondeterminism across model versions.
- **Contract:** the v5 schema allows the new key, so the contract and fingerprint versions are unchanged. `tlds-v1` is added to the analysis ID's method list, so stored records are never reused across the change.
- **UI:** the Drift Explanation view gains a "Combined indicator" section with the four parts, the worked calculation and the weights. Records without TLDS omit the section.

## Consequences

- With the default weights, most material amendments score "Low" (42 of 59), because L contributes 40 × L and short amendments add little else. The bands are provisional and need expert-labelled data before they mean anything.
- Unscored rule changes (24 of 86) give no composite. Turning missing evidence into 0 would be worse.

## Rejected

- **Renormalising missing components into the main score:** it silently compares partial with complete scores.
- **A pretrained embedding service:** external API cost, and nondeterministic test inputs.
- **Weighted RMS, as in legacy drift-metrics-v3:** the requested formula is linear, and linearity keeps each contribution readable.
