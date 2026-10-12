# Temporal graph protocol v3 (graph v4 onwards)

Supersedes nothing: `temporal_graph_protocol.v2.md` still governs graphs v2 and v3, which remain frozen and byte-reproducible. This protocol adds evidence-strength rules applied from graph **v4** (`STRICT_EVIDENCE_POLICY_VERSIONS`). Every status below is a machine check, not legal validation.

## Inputs

Graph v4 is built from:
- extraction v2.2;
- field-silver labels v2.2;
- `version_graph.v1.json`.

The checkpoint records the SHA-256 of each, and the Phase 3 gate re-verifies them.

## Exclusions (never a transition)

- Events with `source_text_unreliable` (scanned text layer, e.g. IT Amendment 2008) or `operand_contains_page_furniture`. They are forced to ABSTAIN and recorded as unresolved with that reason.
- Events with `layout_furniture_removed` whose after-fragment is not found in a consolidated snapshot of the target provision. These become `layout_cleaned_operand_not_corroborated`. Layout cleaning is trusted only when independent consolidated text agrees.
- Two or more candidate events from one amending Act on one provision (including split compound parts). These become `compound_or_repeated_transition_requires_ordered_reconstruction`, since order of application is not established.

## Short-fragment specificity

An after-fragment shorter than 15 normalized characters found in consolidated text is strong corroboration only if one of these holds:

- **INSERT:** the instruction's `after the words "…"` anchor appears immediately before the fragment in the consolidated text.
- **SUBSTITUTE / REPLACE:** the fragment occurs exactly once in that consolidated text, and the old wording does not occur there.

Otherwise the check `after_fragment_corroboration_specific` is false and the status is `MACHINE_SHORT_FRAGMENT_MATCH_ONLY`. The transition is then excluded from the fully machine-checked count and from consumer answers.

## Consumer contract (`graph-consumer-v1`, `versioning/consumer.py`)

The contract sits between the graph and RAG/risk.

**Refusal:** it refuses a graph whose bytes do not match its passed checkpoint, or whose version or schema it does not support.

**On a strongly corroborated dated transition** it returns `FRAGMENT_SUPPORTED` with:
- `version_scope = AMENDMENT_CONTROLLED_FRAGMENT` and `is_complete_consolidated_text = false`;
- `applicability_status = NOT_DETERMINED_REQUIRES_SCENARIO_FACTS_AND_REVIEW`;
- `legal_validation = UNVERIFIED`;
- source evidence (URL, SHA-256, page, line, exact text).

**Otherwise** it returns `UNRESOLVED` with `abstention_reasons`. This covers no dated transition, a weak or internal-only transition, and an unknown provision.

Commencement dates are Act-wide (`ACT_WIDE_COMMENCEMENT_NOT_SCENARIO_APPLICABILITY`). Scenario applicability, transitional and retrospective effect are decided only by the applicability resolver from approved facts.
