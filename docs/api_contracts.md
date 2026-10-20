# HTTP API contracts used by the dashboard (2026-10-12)

The field lists were read from live responses of this checkout. They are engineering contracts only; no field is a legal conclusion.

## `POST /api/rag/query`  body `{"query": str, "mode": "specific" | "generic", "scenario"?: {...}}`

**rag-answer-v5** (`schema_version` 5.0.0; schema `schemas/rag/rag_answer.v5.schema.json`; ADR 0017) adds the following. Every v4 field is retained; stored v4 records stay readable at `/api/analyses/<id>`.

- **`fingerprint.version`:** `legal-change-fingerprint-v1.2`.
- **`fingerprint.reading`:** `[{kind: wording | rule | disagreement | outcome, text, field?, evidence_ids}]`.
- **`rule_drift.details.fields[]`:** adds `label` and `why`. The key `monetary_threshold` is now `threshold`, with values `amount: …` or `count: …`.
- **`rule_drift.details`:** `structural_changes` (list items or Explanations); `unscored_reason` is `CROSS_REFERENCE_ONLY`, `TERM_SUBSTITUTED` or `UNSUPPORTED_RULE_FIELD`. `calculation` is null when the change is not scored.
- **`determinations-v4`:** materiality `details.scored_operands` and `input_normalisation` (triage-input-v2).
- **`answer-composition-v2`:** the `effect` section is present only when facts were applied; `what_changed` is titled "Key change".
- **Browser addresses:** `#analysis/<id>/<answer|evidence|drift|calculation|scenario|sources>`. `#drift` and `#calculation` open the current analysis. v4 `…/scores` links open `calculation`.

**rag-answer-v4** (`schema_version` 4.0.0; schema `schemas/rag/rag_answer.v4.schema.json`; ADR 0016) adds the following. Every v3, v2 and v1 field is retained.

- **`analysis_id`:** `an_` plus 24 hex characters. It is a hash of the contract, method versions, query, mode, applied scenario, generation method, index identity, graph hash and active release. The response is stored once under this ID.
- **`limit`** on every determination and fingerprint component: `{kind: evidence | facts | method | not_applicable, reason, action: {type: verify_source | add_facts | queue_review | none, label}}`.
- **`scenario_request`:** `{fields[{key, label, kind, options, unlocks[], group: core | risk, value, source: question | form | null}], facts_in_use, blocked_by_evidence[], explanation}`. It holds only the facts that unlock a component whose limit kind is `facts`.
- **`determinations-v3`:** `materiality.details.source` is `FROZEN_SILVER_SET` or `ON_THE_FLY_MACHINE_TRIAGE` (with `rule_a`, `rule_b` and `review_status`).
- **`legal-change-fingerprint-v1.1`:** an unsupported rule change gives `rule_drift.value = null`, `label "Not scored"` and `details.unscored_reason`. Registry outcome rows may carry `assumes`.

## `GET /api/analyses/<analysis_id>`

Returns the stored rag-answer-v4 response, unchanged. An ID that does not match `an_[0-9a-f]{24}` gives 400; an unknown ID gives 404. Shareable browser address: `#analysis/<id>/<answer|evidence|scores|scenario|sources>`.

**rag-answer-v3** (`schema_version` 3.0.0; schema `schemas/rag/rag_answer.v3.schema.json`; ADR 0015) adds the following. Every v2 and v1 field is retained.

- **`fingerprint`:** `{version: "legal-change-fingerprint-v1", wording_drift, rule_drift, outcome_drift, note}`.
  - **Each component:** `{state, value, label, summary, reason, next_action, method, evidence_ids, details, needs, uncertainty, legal_validation}`.
  - **`value`:** wording 0–100%; rule 0–100 (weighted); outcome 100 = a supported answer flip, 0 = none. It is `null` whenever the component is not determined, never 0.
  - **`wording_drift.details`:** `before_clause`, `after_clause` (offsets refer to these), `spans[{operation: added | removed | substituted, before_text, after_text, before_offsets, after_offsets}]`, `inputs`, `weights`, `formula`, `calculation`, `flag` (IDENTICAL or FORMATTING_ONLY), and `legacy_trace`.
  - **`rule_drift.details`:** `fields[{field, weight, operation, status, before, after, before_spans, after_spans, contribution}]`, `calculation`, `lower_bound`, `llm_proposal`, `operative_sentences`.
  - **`outcome_drift.details`:** `evaluated[{field, decisive_fact, before_answer, after_answer, changed}]`, `not_evaluable`, `controlled_scenarios{values_tested, flips, evaluated, percent}`, `compat_percent`, `applies`.
- **`determinations-v2`:** adds `applicability`, with `details.publication`, `details.commencement` and `details.scenario_applicability` kept separate.
  - `textual_drift` is a deprecated alias of `fingerprint.wording_drift`.
  - For a scenario, `answer_change` mirrors outcome drift.
