# Phase C checkpoint — graph v4, evidence-strength policy, consumer interface

Date: 2026-10-12. Base `74aef24` (release v0.3.0). Engineering results only; **legal/research gate UNVERIFIED**.

## Graph v3 → v4

| | v3 (from v2.1) | v4 (`fcff6fbc…` from v2.2 + silver v2.2) |
| --- | --- | --- |
| Legal sources / acts / provisions | 100 / 63 / 5,657 | 100 / 63 / 5,657 |
| Amendment & commencement events | 864 / 864 | 1,150 / 1,150 |
| Provision versions | 5,827 (5,657 + 2×85) | 5,929 (5,657 + 2×136) |
| Transitions | 85 | 136 |
| — CROSS_SOURCE_CORROBORATED | 56 | 86 |
| — SHORT_FRAGMENT_MATCH_ONLY | — | 6 |
| — INTERNAL_CHECKS_ONLY | 29 | 44 |
| Fully machine-checked | 55 | 86 |
| Dated (all fully checked) | 4 | 5 |
| Unresolved transitions | 779 | 1,014 |
| Transitions from compound parts / layout-cleaned events | — | 29 / 2 |
| Source-fidelity-flagged events (never transitions) | 49 | 37 (35 IT 2008 + 2 page furniture) |
| Human-validated | 0 | 0 |

Reconciliation: 136 + 1,014 = 1,150 events.

v4 unresolved reasons:

| Reason | Count |
| --- | --- |
| event or target not silver-resolved | 771 |
| wording missing | 691 |
| operation not reconstructable | 234 |
| compound/repeated on one provision | 218 |
| `source_text_unreliable` | 35 |
| `layout_cleaned_operand_not_corroborated` | 3 |
| `operand_contains_page_furniture` | 2 |

Silver v2.2 (`6e0a51d6…`) auto-accepts 502/1,150 fields-complete events; this is machine agreement, not accuracy.

The v4 graph invariants pass: unique IDs, hashes, source links, target alignment, version continuity and no cycles. Graph v3 still rebuilds byte-identically under the new code. The v4 build was re-run and accepted as identical.

## Policies (protocol `protocols/temporal_graph_protocol.v3.md`)

- **Short fragments.** An after-fragment under 15 characters must pass a context check: the anchor sits next to the fragment for INSERT; for SUBSTITUTE the fragment occurs once and the old wording is gone. Six matches fail the check and are downgraded: "section 164", "ten years" ×2, "filing", "or culture", "officers". The checkpoint's corroboration count excludes them (86).
- **Layout-cleaned operands.** These become transitions only with consolidated-text support: 2 do, 3 abstain.
- **OCR-uncertain and page-furniture operands.** These never become transitions. The Phase 3 gate re-checks all three rules against the graph file (`v4_weak_or_unreliable_evidence_never_strong_transition`).
- **A first v4 checkpoint mis-counted corroboration** (92, including the six weak matches). It was fixed and rebuilt before commit; the graph bytes were unchanged.

## Temporal applicability

Five tests were added on the existing resolver; all passed without code changes:

| Case | Resolver result |
| --- | --- |
| Assent-only | `unresolved_escalate`, reason `publication_or_assent_evidence_does_not_establish_applicability` |
| Deferred commencement | `not_yet_effective` before the date, the new version from the date |
| Transitional provision | escalates for explicit adjudication |
| Retrospective effect | the evidenced effective date governs, not assent |
| Multiple active versions without a supersession path | escalates |

Publication-only, partial-commencement, conflicting-date and uncertain-evidence tests already existed.

Point-in-time queries that abstain return the provision's unresolved transitions with source anchors. A returned fragment carries `AMENDMENT_CONTROLLED_FRAGMENT` and a scope warning.

## Consumer interface `graph-consumer-v1`

`versioning/consumer.py` is the only supported way for RAG/risk to read the temporal graph.
- **Refusal:** it refuses a graph whose bytes do not match its passed checkpoint, or an unsupported version (v2 refused).
- **What a response carries:** the graph version and hash, version scope, `is_complete_consolidated_text: false`, `applicability_status: NOT_DETERMINED_REQUIRES_SCENARIO_FACTS_AND_REVIEW`, and `legal_validation: UNVERIFIED`.
- **When it abstains:** it answers `UNRESOLVED` with reasons unless a dated, strongly corroborated transition exists.

**Consumers are not migrated yet.** RAG still indexes `version_graph.v1` and risk still uses its obligation registry. Migration is planned with integration tests in Phases E and F.

## Gates

- Engineering:
  - 133 tests ran.
  - `validate-contract` exit 0.
  - `check-gates`: Phases 0–10 pass, including the v4 checks; Phase 11 passes after release v0.4.0.
- Legal/research: **UNVERIFIED**.

## Limits

- Only 5 transitions are dated, because commencement is extracted only from an unambiguous Act-wide clause. Partial, notified and retrospective commencement are not extracted from the corpus.
- 218 same-provision candidates need ordered reconstruction.
