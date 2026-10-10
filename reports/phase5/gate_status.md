# Phase 5 — Benchmark and Materiality Integration Status

**Engineering gate: PASSED**
**Automated silver-label checkpoint: PASSED**
**Legal/research gold checkpoint: NOT PASSED**

## Automated materiality silver run

- 50 evidence-linked amendment-fragment cases processed by two deterministic rule systems.
- 50 provisional higher-label machine consensus outputs; 0 cases abstained for a >1-category disagreement.
- Raw algorithm agreement: 62%; Cohen's kappa between algorithms: 0.474.
- Machine agreement is not human inter-annotator agreement. The test set contains no `None` examples, so that class lacks empirical coverage.
- Scores against one rule system are included only as rule-to-rule comparison; they do not establish classifier accuracy.

## What is still not established

- No independent human annotations or independent human adjudications exist.
- No legal gold labels, legal reviewer approval, or approved frozen taxonomy exists.
- The current ten-dimension registry is still a draft pending the Phase 0 dimension-count decision.
- The 50 records contain operation-controlled fragments, not complete historical provision contexts.
- Classifier precision/recall/F1 against legal gold and validated classifier status remain unavailable.

Machine-generated silver outputs remain useful for triage and identifying disagreements, but they are not legally validated materiality labels and do not close the scientific checkpoint.
