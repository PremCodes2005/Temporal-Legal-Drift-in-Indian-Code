# HTTP API contracts used by the dashboard (2026-10-12)

The field lists were read from live responses of this checkout. They are engineering contracts only; no field is a legal conclusion.

## `POST /api/rag/query`  body `{"query": str, "mode": "specific" | "generic", "scenario"?: {...}}`

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
