# Phase 8 Baseline and Materiality-Modelling Protocol

**Status:** Baseline framework and deterministic feature preparation implemented; evaluation not run because no frozen gold benchmark exists.

The registered suite covers majority, class-prior, lexical/edit, amendment-operation, legal-cue, generic document-revision, zero-shot LLM, few-shot LLM, legal-encoder, long-context, closest-work-inspired and optional proposed-model families. Registration does not mean every external or neural model has been implemented or executed; each entry records its actual status.

Implemented dependency-free components include majority and class-prior predictors, operation-prior prediction, lexical/edit features, legal-cue counts, confusion matrices, per-class precision/recall/F1, macro-F1, high-materiality false-negative rate and multiclass Brier score. Test-set tuning is disabled. Any future run must use the frozen release checksum, registered seed and canonical labels, and preserve predictions and configuration.

The current artifact has 50 feature rows, zero gold labels and zero metrics. No prior work is claimed as reproduced.
