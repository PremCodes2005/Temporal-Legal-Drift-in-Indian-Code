# Phase 9 Temporal LLM Drift Evaluation Protocol

**Status:** Controlled experiment planner, assertion normalizer and drift metrics implemented; model execution not performed.

Every scenario is planned under six conditions: no legal context, pre-amendment context, post-amendment context, both versions, both versions plus reference date, and reconstructed temporally applicable context. Scenario facts are fingerprinted and must remain identical across conditions. Model, model version, prompt version, temperature and retrieval configuration are recorded for every run.

Responses must use the structured conclusions `compliant`, `non_compliant` or `indeterminate`, with cited version, citations, explanation and uncertainty. The normalizer rejects missing or unexpected fields. Paired scoring computes false stability and false instability with explicit counts and denominators; undefined rates remain `null` rather than being coerced to zero.

The current plan contains 78 blocked runs for 13 scaffolds and six conditions. No provider was called, no response exists and no temporal-drift metric is reported.
