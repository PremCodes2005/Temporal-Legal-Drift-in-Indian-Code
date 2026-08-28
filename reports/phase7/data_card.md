# Technical Release Data Card

## Status

This is a Phase 7 pipeline dry run, not a frozen benchmark and not legal gold. It exists to validate schemas, identifiers, provenance checksums, grouping logic, split feasibility and leakage controls before expert-authored records exist.

## Inputs

- Evidence-linked amendment annotation tasks from the bounded India Code pilot.
- Scenario-authoring scaffolds derived only from internally corroborated amendment/date evidence.
- Phase 3 version graph and Phase 4 cross-source validation records.

## Exclusions

- No materiality label has been assigned.
- No compliance facts, questions, answers, consequences or expected-change labels have been authored.
- No historical before-version has been approved.
- No model output is included.

## Leakage policy

Exact and near-duplicate amendment instructions are grouped before feasible dry-run split assignment. Amendment-event and provision-lineage grouping are applied to their corresponding split strategies. Act, temporal and domain holdouts are reported infeasible rather than simulated from inadequate coverage.

## Permitted claims

The release may support claims about deterministic pipeline execution and disclosed leakage diagnostics only. It must not support claims about legal correctness, materiality performance, compliance reasoning, temporal drift or benchmark coverage.
