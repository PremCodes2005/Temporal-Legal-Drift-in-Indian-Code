# Automated Materiality Labeler Agreement — Silver Diagnostics

> This is agreement between two deterministic rule systems, not human inter-annotator agreement, legal validation, or classifier accuracy.

- Cases processed: 50
- Provisional higher-label outputs: 50
- Unresolved large disagreements: 0
- Exact rule-system agreement: 62.0%
- Cohen's kappa between algorithms: 0.474
- Proxy method-comparison accuracy (method A reference): 62.0%
- Proxy method-comparison macro F1: 0.599

## Provisional label distribution

| Label | Cases |
| --- | ---: |
| High | 16 |
| Low | 3 |
| Medium | 31 |

## Confusion matrix

Rows are cue-transition rules; columns are operation-delta rules.

| Cue rules \ Operation-delta | High | Medium | Low | None |
| --- | ---: | ---: | ---: | ---: |
| High | 16 | 0 | 0 | 0 |
| Medium | 0 | 12 | 0 | 0 |
| Low | 0 | 19 | 3 | 0 |
| None | 0 | 0 | 0 | 0 |

## Reading this result

The disagreement is substantial (38% of cases). The rules share a cue lexicon and source cases, so they are not statistically independent labelers. They tend to differ on whether an operative but weakly cued fragment is Low or Medium. The conservative tie-break stores provisional labels, but does not resolve legal ambiguity. `None` has no cases in this amendment-positive sample, so that category has no observed coverage. The displayed precision/recall/F1 treat one automated rule as a proxy reference and must not be cited as real-corpus materiality-classifier performance.

Source citations establish the origin of the quoted wording only. They do not prove that an automatically inferred legal effect is correct. Each record remains `NOT_GOLD`; taxonomy approval, independent legal review, and an independently validated benchmark are still outstanding.
