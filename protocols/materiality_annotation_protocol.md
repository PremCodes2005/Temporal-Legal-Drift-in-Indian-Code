# Materiality Annotation Workflow

The current materiality engine is a transparent **triage heuristic**, not a trained or validated classifier. Its rule output is advisory and must be checked against cited evidence.

The requested materiality Phase 4 is implemented in this repository alongside its existing Phase 4 temporal-applicability subsystem. The prior Phase 5 scaffold remains for benchmark integration. The materiality workflow creates exactly 50 unique fragment-level cases from Phase 3 transitions that have operation round-trip checks and an independently downloaded consolidated-text match. It stores both source anchors and never labels the cases automatically.

## Annotation lifecycle

1. Generate the open round with build-materiality-annotation-round.
2. Two annotators independently submit one record per pair, using the versioned guideline and source-grounded quotes. Keep each submission unchanged.
3. Calculate raw agreement, Cohen's kappa (when defined), per-annotator class counts, denominator, and confusion matrix.
4. An independent adjudicator supplies one evidence-quoted decision and rationale per pair.
5. Freeze the output as materiality_gold_v1 only when all 50 records have exactly two valid, independent annotations and an explicit adjudication.

The round is not gold. A separate automated path runs two deterministic rule labelers and a conservative rule adjudicator to produce a `materiality-silver-v1` artifact. Its labels and agreement are explicitly machine-generated diagnostics—not human annotation, legal adjudication, or ground truth. The automated agreement score must not be reported as legal accuracy. An insertion's before fragment is an explicitly empty state, not invented text. All cases are fragment-level and may lack complete historical provision context.

The first model implementation is a dependency-free experimental softmax model with a lexical-only feature setting and a combined lexical/operation/legal-cue setting. Training is rejected unless rows are adjudicated gold. Group-disjoint train/test evaluation reports precision, recall, F1, support, confusion matrix, and high-materiality false negatives. Majority, class-prior, operation and legal-cue baselines are available. An embedding model and LLM classifier are intentionally not selected or executed before the gold set and experiment configuration exist.

The automated labeler comparison reports raw method agreement, Cohen's kappa between the two algorithms, and a confusion matrix. These statistics measure only the implemented rules' consistency; they do not establish legal correctness. No real-corpus classifier F1 or legal agreement claim is reported until independently validated labels exist. A score from the app's current PDF comparison remains named materiality triage, with a compatibility field for existing clients; it is not a materiality classifier.
