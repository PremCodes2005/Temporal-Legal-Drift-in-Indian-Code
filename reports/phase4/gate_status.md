# Phase 4 Gate Status

**Engineering/automated gate: PASSED**

**Temporal-applicability legal-validation gate: PENDING**

## Implemented

- Separate temporal fact types for publication, assent, commencement, applicability, legal effect, retrospective effect, transitional provisions, deferred commencement and partial commencement.
- Evidence references, review status, uncertainty and scenario conditions on every temporal fact.
- Applicability queries using scenario ID, provision lineage, reference date and attributes.
- Evidence-traced determinations with resolved, not-yet-effective and unresolved/escalated outcomes.
- Explicit refusal to infer applicability from publication, assent or latest-document recency alone.
- Explicit version-transition checks before one active version supersedes another.
- Conditional and partial-commencement handling.
- JSON schemas, CLI resolution command, deterministic self-check and automated tests.
- Real-corpus extraction of 1,873 evidence-linked temporal candidates; all remain unreviewed and none can drive a resolved answer.

## Engineering validation

- Pre-effective-date version selection: passed.
- Post-effective-date version selection through an explicit transition: passed.
- Publication-only evidence remains unresolved: passed.
- Unreviewed evidence remains unresolved: passed.
- Missing partial-commencement attributes cause escalation: passed.
- Temporal registry and code fact types reconcile: passed.
- Real-corpus candidate evidence and review-state reconciliation: passed.

## Legal/research blockers

- No real applicability determination has qualified legal-review approval.
- The legal hierarchy and interaction of commencement, retrospectivity and transitional provisions remain unencoded pending review.
- Real scenarios cannot enter benchmark gold until their temporal facts and governing-version determination are approved.

The engineering resolver is complete. Its output remains `resolved_requires_expert_confirmation` or an explicit unresolved status; it does not autonomously publish legal conclusions.
