# Phase 10 Evidence-Grounded Explanation Protocol

**Status:** Structured rubric, evidence-resolution checks and explanation-drift detection implemented; explanation scoring not performed.

An explanation record includes the instrument, provision path, applicable date, version, before/after evidence, amendment operation, materiality dimensions and level, compliance consequence, citations, confidence and uncertainty/escalation reason.

Automated support checks cover field completeness, evidence-identifier resolution, version alignment, temporal alignment, citation precision, uncertainty presence and explanation-drift flags. A correct consequence supported by a stale version, date or citation is flagged as explanation drift when gold fields are available.

Automated support is not legal correctness. Entailment, materiality reasoning, compliance reasoning, evidence correctness and acceptability remain expert-required dimensions. LLM-as-judge is not permitted as the sole legal evaluator. The current plan contains no model explanations, automated scores, expert scores or aggregate quality claims.
