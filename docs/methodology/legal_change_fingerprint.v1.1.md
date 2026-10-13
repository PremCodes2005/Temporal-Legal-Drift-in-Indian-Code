# Legal Change Fingerprint v1.1 (`legal-change-fingerprint-v1.1`, `rule-drift-v1.1`)

This document lists only the changes from `legal_change_fingerprint.v1.md`, which remains the full method and is unchanged. The weights in `configs/metrics/rule_drift.v1.1.json` equal those in v1; v1 stays in place for its release. ADR 0016 records the decision.

## Rule drift

- **Actor.** An actor is accepted only when the subject's head noun phrase ends in a recognised legal-actor noun: government, commission, court, tribunal, authority, board, committee, officer, controller, person, party, company, director, depositor, bank, licensee, and similar.
  - The head noun phrase is the subject cut at the first qualifier: issued, made, granted, appointed, by, under, of, which, who, for, in respect.
  - "Provided that", "it is hereby declared that" and leading conjunctions are stripped first.
  - So in "the Digital Signature Certificate issued by such Certifying Authority shall be valid", the head is "the Digital Signature Certificate". That is not an actor, and "Certifying Authority" inside the qualifier is not taken.
- **Action.** An action is extracted only for an accepted actor.
- **Unscored changes.** A change in the operative sentences that touches no supported field is now reported as **Not scored**. It has state INSUFFICIENT_EVIDENCE, `details.unscored_reason = UNSUPPORTED_RULE_FIELD` and a `method` limit.
  - Before v1.1 this was 0/100 or a spurious field score (IT s.19: "actor" 5/100).
  - A number is given only when a supported field changed and both sides are aligned.

## Outcome drift

- If rule drift is unscored, outcome drift cannot be "Unchanged". It reports "Cannot determine" with a `method` limit.
- **Registry rows:** a row may record `assumes`: the shared scope and conditions that both versions require and that were assumed to be met in order to isolate the decisive fact. These are listed in `details.assumptions` and in the reason.

## Limits (all components)

Each component carries `limit {kind, reason, action}`. The kind is one of:
- `evidence`: missing or unreliable legal text; the action is verify_source;
- `facts`: unknown user situation; the action is add_facts;
- `method`: outside what the method can score; the action is queue_review;
- `not_applicable`.

## Materiality triage (determinations-v3)

- **No frozen silver match:** with adequate evidence, the answer computes materiality on the fly using rule-cue-transition-v1 (rule A) and operation-delta-v1 (rule B).
  - When they agree, the label is shown; when they disagree, both are shown.
  - The state is PROVISIONAL, with `source: ON_THE_FLY_MACHINE_TRIAGE` and `review_status: NOT_REVIEWED_MACHINE_TRIAGE`.
- **Silver match:** the frozen silver label is shown with `source: FROZEN_SILVER_SET`.
- **Neither is gold**, and unreliable source text blocks triage.

**Known limitation:** rule A detects digit tokens only, so a number-word change (CPC s.32 "five hundred" → "five thousand") triages Low.

Legal validation of all of the above: UNVERIFIED.