- **`metrics.legacy_diagnostic`:** marks `overall_drift_percent` and `conceptual_drift_percent` (drift-metrics-v3) as legacy diagnostics; their values are unchanged.
- **Scenario facts used by outcome drift:** `elapsed_days`, `elapsed_months`, `amount`, `exception_conditions_met`, `contravention`, `within_scope`, plus the registry's own facts.

**rag-answer-v2** (`schema_version` 2.0.0; schema `schemas/rag/rag_answer.v2.schema.json`; ADR 0014). Every v1 field below is retained, so v1 consumers keep working.

- **Optional `scenario`:** `reference_date` (YYYY-MM-DD), `organization_type`, `industry`, `jurisdiction`, `activity` (short text), and `facts` (at most 30 snake_case names with scalar values). Unknown fields are rejected.
- **Added top-level fields:**
  - `question_frame`: the resolved Act, amending Act, sections, question type and unresolved Act names;
  - `scenario`: the validated echo;
  - `evidence`: a list of `{evidence_id, role, entry_id, act_name, text, page, line, verbatim, scope, source_sha256, text_sha256, pdf_url, official_url, text_reliability}`;
  - `version_evidence`: support class, reason code, transition or footnote details, candidates and suggested sections;
  - `determinations`: `{version: "determinations-v1", textual_drift, materiality, answer_change, risk}`.
- **Each determination:** `{state, label, summary, reason, method, evidence_ids, details, needs, review_status, legal_validation: "UNVERIFIED"}`.
  - `state` is one of DETERMINED, PROVISIONAL, CONDITIONAL, NEEDS_FACTS, INSUFFICIENT_EVIDENCE or OUT_OF_SCOPE.
  - `label` is null unless the state is DETERMINED, PROVISIONAL or CONDITIONAL.
  - `needs` lists the minimum facts required: `{key, label, kind: date | choice | boolean | text, options?}`.
- **`answer` additions:** `direct_answer`, then `sections` as `[{id: before | after | what_changed | effect | key_points | candidates | suggestions, title, label?, text, evidence_ids, kind: evidence | derived | inference | limitation}]`, plus `answer_limitations`.
  - `generation_method` is `grounded_composition` for version questions, which never use a model.
- **`comparison`:** `comparison-record-v2` for version questions. It adds `support_reason` and `relation_verification`, and its classes include RELATION_MISMATCH, WEAK_TRANSITION_ONLY and NO_SUPPORTED_VERSION; `before`/`after` are null unless versions are supported. General questions keep comparison-record-v1.

### rag-answer-v1 fields (retained)

Top level: `schema_version, query, intent, mode, answer, citations, comparison, metrics, retrieval, verification, source_fidelity_warnings, source_guidance, limitations, repository`.

`comparison` is **comparison-record-v1**:
- **Identity and contract:** `contract_version`, `scoring_contract_version`, `query_id`.
- **Pairing:** `support_class`, one of `GRAPH_TRANSITION_FRAGMENTS`, `CONSOLIDATED_FOOTNOTE_RECONSTRUCTION`, `UNALIGNED_EXCERPTS`, `AMBIGUOUS_CANDIDATES` or `NOT_A_COMPARISON`.
- **Amendment:** `operation`, `provision_path`, `amendment_event_id`, `graph_transition_id`, `competing_transition_ids`.
- **Dates:** `requested_date`, `supported_effective_date`.
- **Evidence and abstention:** `changed_spans`, `abstention_reasons`, `reliability`, `question_relevance`.
- **Statuses:** `applicability_status`, `materiality_status`, `consequence_status`, `legal_validation`. These are statuses, never conclusions.
- **`before` / `after`:**
  - text and role: `role`, `compared_text`, `span_basis` (`derived_text_not_a_verbatim_source_span` for reconstructions);
  - source: `act_name`, `entry_id`, `source_id`, `source_sha256`, `document_version`, `source_url`;
  - location: `page`, `line`, `source_anchor`, `chunk_id`, `text_offset`, `local_pdf_url` (`/corpus/<file>.pdf#page=N`);
  - `page_region_highlight` (always unavailable: no verified PDF coordinates).

`metrics` is **drift-metrics-v3** (see `docs/methodology/drift_score.v3.md`). It is `null` when no aligned pair exists, and unavailable components are `null`, never 0.
- **Scores:** `semantic_drift_percent`, `lexical_drift_percent`, `conceptual_drift_percent`, `overall_drift_percent`, `evidence_alignment_quality_percent`.
- **Calculation:** `weights`, `calculation_trace`, `score_basis`, `compared_text_sha256`.
- **Agreement and availability:** `component_disagreement`, `component_spread_percent`, `availability`, `unavailable_reasons`.
- **Context:** `reliability`, `question_relevance`, `levels`, `level_thresholds`.
- **Deprecated:** `alignment_accuracy_percent` (listed in `deprecated_fields`).

