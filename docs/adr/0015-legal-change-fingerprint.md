# ADR 0015: Legal Change Fingerprint: wording, rule and outcome drift

Status: **accepted 2026-10-13**. Method: `docs/methodology/legal_change_fingerprint.v1.md`.

## Context

The legacy `overall_drift_percent` combines three signals in one number:
- a feature-hash similarity;
- a lexical similarity;
- a legal-cue proxy.

For graph transitions it is computed on the amendment fragments, so replacing "ten thousand" with "one lakh" scores 84% even though the clause barely moved. It cannot say *what* changed in the rule, or whether a scenario's answer changes.

## Decision

- **Three components, reported together and never averaged:**
  - wording drift (clause-level, surface wording);
  - rule drift (a field-level rule delta with a weighted, versioned score);
  - outcome drift (the same scenario facts under both rules).
- **Shared gates:** same provision, supported amendment, text quality, labelled kinds of version text, and separate dates. A missing component is null with a reason.
- **Legacy score:** the legacy overall score is kept unchanged and is labelled a legacy diagnostic in the API and the UI.
- **Contract:** response contract `rag-answer-v3`, which adds `fingerprint`; `determinations-v2`, which adds a separate `applicability`; and `textual_drift` deprecated in favour of `fingerprint.wording_drift`. All v2 fields are kept.
- **Risk:** it stays with the obligation registry; neither drift ever sets it.

## Rejected

- One combined "legal change" score: it would hide disagreements between the components, such as large rewording with no rule change.
- An LLM-scored rule drift: it is unverifiable. LLM proposals are allowed only behind schema and verbatim-span checks.
- Fragment-level wording drift: it overstates small edits.
