# Phase 5 — compliance risk implementation

The deterministic risk engine, strict scenario/output contracts, versioned evidence registry, CLI, HTTP API and dashboard are implemented. Risk uses applicable obligations, scenario facts and consequence severity. Neither drift scores nor the materiality label determine risk. Incomplete applicability, evidence or facts produce an unresolved result with escalation.

Phase 4 was checked first: its 35 focused tests and then all 93 existing tests passed. No additional engineering error was reproduced. Its outstanding extraction reviews and absent independent legal validation remain recorded in `phase4_preflight.v1.json`.

## Deliverables

- `src/temporal_legal_drift/risk/`: models, deterministic engine, immutable artifact builder and service.
- `schemas/risk/`: scenario and output contracts.
- `data/risk/obligation_registry.v1.json`: two explicit conditional Section 19 models with source fingerprints and evidence.
- `data/risk/compliance_scenarios.v1.json`: all 13 original source templates preserved as structured abstention cases, plus two separate pre/post demonstration inputs.
- `experiments/risk/baseline_results.v1.json`: deterministic outcomes and expected-behavior comparisons, with legal performance metrics left null.
- `protocols/compliance_risk_protocol.v1.md`: risk definitions, date arithmetic, uncertainty, provenance and usage.
- `GET /api/risk/catalog`, `POST /api/risk/assess`, `build-risk-checkpoint` and `assess-risk --scenario <json>`.
- Frontend Compliance risk tab with editable scenario context/facts and evidence-backed results.

## Checkpoint accounting

| Requirement | State |
|---|---|
| 13 scenarios in structured format | Complete, preserving source IDs and evidence |
| Expected engineering behavior | Defined and evaluated: abstain on incomplete scenarios |
| Substantive expected legal outcomes for all 13 | Incomplete; original templates have no authored facts or outcomes |
| Two conditional Section 19 executions | Implemented and explicitly labelled as assumptions |
| Deterministic baseline and risk definitions | Implemented |
| Uncertainty and escalation | Implemented; unknown risk is null rather than the None class |
| False-positive/false-negative and boundary tests | Implemented with explicitly synthetic unit-test fixtures |
| Expert validation | NOT PERFORMED |
| Legal accuracy and research checkpoint | Unverified / incomplete |

The original count of 13 did not represent 13 completed demonstrations: repository inspection found 13 empty scaffolds and one separate authored Section 19 demo. The new conversion does not turn these into legal ground truth. Test expectations were specified independently of the engine's outputs; the runtime receives no expected outcomes. Passing these tests establishes the implemented decision contract, not legal correctness.

Next, author scenario facts and obligation models for the 13 source cases, establish each applicable historical version, and obtain independent adjudication where possible. Until then, they remain useful for testing abstention and evidence preservation, but cannot establish false-positive/false-negative rates on Indian legal risk. The wider corpus is not yet covered by risk models.
