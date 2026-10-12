# ADR 0005 — Structured, evidence-bounded explanations

Status: **accepted 2026-10-12** (implementation: `src/temporal_legal_drift/explanations/contract.py`).

## Decision

Explanations are a fixed JSON contract (`structured-explanation-v1`). It covers:
- provision and version scope, dates and applicability status;
- the amendment fragment and materiality status;
- obligation and conditional risk;
- claims and citations, uncertainty, escalation, and generation method;
- `legal_validation: UNVERIFIED`.

**The default is deterministic.** Claims are assembled from validated stage outputs of an orchestration trace, and each cites anchors derived from that trace's source evidence.

**A language model may only rephrase the claims.** Its output must keep the same claims and anchors and pass `validate_explanation`. That validator checks:
- exact fields;
- version, date and risk equal to the trace;
- every citation an exact trace anchor;
- no claim citing an unknown anchor;
- no unsupported ISO dates;
- no fragment presented as a complete provision;
- escalation still required.

If the output fails any check, the deterministic claims are kept and `fallback_reason` records why. Raw model output is retained.

## Trade-off

Faithfulness by construction, at the cost of fluency and coverage: the explanation cannot say anything the pipeline did not establish. A free-form LLM answer was rejected because citation presence does not prove support. Automated validation remains separate from expert review.
