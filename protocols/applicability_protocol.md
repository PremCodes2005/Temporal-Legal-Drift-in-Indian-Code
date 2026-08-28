# Phase 4 Temporal Applicability Protocol

**Status:** Engineering implementation complete; qualified legal-validation gate pending.

The resolver answers: given scenario S, reference date T and provision lineage L, which evidence-supported version governs?

Rules:

1. Publication and assent are represented separately and do not alone prove applicability.
2. Only temporal facts with `approved` review status can support a determination.
3. Commencement, applicability, legal effect, retrospective effect, deferred commencement and partial commencement require explicit effective evidence.
4. Conditional facts require matching scenario attributes; missing attributes cause escalation.
5. Transitional provisions cause escalation unless an approved adjudication rule is later added.
6. Multiple active versions require an explicit supersession path in the version graph.
7. Conflicting dates, missing evidence and ambiguous branches remain unresolved.
8. A technically resolved result still requires qualified expert confirmation.
9. No latest-version heuristic is permitted.
10. The resolver does not determine the scenario's compliance consequence.
