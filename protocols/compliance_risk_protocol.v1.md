# Compliance risk baseline v1

This is the revised project's Phase 5 (risk), independent of the older Phase 5 annotation scaffolding. Implementation status is recorded under `reports/risk/` to preserve those earlier artifacts.

## Decision contract

Amendment and materiality metadata → applicable version → scenario scope and facts → obligation → consequence → operational risk.

Drift, edit similarity and model confidence are not risk inputs. Changing materiality alone cannot change a risk decision. Unknown materiality is retained but does not prevent evaluation of an otherwise supported obligation. Exposure is recorded with the scenario; no monetary risk estimate is inferred without a validated monetary model.

`ComplianceScenario` has scenario ID, organization type, industry, jurisdiction, structured facts, reference date, applicable provision, activity and exposure. Missing context is represented by null. A field omitted from the scenario schema is an input error. A missing legally relevant fact produces `INSUFFICIENT_EVIDENCE`, not a zero-risk answer.

The server selects a versioned obligation model by provision and explicitly supported reference date. Conflicting models, unresolved applicability and unmet applicability conditions require review. Temporal evidence is required in addition to obligation text. The current demonstration uses two specified dates and makes no claim about intervening or subsequent dates. The general resolver's unresolved legal determinations must not be upgraded by this layer.

Supported deterministic operations are deadline, requirement, prohibition and eligibility. Deadline arithmetic explicitly counts calendar days excluding the trigger date, with an inclusive due date. Other counting conventions require a new model. An absent completion fact is unknown; an explicit null completion date means not completed. Future completion dates and completion before the trigger require review. A pending obligation within seven days of its deadline has Low operational priority and `risk_flag=false`; it is not a detected breach.

## Levels and outputs

| Risk level | Operational meaning |
|---|---|
| High | Detected non-satisfaction with a severe consequence specified in the obligation model |
| Medium | Detected non-satisfaction with a material operational consequence specified in the model |
| Low | Detected non-satisfaction with a limited consequence, or an approaching pending deadline |
| None | No adverse consequence detected under the selected obligation and supplied facts |
| null | Risk cannot be determined; this is a workflow state rather than a fifth class |

Consequence severity is an explicit proposed operational policy; it is never copied from materiality. Urgency is IMMEDIATE for detected non-satisfaction, SOON for a pending deadline within seven days, ROUTINE for a later pending deadline, NONE for satisfaction, and UNKNOWN for unresolved cases. Every result includes the rule, version, evidence, reasoning, uncertainty and escalation status. Existing models are not expert validated and always retain that uncertainty. No criminal penalty or legal invalidity is inferred from a missing eligibility basis.

## Existing corpus and benchmark

The repository contains 13 evidence-linked empty scenario scaffolds and one separate authored Section 19 demonstration. The 13 retain their IDs, source pairs, source hashes and candidate versions in `data/risk/compliance_scenarios.v1.json`. Their engineering expectations are abstention because their facts and legal outcomes were never authored. Their expected law, obligation and legal consequence remain null, with explicit reasons. This is an abstention benchmark, not 13 substantive legal-risk gold cases.

The separate Section 19 example is evaluated at both original reference dates. It stipulates recognition, approval, notification, regulatory conditions and a notified electronic signature that is not a digital signature. The pre-amendment wording is an engineer's conditional reconstruction from the substitution footnote. The expected Medium priority before and None after are hypotheses under this model. These two examples are not independent validation and are not added to the 13-case count.

Synthetic deadline, requirement and prohibition cases exist only in tests. They check false positives, false negatives, boundary dates, missing facts, conflicting dates, evidence tampering and independence from materiality. Their success does not measure legal accuracy. Real-corpus false-positive/false-negative rates remain null until independently labelled positive and negative cases exist. Expert rationale remains null and expert validation remains NOT_PERFORMED.

## Reproduce and use

Run `PYTHONPATH=src .venv/bin/python -m temporal_legal_drift.cli build-risk-checkpoint` from the project directory. Identical reruns are accepted; changed artifacts at the same version are rejected. Input and artifact hashes bind the graph, the preserved Phase 4 records, original scenarios and raw PDF bytes.

The dashboard's Compliance risk tab loads `GET /api/risk/catalog` and submits a `ComplianceScenario` to `POST /api/risk/assess`. The API accepts no caller-supplied rules or scores. A JSON scenario can also be evaluated with `assess-risk --scenario <path>`. Rule/evidence or source changes require a new versioned release. The original datasets and graph are preserved.

## Checkpoint

Engineering completion requires strict input validation, reproducible output, source checksums, all 13 migrated cases, conditional demonstrations, connected API/UI, and false-positive/false-negative regression tests. The research checkpoint additionally requires independently justified substantive scenarios and expert validation; those requirements remain unfulfilled. Automation cannot substitute an agreement or a hash check for them.
