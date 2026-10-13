# RAG assistant audit: after the rag-answer-v2 integration (2026-10-13)

Same case set and offline extractive run as `baseline_audit.v1.md`. Engineering metrics only; legal validation is **UNVERIFIED**.

| Metric | Baseline | Integrated |
| --- | --- | --- |
| Support errors (wrong or missing version support) | 12 / 24 | 0 / 24 |
| Pairing errors (evidence from an Act outside the question) | 2 | 0 |
| Citation errors (cited Act outside the expected Acts) | 5 | 0 |
| Determination states matching source-derived expectations | 0 / 24 (all absent) | 24 / 24 |

**Coverage of the 24 queries:**

| Outcome | Cases |
| --- | --- |
| Supported | 7 |
| Provisional (machine-triage materiality) | 2 |
| Conditional | 2 |
| Partial, needs facts | 6 |
| Justified abstention | 4 |
| General answer | 3 |

**Determination states:** `{"textual_drift": {"OUT_OF_SCOPE": 6, "DETERMINED": 14, "INSUFFICIENT_EVIDENCE": 4}, "materiality": {"PROVISIONAL": 6, "INSUFFICIENT_EVIDENCE": 15, "OUT_OF_SCOPE": 3}, "answer_change": {"NEEDS_FACTS": 6, "CONDITIONAL": 2, "DETERMINED": 9, "INSUFFICIENT_EVIDENCE": 4, "OUT_OF_SCOPE": 3}, "risk": {"OUT_OF_SCOPE": 20, "NEEDS_FACTS": 2, "CONDITIONAL": 1, "INSUFFICIENT_EVIDENCE": 1}}`.

**Held-out pairing check:** one templated question for each of the 86 strongly corroborated graph-v4 transitions (`heldout_transitions.v1.json`). Result: {'correct_transition': 86}. Every question selected exactly that transition, and no evidence came from another Act.

## Caveats

- **Not held out:** the 24-case set was used during development. Four expectations were corrected after source inspection, each with its reason recorded in the case's `basis`:
  - the Companies s.105 footnote is real evidence;
  - insertions have no drift under drift-metrics-v3;
  - "what changed" questions consistently need facts;
  - comparing both versions needs both rules' facts.
- **Paraphrase:** the held-out check uses formal Act titles, so it tests pairing, not robustness to paraphrase.
- **Not legal accuracy:** no legal reviewer validated any answer.
