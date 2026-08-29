# Phase 9 Temporal LLM Drift Evaluation Protocol

**Status:** Controlled experiment executed as a non-gold operational smoke test; research performance scoring remains unavailable.

Every scenario is planned under six conditions: no legal context, pre-amendment context, post-amendment context, both versions, both versions plus reference date, and reconstructed temporally applicable context. Scenario facts are fingerprinted and must remain identical across conditions. Model, model version, prompt version, temperature and retrieval configuration are recorded for every run.

Responses must use the structured conclusions `compliant`, `non_compliant` or `indeterminate`, with cited version, citations, explanation and uncertainty. The normalizer rejects missing or unexpected fields. Paired scoring computes false stability and false instability with explicit counts and denominators; undefined rates remain `null` rather than being coerced to zero.

The current artifact contains 78 completed runs for 13 scaffolds and six conditions using `gpt-5.6-sol` through the OpenAI Codex CLI. All raw prompts and schema-valid responses are preserved. Because the scaffolds have no authored facts, legal questions, expected answers or expected-change labels, every output abstained as `indeterminate`. This is the expected safe pipeline behaviour, not a performance result. No temporal-drift accuracy metric is reported.