## `GET /api/sources/health`

Top level: `sources, alerts, document_states, failed_documents, review_queue_pending, time_base, active_binding, live_query_lookup, coverage_claim`. Each entry in `alerts` is `{source_key, code: SCHEDULER_MISSED_RUN | INGESTION_STALE, detail}`. `commencement_pending_review` counts commencement records awaiting a qualified review.

`source_fidelity_warnings` in `/api/rag/query` may include `{"warning": "source text partly withheld"}`: lines on the cited page were withheld by `text-quality-v1`.

Each entry in `sources` has: `source_key` (`india_code` or `egazette`), `last_attempt_at`, `last_success_at`, `last_status`, `next_eligible_at`, `lag_hours`, `scheduled_ingestion_healthy`. Times are UTC.

## Additions (2026-10-20, ADR 0022)

### `GET /api/sources/notifications` (source-notifications-v1)

A read-only view of the monitoring ledger. It makes no network request and does not affect the 24-hour source-check gate.

- **Top level:** `version, generated_at, scope, note, legal_effect_claimed: false, items, total, listed, listed_total, sources`.
- **`items`:** one per official record that is in the review queue or whose download failed, newest first by first discovery. Each is `{id, title, source_key, source, published, discovered_at, last_checked_at, official_url, status, status_label, queue_id, candidate_events, candidate_targets, legal_effect_claimed: false}`.
  - `discovered_at` is the first observation of the record; `last_checked_at` is the latest.
  - `official_url` is null unless it is `https` on that source's official host.
  - `status` is one of AWAITING_REVIEW, REVISED_AWAITING_REVIEW, CANDIDATE_UNVERIFIED, DOWNLOAD_FAILED, or a review-ledger state (REVIEW_ACKNOWLEDGED, ESCALATED_FOR_QUALIFIED_REVIEW, CHANGES_REQUESTED, OPINION_RECORDED). No status means a verified or commenced change to law; the review ledger has no action that produces one.
- **`listed`:** records the source listed but that were never downloaded (status LISTED_NOT_DOWNLOADED). They are kept apart so they cannot bury documents under review.
- **`sources`:** `{source_key, source, state: OK | STALE | FAILED | NEVER_SUCCEEDED, detail, last_success_at, last_attempt_at, next_eligible_at}`. STALE means no success for more than 48 hours.

### `GET /api/methods/tlds`

The combined-score method read from `configs/metrics/tlds.v1.json` and `reports/fingerprint/tlds_heldout.v1.json`:
- `version`, `formula`, `weights`, `weights_status`;
- `components` (per component: `measures`, `why_this_weight`);
- `bands`, `bands_note`, `missing`, `disagreement_spread`;
- `sensitivity` (the four held-out weightings, with band counts, "material legal effect but Low" counts and Spearman order agreement).

### `fingerprint.tlds` (tlds-v1.1)

Same formula, weights and values as tlds-v1. It adds:
- **`contributions`:** `{component: 100 × weight × value}`, or null for a missing component;
- **`disagreement`:** `{spread, highest, lowest, strong, rule}`, where `strong` means the components' values differ by 0.6 or more.

Stored tlds-v1 analyses are unchanged and still open; the page says their points were not recorded.

### Frontend address

`#comparison/<analysis_id>` is the clause comparison of a stored analysis; plain `#comparison` reopens the last one shown.

## Additions (2026-10-20, ADR 0023)

- **`GET /api/sources/notifications` is now `source-notifications-v2`.** A record is one downloaded version, `key = "<official_id>:<sha256>"`, so a repeat check is never a new record and a revised PDF is. Identical bytes under several official ids are one record (`same_document_ids`). Its `discovered_at` is the first observation of that version.
  - **Lists:** `latest` holds the newest five; `older` holds the rest. `items` (`latest` + `older`) is kept for v1 readers, and `failed` lists download failures.
  - **Record fields:** each record adds `key`, `sha256`, `version`, `category` (`NEW_DOCUMENT` | `POSSIBLE_AMENDMENT`) and `category_label`.
  - **`categories`:** `[{category, label, count, note}]` for `NEW_DOCUMENT`, `POSSIBLE_AMENDMENT` and `VERIFIED_AMENDMENT`. The last is always 0, because the review ledger has no verifying action.
- **`GET /api/methods/rule-drift`:** the rule-drift field weights from `configs/metrics/rule_drift.v1.2.json`, with `fields` (`field`, `label`, `weight`, `why`), `rationale` (`status`, `total`, `tiers`, `counting`, `not_the_combined_weights`) and `sensitivity` (from `reports/fingerprint/rule_weights_sensitivity.v1.json`). It is separate from `GET /api/methods/tlds`.
- **Retired screen:** the routes behind the Case trace & review screen (`/api/runs*`, `/api/reviewers`, `/api/reviews`) remain available but are no longer linked from the interface.
