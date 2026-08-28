# Phase 7 Benchmark Release and Leakage Protocol

**Status:** Technical release dry run implemented; scientific benchmark freeze refused for non-gold inputs.

The release builder reconciles Phase 5 and 6 counts and checksums, detects normalized exact duplicates and high token-Jaccard near duplicates, groups duplicate records before split assignment and reports all six required split strategies. Amendment-event-held-out and lineage-held-out dry runs use their grouping keys. Random splitting is diagnostic only.

Act-held-out, temporal-holdout and domain-held-out strategies remain explicitly infeasible in the current one-Act, one-effective-date, unlabelled pilot. Shared source artifacts are disclosed. The release is deterministic and versioned but cannot be called a frozen benchmark until complete pairs, materiality gold and expert-validated compliance scenarios exist.
