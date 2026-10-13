# Definitive Research and Implementation Plan

## Temporal Legal Drift in the Indian Code

**Status:** Research specification and implementation roadmap; engineering prototype exists, but legal/research validation is pending.

**Target:** Lab-validated research prototype (TRL 4 is a target, not a current claim).

**Core orientation:** Temporal legal reasoning and compliance-drift evaluation over versioned Indian law.

**Planning baseline:** Clean `main` checkout at `af16acd71d511c04694d442d103caf5e3bf3f9f2`, inspected 2026-10-12. The active release pointer names v0.6.0. This document edit has not rerun tests, gates, live sources, the model, or remote CI. Recheck Git state and the evidence artifacts before implementation.

**Observed engineering, not legal gold:** The repository contains the local 100-PDF pilot corpus, immutable/versioned acquisition records, parsing and amendment extraction, temporal graph v4 and a bounded graph consumer, a conservative applicability resolver, 50 frozen **machine-silver** materiality cases, a conditional compliance-risk engine, explanation-contract and case-orchestration code, an append-only engineering-review ledger, a Python API, and a React/Vite RAG and case-review interface. The source code has a one-shot ingestion scheduler and a live India Code *query-time* lookup; it does not establish a persistent 24-hour Gazette/India Code harvesting service. The current drift utility exposes component scores and weighted RMS, but these are retrieved-text diagnostics, not validated legal accuracy. See `docs/claims_evidence_matrix.md`, `reports/`, and the code for the precise limits of each artifact.

**Open research and product gaps:** No comprehensive India Code or Gazette history, independently validated provision transitions, approved applicability facts for the real corpus, gold materiality labels, substantive expert-gold scenarios, frozen scientific benchmark, legal model-performance estimate, or independent legal validation has been demonstrated. Query-specific before/after highlighting against exact source coordinates and a persistent incremental official-source monitor are **planned**, not implemented. The optional read-only `evaluation_agent/` audits artifacts; it is not the source monitor described in this plan. A passed engineering gate does not certify legal correctness, patentability, or TRL 4.

**How to read this file:** §0 is the current engineering contract and next sprint. §§1–27 preserve the detailed scientific research specification. Their Phase 0–12 names are research phases; §0 and `docs/implementation-plan.md` use the newer engineering Phase 0–10 mapping. Dated historical figures elsewhere are not live status.

## 0. Revision 2026-10-12 (rev 3): canonical architecture and next sprint

**Role of the two plans.** This file is the canonical research contract **and the acceptance specification for the next sprint**. [docs/implementation-plan.md](docs/implementation-plan.md) is the earlier Phase 0–10 execution map; its stated v0.5.0 baseline and Phase 6–8 status predate the inspected checkout and must be refreshed by the implementer before treating it as live status. Evidence artifacts, code, and [docs/verification.md](docs/verification.md) take precedence over either document's status prose. Dated counts elsewhere in this file are audit findings, not live status.

- **Planning Git baseline:** `af16acd` (active release pointer v0.6.0); freeze the actual implementation start commit again before changing code.
- **Evidence:** per-phase checkpoint reports under `reports/`, and `docs/verification.md`.

### 0.1 Target workflow

authoritative Indian legal source → immutable ingestion and provenance → reliable text extraction → amendment event and affected provision → temporal provision graph → scenario-specific temporal applicability → materiality assessment → applicable obligation and compliance consequence → conditional compliance-risk assessment → evidence-grounded explanation → human review or escalation → audit trail and dashboard → controlled benchmark evaluation.

Every substantive output must trace back to the following. A stage that cannot supply them must abstain rather than guess.
- the source document, source SHA-256, and page/locator with evidence span;
- the amendment event and the provision version;
- the applicable date;
- the transformation version.

### 0.2 Separate concepts (no shortcuts between them)

| Concept | Question it answers | May not be inferred from |
| --- | --- | --- |
| Textual / vector drift | How did retrieved text change? | — |
| Materiality | How legally significant may the amendment be? | drift magnitude |
| Temporal applicability | Which version governs this scenario and date? | publication date, newest PDF |
| Compliance consequence | What does that version imply for these facts? | materiality class |
| Operational risk | Conditional obligation × consequence × urgency × uncertainty | drift, materiality alone |

"High drift → high risk" and "High materiality → changed answer" are prohibited. Unknown risk is `null`, not "None".

### 0.3 Phases and completion criteria

The implementation phases below replace the overlapping numbering used in earlier reports. Research phases 0–12 in §19 remain the scientific design.

| Phase | Completion criterion (engineering) | Research/legal criterion |
| --- | --- | --- |
| 0 Baseline & reproducibility | A clean checkout restores declared inputs and passes tests and gates; overwrite and tamper refusal tested | — |
| 1 Source ingestion | Duplicate bytes reuse an artifact; changed bytes create a version; failures are logged; new documents are queued for review | Source sufficiency approved by a reviewer |
| 2 Fidelity & extraction | Every accepted event is traceable to reliable text; every failure has a reason; no coverage from guessing | Hand-checked extraction fixtures |
| 3 Temporal graph | Counts, hashes, links, dates and supersession validate; unsupported versions abstain | Independently validated transitions |
| 4 Materiality | Reproducible, evidence-linked triage with abstention; silver agreement reported only as such | Independent gold labels; then precision/recall/F1 |
| 5 Compliance risk | Deterministic and evidence-linked; unknown is null | Independently adjudicated outcomes |
| 6 Explainable LLM | Structured, schema-valid, evidence-bounded explanations; fallback explicit; raw and normalized output kept | Expert explanation review |
| 7 Orchestration | One traced run from source to review state through versioned interfaces; unreliable sources end unresolved | — |
| 8 Dashboard & review | Representative tasks on desktop and mobile; API and UI states reconcile; append-only reviewer audit; no implied approval | Qualified reviewer identity |
| 9 Benchmark | Frozen manifests, split and leakage audit, data card, metric definitions and claim-evidence matrix reproduce | Gold reference outcomes for false stability/instability |
| 10 Final reproducibility | Every claimed engineering result reproduces in a clean environment; docs agree | Independent validation actually performed |

**Mapping from earlier numbering:**
- Implementation Phase 2 = extraction.
- Phase 3 = graph.
- Phase 4 = applicability, now part of this plan's Phase 3.
- Phases 5–7 = materiality, scenarios and the release dry run (this plan's Phases 4, 5 and 9).
- The "Phase A–G" labels of the 2026-10-12 repair run map to Phases 0, 2, 3, 4, 5, 6/8 and 9.

### 0.4 Claims boundary

An implemented architecture is a technical demonstration, not a patentability opinion. Engineering gates, machine agreement, short-fragment matches, LLM consensus and citation presence are not legal validation. Without a qualified independent reviewer the legal/research gate stays **UNVERIFIED**.

### 0.5 Change log

- **rev 3 (2026-10-12).** Rebased the planning status on `af16acd`/v0.6.0 and specified the next three deliverables: incremental 24-hour official-source monitoring, transparent drift methodology, and query-grounded clause comparison with source highlighting. These are prospective gates, not implementation claims. The old scientific Phase 0–12 sequence remains below.
- **rev 2 (2026-10-12).**
  - Adopted the Phase 0–10 architecture target supplied by the project lead.
  - Reconciled it with verified repository state: extraction v2.2, graph v4, release v0.5.0, CI green. Historical figures in that proposal (56/58 tests, 76 events, zero labels) are superseded.
  - Removed contradictory phase numbering by the mapping above.
  - The supplied proposal's full text was not attached and is not stored.
- **rev 1 (2026-10-12, `bd43b4d`).** Added the compliance-risk deliverable and integration-boundary notes.

### 0.6 Next-sprint contract: three integrated deliverables

This sprint is **required engineering work** following the current prototype. It does not replace the independent legal-validation and benchmark gates in §§19–26. Implement it as small, versioned extensions to the existing ingestion, versioning, RAG, API and React components; keep frozen releases and datasets immutable. A periodic *source-acquisition job* is required here. The autonomous legal-conclusion agent of research Phase 12 remains optional.

| Deliverable | User-visible result | Non-negotiable boundary |
| --- | --- | --- |
| A. Official-source monitoring | New or revised Gazette/India Code records are discovered on a 24-hour cadence and enter the evidence/review pipeline without reprocessing unchanged bytes. | A new publication is not automatically an applicable amendment; no claim of complete official coverage. |
| B. Explainable drift methodology | Each supported comparison shows the inputs, component calculations, aggregation, disagreement and uncertainty behind its score. | A drift percentage is not legal materiality, compliance risk, answer accuracy or a probability. |
| C. Query-specific clause comparison | The question selects relevant, correctly related before/after clauses; the interface highlights exact cited spans and explains the change. | Do not label an amending instruction and a current consolidation as historical pre/post versions without a supported transition. |

**Integrated user journey:** ask a question and, where needed, specify a date and scenario → identify the legal instrument and target provision → retrieve source candidates → verify source integrity, relationship and temporal support → align the relevant clause or abstain → generate an evidence-bounded answer → calculate available drift diagnostics → display before/after excerpts, source links and review state → record a reproducible run. If the question is ordinary statutory QA with no supported pair, answer from supported evidence and mark comparison metrics unavailable.

**Baseline vs target:** `ingestion/scheduler.py` currently runs once only when invoked; `rag/indiacode.py` currently looks up live current records at query time; `rag/metrics.py` currently computes 40/30/30 weighted-RMS drift using feature-hash vectors, lexical overlap and either legal-cue proxy or model output; `frontend/src/App.jsx` shows excerpts and calculation traces. None of these facts proves automated 24-hour discovery, semantic embeddings, calibrated scores, complete clause alignment or PDF-coordinate highlighting. Preserve these interfaces where sound; version changed contracts.

### 0.7 Deliverable A — official-source monitoring and incremental ingestion

**Source-access gate.** Before writing a connector, document the actual official discovery/download mechanism for each source: India Code and the Gazette portal. Verify permissible access, metadata fields, pagination, redirects, authentication, rate limits, robots/terms where relevant, stable identifiers and whether an API is documented or merely observed. Do not invent an endpoint or bypass access controls. If a source offers no reliable lawful machine interface, implement a bounded manual-import or notification-only adapter and mark that source `ACCESS_LIMITED`; do not claim live synchronization.

**Source registry and state model.** Maintain a versioned registry keyed by authority and source collection. Each discovered record must retain official ID (when available), canonical URL, title, source type, jurisdiction, instrument/target Act if stated, publication/assent/commencement values **as separate unapproved facts**, discovery time, retrieval time, response metadata, byte SHA-256, MIME type, immutable local artifact path, source-text reliability flags and processing state. Permit missing fields explicitly. Source identity and byte identity are separate: the same bytes at two URLs are one content artifact with two source observations; changed bytes for one official ID create a new source version, never an overwrite. Cross-source equivalence requires an explicit relation supported by evidence, not a title match alone.

**24-hour schedule.** Persist `last_attempt_at`, `last_success_at`, `next_eligible_at`, cursor/checkpoint, lease owner and run ID per source. The ordinary scheduler must make **at most one automatic discovery attempt per source in each rolling 24-hour window**; restart and multiple workers must not trigger duplicate attempts. Define UTC as the stored time base and expose local display time separately. A failed attempt is logged and becomes eligible at the next scheduled window; manual retry is explicitly marked and audited. Backfill is a separate bounded command, never disguised as the daily job. The selected host/scheduler, time zone, health check and deployment responsibility must be specified in the implementation record; an in-process daemon tied to a developer laptop is not an operational guarantee.

**Incremental processing contract.** Discovery → download to temporary storage with size/type/timeout limits → SHA-256 and integrity check → immutable artifact write → compare official identity, URL and bytes against prior observations → enqueue only new or revised content → parse and assess text fidelity → extract amendment candidates → update graph or unresolved queue → rebuild/update retrieval index under an atomic version binding → produce a run manifest and human-review task. Reuse already successful stage outputs by content hash **plus parser, extractor, graph and index configuration versions**; changed code/configuration is a legitimate reprocessing reason. An unchanged download may update `last_seen_at` without rerunning extraction, graph construction, index building or model evaluation. A changed file must retain both versions and a revision relationship. A stage failure must leave a resumable state and cannot publish a partial graph/index as current.

**Compatibility and legal safety.** A candidate graph and index are built off to the side, reconciled against source hashes and schema versions, then activated together; never serve graph vN with index vN−1. New documents enter review before legal-effect claims. Publication is not commencement; applicability must remain unresolved unless the required temporal facts and legal rules are supported. No fresh live record silently alters frozen benchmark results or prior releases.

**Observable outputs:** registry snapshot; discovery and download logs; immutable source/revision manifests; failure/retry log; review queue; run/stage manifest; corpus/graph/index binding; dashboard source-health indicator with last attempted/succeeded time, lag, queued, failed, reviewed and access-limited counts. Status should distinguish “live query available” from “scheduled ingestion healthy.”

### 0.8 Deliverable B — drift score specification and evaluation

**Unit of analysis:** a verified, query-relevant, aligned provision/clause pair with source anchors. Do not score unrelated documents or whole Acts merely because retrieval returned them together. Record the exact canonicalized text used, query, selected IDs, source hashes, graph transition (if any), reference date, extraction quality and model/configuration versions. For multiple relevant clauses, show per-clause metrics and a clearly declared aggregation policy; do not mix scores from unsupported pairs.

**Component meanings and current baseline:**

| Component | Current implementation | Sprint decision and check |
| --- | --- | --- |
| Lexical/textual movement | Token-set Jaccard and token-sequence similarity, combined as `100 × [1 − (0.55J + 0.45S)]`. | Keep as a baseline; test punctuation, numbering, OCR noise, long insertions and short fragments. Show changed tokens/spans. |
| Vector movement | Cosine distance over deterministic feature-hash vectors, falling back to Jaccard in the utility if no vectors are provided. | Call this **feature-vector drift**, not pretrained semantic understanding. A true embedding method is optional and must name its model/version and be benchmarked separately. |
| Conceptual/legal-cue movement | Deterministic obligation/permission/prohibition/penalty/scope/number proxy, or a bounded LLM-provided score when available. | Show which method ran and the precise cited cues. LLM judgment must be schema-validated, evidence-bound, reproducible/configured at low variance and able to abstain; it is not legal ground truth. |
| Overall movement | `sqrt(0.40V² + 0.30L² + 0.30C²)`; component spread is also exposed. | Preserve as the **versioned baseline formula** until sensitivity/robustness checks justify different weights. Publish inputs, weights, squared contributions and result. Opposing 0/100 components must be displayed as disagreement, not interpreted as moderate legal change. |
| Evidence/alignment quality | A heuristic using retrieval scores, paired-evidence completeness and metadata coverage, currently labelled “alignment accuracy.” | Rename in the next API/UI contract to **evidence-alignment quality** or another non-accuracy name. It is not answer accuracy or a calibrated confidence probability. Keep backward compatibility only with an explicit deprecation/version field. |

**Separation of concepts:** numerical drift bands (Low/Medium/High) describe measured text movement only; they are **not** the materiality taxonomy (High/Medium/Low/None), compliance outcome, urgency or risk level. A 10-to-15-day deadline edit may have little lexical drift but a material obligation change; a scenario involving filing on day 12 may change compliance outcome, while one filed on day 5 may not. The system must display that distinction and abstain on consequences without supported facts/applicability. A no-change result requires genuine aligned evidence, not missing data.

**Missing data and disagreement policy:** if source fidelity, relation, alignment or a component's evidence is insufficient, mark the component and overall score `unavailable` with a reason; never silently replace an absent conceptual score with zero. If a proxy is used, label it. Show component spread and an explicit disagreement warning; an aggregate cannot conceal a severe component. If scoring is later calibrated against independent reference judgments, record the dataset, split, confidence intervals, thresholds, calibration plots and version—do not backfill a claim of legal accuracy into today's heuristic.

**Evaluation set:** build a small frozen technical fixture suite from source-backed aligned pairs and separately marked synthetic edge cases. Include exact equality, spelling-only edits, deadline/amount changes, negation, added penalty, long insertion, OCR corruption, wrong-Act retrieval, wrong-version pairing, missing before/after, ambiguous transition and opposing 0/100 components. Check determinism, bounded 0–100 outputs where available, formula reproduction, component disagreement, mode invariance, abstention and score-to-source traceability. An independent legal-label evaluation remains a later research gate.

### 0.9 Deliverable C — query-grounded before/after clause comparison

**Selection pipeline:** classify intent (lookup, summary, comparison, scenario question) → extract instrument, provision and dates where given → search hybrid local/official evidence → rank candidate amendment relationships → resolve actual target provision and before/after version using the graph and temporal facts → restrict to clauses relevant to the question → align comparable spans → generate explanation and metrics only over those spans. Retrieval score alone cannot establish a legal version or effective date. For an amending instruction that cannot be transformed into a trustworthy consolidated after-text, display “amendment instruction” and “available Act text,” not fabricated pre/post law.

**Comparison record:** query ID, intent and mode; instrument and provision IDs; candidate and selected source IDs with hashes; relation/transition ID and support class; requested and supported dates; normalized before/after text; exact source page/line and, where recoverable, PDF text coordinates; added/removed/modified spans; operation; source-fidelity warnings; materiality triage **status**; scenario-specific consequence **status**; scoring-method version and trace; answer citations and abstention reasons. Keep original extracted text and PDF as immutable evidence; normalization and alignment are derived layers.

**Rendering contract:** a readable side-by-side comparison on wide screens, stacked on small screens; source name/version/date and citation at the top of each pane; consistent colors and patterns for additions, removals and unchanged context; a focused “what changed” summary; direct open-source links; a separate score-explanation panel showing the exact compared spans and formula. If reliable PDF coordinates exist, clicking a citation opens and highlights the corresponding page region. If they do not, highlight the verified textual excerpt and say “page-region highlight unavailable” rather than painting an approximate PDF location. Do not insert unsanitized model HTML into the DOM. Use semantic headings, keyboard-operable controls, visible focus, adequate contrast, non-color-only indicators, screen-reader labels and clear loading/empty/error/review-required states. `Specific` mode should show clause-level details; `Generic` mode should summarize only the same supported evidence, with score and source selection invariant across modes.

**Answer quality contract:** distinguish supported quotation, derived comparison, machine materiality triage, applicability determination and scenario consequence in both API and UI. Every substantive sentence must map to one or more returned citations or be explicitly marked inference/uncertainty. An LLM timeout uses an identified extractive fallback; a successful request must not display a fictitious LLM analysis. An answer may be useful without a drift score, and the official India Code/Gazette links remain available for complete-text verification.

### 0.10 Execution order and hard gates for this sprint

The labels **S0–S6** below are sprint milestones, not the research phases in §19 and not a renumbering of existing reports. Each gate blocks dependent work from laundering a source, graph or evidence error into a polished answer.

| Stage | Objective, inputs and implementation tasks | Deliverables and validation checks | Gate and failure condition |
| --- | --- | --- | --- |
| **S0. Freeze and inspect** | Input: clean baseline, active v0.6.0 release, current code/tests/artifacts. Record Git SHA, checksums, dependency lock, API/schema contracts and existing benchmark limits. Reproduce only safe read-only checks first; decide write targets before running builders. | Baseline record, defect list, API/schema compatibility map and approved acceptance fixtures. Tests and gates reported with exact commands/results; no frozen artifact changed. | **Gate:** baseline reproducible and rollback path documented. **Fail:** dirty/unexplained inputs, checksum mismatch or untracked generated output about to be overwritten. |
| **S1. Official-source feasibility** | Depends on S0. Verify Gazette and India Code access mechanisms, terms, identifiers and metadata using bounded samples; design connector contracts and a manual/import fallback. | Source-access decision record, test fixtures, rate/access policy and explicit supported scope. | **Gate:** at least one lawful, reliable path for each claimed source, or honestly mark that source `ACCESS_LIMITED`. **Fail:** undocumented API assumed stable, blocked access bypassed, or completeness claimed without audit. |
| **S2. Scheduled incremental pipeline** | Depends on S1. Implement persistent 24-hour checkpoints, cross-process lease, idempotent discovery/download, immutable hash/version records, stage cache/retry/recovery, review queue and atomic graph/index activation. | Versioned ingestion manifests and operator commands. Tests with fake clock/HTTP and temporary storage cover 24-hour boundary, concurrent workers, duplicates, changed bytes, renamed URLs, partial failures, restart, network outage, tampering and no-reprocess rule. | **Gate:** one new document traverses to review; unchanged bytes do not repeat downstream work; revisions produce new versions; graph/index bindings reconcile. **Fail:** duplicate automatic run, overwritten source, partial active index or silent drop. |
| **S3. Query-pair and score contract** | Depends on S0 and trustworthy source/version fixtures; S2 need not be fully deployed for local fixtures. Specify alignment, component availability, scoring formulas/weights, mode invariance and versioned response fields. Refactor only necessary backend boundaries. | Frozen technical scoring fixtures, per-component trace and comparison-record schema; “alignment accuracy” migration plan. Unit/property tests for 0/100 disagreement, numerical changes, same text, noise, missing components and unsupported pairs. | **Gate:** every displayed number recomputes from the returned evidence and method version; unsupported pairs have no score. **Fail:** score from whole-doc mismatch, hidden proxy, NaN, silent zero or implied legal accuracy. |
| **S4. Clause retrieval and explanation** | Depends on S3 and graph-source integrity. Select query-relevant provisions, verify relation and temporal support, align spans, attach locators, compare, and constrain/validate the explanation. | Versioned comparison API and golden technical fixtures. Tests cover correct vs distractor clause, same-act/wrong-version, an amending instruction vs consolidation, dates, OCR/furniture, citations, fallback and explicit abstention. | **Gate:** pre/post labels and citations match the actual version evidence; wrong or incomplete evidence is not promoted. **Fail:** fabricated version, unsupported effective date, model-only citation or mislabeled excerpt. |
| **S5. UX integration** | Depends on S3–S4 contracts. Implement source health, query-first comparison, exact-span view, score breakdown and method, open-source/highlight behavior and error states in React. Preserve current navigation and review flow unless usability evidence warrants change. | Responsive, accessible interface and API contract tests. Browser tests or documented manual checks at desktop/mobile widths; keyboard and screen-reader checks; score/formula/source parity with backend. | **Gate:** a novice can identify what changed, why the score appears, and what remains unverified. **Fail:** inaccessible controls, unexplained percentages, misleading PDF highlight, blank failure state or frontend/backend disagreement. |
| **S6. Integrated release** | Depends on S2, S4 and S5. Run full Python/frontend suites, source-mocked end-to-end daily cycle, representative question-to-citation flow, graph/index compatibility, clean-environment build and release-version audit. Update operational docs and claim-to-evidence matrix to actual results. | New immutable release (not an edit to v0.6.0), deployment/runbook, evidence reports, known-limit list and rollback procedure. | **Gate:** fresh environment reproduces claimed engineering behavior; no regression in prior gates; legal/research validation still accurately marked. **Fail:** unchecked external source dependence, missing release binding, silent fallback or unrepeatable result. |

**Execution discipline:** after each stage, inspect the Git diff and provenance manifest; run focused tests, then the relevant gate. Do not advance on a failing hard gate. Repair root causes at the earliest faulty stage rather than adding presentation-layer exceptions. Keep old reports, source artifacts, silver labels and releases immutable. Add a new version when a contract or derived dataset changes. Do not change `docs/context.md`, `docs/implementation-plan.md`, or application files merely by virtue of editing this plan; update them during the implementation sprint when the corresponding facts actually change.

### 0.11 API, storage and observability contract to finalize before coding

- **APIs:** retain the single-prompt `{query, mode}` user flow; add explicit comparison, source-health and run-trace fields under a versioned response contract. Make `reference_date`/scenario optional inputs only when the question needs them. Never require manual pre/post PDF uploads for ordinary RAG use, though reviewed imports may remain an administrative path.
- **Storage:** immutable raw bytes; versioned normalized text, amendment events, graph, index, alignment and metrics; persisted scheduler state and stage runs; append-only review events. Use content-addressed IDs where suitable and explicit source-document IDs for identity/revision history. Store source and transform hashes in every derived record.
- **Failure taxonomy:** distinguish `SOURCE_UNAVAILABLE`, `ACCESS_LIMITED`, `DOWNLOAD_FAILED`, `SOURCE_TEXT_UNRELIABLE`, `TARGET_UNRESOLVED`, `VERSION_UNSUPPORTED`, `TEMPORAL_FACTS_MISSING`, `PAIR_UNALIGNED`, `SCORING_UNAVAILABLE`, `MODEL_UNAVAILABLE`, `CITATION_UNVERIFIED` and `REVIEW_REQUIRED`. Do not collapse these into a generic “no change.” Version any public status vocabulary.
- **Observability:** structured logs with source/run/correlation IDs but no secrets; counters for discovered, fetched, duplicate, revised, parsed, unresolved, reviewed, indexed, failed and lagged records; alerts for stale daily runs and graph/index mismatch. Do not log full confidential user scenarios by default.
- **Security and operations:** allowlist official hosts and validate redirects, MIME/size limits, safe file names, checksum every source, protect against SSRF and ZIP/PDF bombs, sanitize HTML/Markdown, keep API keys out of Git, throttle official requests, and provide manual pause/retry/backfill with audit records.

### 0.12 Definition of done and explicitly deferred claims

The **sprint engineering deliverables** are done only when a scheduled run demonstrably discovers a new or revised authorized source, preserves its evidence and version history, processes only necessary stages, activates a consistent graph/index pair or records a reviewable failure, and a question about a supported transition produces a correctly attributed clause comparison and a fully recomputable drift trace. A supported non-comparison question must still receive an evidence-bounded answer without inventing a score. The desktop/mobile UI must expose limitations plainly. The same examples must reproduce in a clean environment from frozen fixtures without requiring live source availability.

The **research project** is not complete merely because this sprint passes. Coverage of all India Code Acts/amendments, complete historical consolidations, legally validated applicability, materiality gold, expert-gold compliance scenarios, legal-risk correctness, controlled drift-benchmark results and independent expert review remain separate gates. If no qualified reviewer is available, publish engineering/silver findings with the legal gate `UNVERIFIED`; do not promote an internal model or team review to legal gold. Any claim of “recent” or “up to date” must include source scope and last successful discovery time.

---

## 1. Project Definition

The project will design and evaluate a temporally versioned India Code benchmark for determining whether LLM-based compliance systems correctly propagate legally applicable changes in Indian law over time.

The planned end-to-end research flow is:

```text
India Code and other authoritative Indian legal sources
    -> historical provision reconstruction
    -> temporal applicability determination
    -> amendment representation
    -> materiality analysis
    -> controlled compliance scenarios
    -> pre/post LLM compliance reasoning
    -> false stability / false instability
    -> citation drift / explanation drift
    -> expert validation
    -> reproducible benchmark release
```

Materiality classification is an intermediate research component. The project is not defined as a standalone amendment classifier. Its central object is the behaviour of compliance reasoning across legally applicable versions of Indian law.

### Primary research question

> **Do LLM-based compliance systems correctly propagate legally applicable changes in Indian law over time?**

### Intended core contribution

> **A temporally versioned India Code benchmark and evaluation framework that tests whether LLM compliance reasoning correctly propagates legally material legislative changes, while distinguishing genuine legal drift from non-material textual change and grounding conclusions in authoritative evidence.**

---

## 2. Research Problem

An LLM compliance assertion can fail temporally even when it is fluent, cites a real provision, and appears legally plausible. The relevant failure is not merely failure to detect that text changed. The system must determine:

1. which provision version governs the facts at the reference date;
2. what amendment transformed the relevant provision;
3. whether the amendment is legally material;
4. whether that material change affects the particular compliance scenario;
5. whether the model updates its conclusion, citation, and explanation appropriately; and
6. whether every conclusion is supported by authoritative evidence.

The research problem therefore contains three distinct decisions:

- **Materiality:** how legally significant is the amendment?
- **Temporal applicability:** which legal version governs this scenario at this time?
- **Compliance consequence:** what does the applicable law imply for these facts?

These decisions must be represented and evaluated separately. A material amendment need not change every scenario outcome, and a correct materiality label cannot compensate for applying the wrong legal version.

The newer compliance-risk deliverable adds a **fourth downstream assessment**, not a substitute for any of the three: given an applicable obligation, scenario facts, and a supported consequence, determine provisional severity, urgency, uncertainty, and escalation. Neither large textual drift nor a High materiality label automatically means High risk. A risk result with missing evidence is unknown, not `None`.

---

## 3. Research Questions

### RQ1 - Historical reconstruction and applicability

Can Indian legislative history be reconstructed accurately enough to determine which provision version governs a scenario at a specified date?

### RQ2 - Amendment materiality

Can legally material changes be distinguished from non-material textual changes using structured amendment representations?

### RQ3 - Compliance propagation

Do LLM compliance assertions appropriately update when the legally applicable Indian provision changes?

### RQ4 - Evidence-grounded explanation

Can evidence-grounded explanations identify the correct legal version, amendment, materiality, and compliance consequence?

Each RQ requires its own ground truth, metrics, failure analysis, and legal-validation procedure. Performance on one RQ must not be used as a proxy for another.

---

## 4. Research Hypotheses

These are testable hypotheses, not claims of established results.

### H1 - Reconstructability

A provision-lineage and amendment-event representation linked to authoritative evidence will support more reliable point-in-time legal reconstruction than using only a current consolidated provision or publication date. Success thresholds must be approved in Phase 0 and evaluated against legal-expert determinations.

### H2 - Structured materiality representation

Structured amendment information, including operation, affected legal dimensions, context, and before/after evidence, will improve materiality classification over class-prior, lexical, and edit-distance baselines. The hypothesis may be rejected if strong general revision or LLM baselines perform equivalently.

### H3 - Context-sensitive temporal drift

LLM compliance behaviour will vary across legal-context conditions. Providing reconstructed, temporally applicable legal context is expected to reduce version, applicability, citation, and compliance errors relative to underspecified or temporally ambiguous conditions. This must be tested under controlled model and prompt configurations.

### H4 - Scenario dependence

Amendment materiality alone will not fully determine whether a compliance answer should change. Expected change will depend jointly on the amendment, the applicable version, the reference date, transitional or retrospective rules where relevant, and the scenario facts.

### H5 - Evidence-grounded explanation

Explanations constrained to identify authoritative evidence, version, amendment operation, materiality, and compliance consequence will be more legally verifiable than unconstrained fluent explanations. Legal correctness must be assessed by experts on an appropriate subset rather than exclusively by an LLM judge.

---

## 5. Novelty and Positioning

### 5.1 Defensible novelty position

The project combines four elements into one evaluation framework:

1. authoritative India Code-centred provision history;
2. explicit temporal-applicability determinations;
3. amendment materiality linked to controlled compliance scenarios; and
4. pre/post evaluation of LLM conclusions, citations, and explanations.

The benchmark and evaluation framework remain scientifically useful even if no proposed model exceeds the strongest baselines.

### 5.2 Claims the project must not make

The project must not claim:

- first-ever amendment classification;
- first-ever legal change detection;
- first-ever materiality classifier;
- generic invention of legal edit-significance classification; or
- autonomous legal correctness.

### 5.3 Adjacent work and novelty audit

The repository identifies adjacent work on legal amendment detection, edit/materiality classification, temporal legal reasoning, legal version reconstruction, and LLM reasoning over changing law. The project context also flags RegTrack and recent temporal legal reasoning benchmarks as important comparators, but the repository does not establish enough verified bibliographic detail to state their precise scope here.

Before implementation begins, Phase 0 must produce a formal novelty audit that:

- verifies the closest work from primary sources;
- includes RegTrack and recent temporal legal reasoning benchmarks;
- compares tasks, jurisdictions, temporal models, units of analysis, labels, scenarios, evaluation conditions, metrics, source provenance, and release artifacts;
- identifies what is reused, adapted, or newly combined;
- determines whether a closest-work-inspired baseline is feasible; and
- creates a claim-to-evidence matrix for the final paper.

The paper must position amendment materiality as one component of temporal compliance propagation and explicitly compare the final contribution with the closest verified work.

---

## 6. Scope and Corpus

### 6.1 In scope

- India Code and other authoritative Indian legal sources needed to establish legislative text, amendments, and temporal applicability;
- provision-level history and amendment events;
- publication, enactment/assent, commencement, applicability, and legal-effect evidence;
- materiality annotation using the canonical four levels;
- controlled compliance scenarios;
- scenario-specific obligation, consequence, and conditional risk assessment;
- LLM pre/post reasoning evaluation;
- version, applicability, outcome, citation, and explanation evaluation;
- expert legal validation; and
- a reproducible, versioned benchmark.

### 6.2 Out of scope for the core project

- eCFR as the primary corpus;
- a generic regulatory-change classifier detached from Indian temporal applicability;
- production legal advice;
- autonomous publication of legal conclusions;
- mandatory deployment of a monitoring agent;
- unsupported claims about legal hierarchy; and
- claims of comprehensive coverage of Indian law.

### 6.3 Phase 0 corpus decisions

Before expanding the technical pilot into a claimed benchmark, the team must approve:

- included legal domains and instruments;
- date range;
- central/state scope, if relevant;
- source-access and redistribution constraints;
- pilot size;
- minimum benchmark target;
- desired benchmark target;
- minimum class coverage;
- domain coverage;
- amendment-operation coverage;
- temporal-complexity coverage; and
- the cost and legal-expertise justification for those targets.

No final dataset size is established in the current repository. The approved targets must be recorded as design decisions, not retrofitted after collection.

---

## 7. Core Concepts and Formal Definitions

### 7.1 Amendment

An authoritative legal event that inserts, substitutes, omits, repeals, modifies, renumbers, or otherwise affects legal text or its operation. Detection of textual difference is not itself a materiality or applicability determination.

### 7.2 Materiality

The legal significance of an amendment independent of any one scenario outcome. The canonical levels are:

- `High`
- `Medium`
- `Low`
- `None`

The annotation guideline must formally define each level, inclusion criteria, exclusion criteria, positive examples, negative examples, boundary cases, and adjudication rules.

### 7.3 Materiality dimensions

The current manuscript discusses obligation, right, prohibition, scope, definition, threshold, time, liability, procedure, exemption, and compliance outcome. The deck describes ten dimensions, while the manuscript enumerates eleven.

Phase 0 must determine whether compliance outcome is:

- a materiality dimension; or
- a separate scenario-dependent field, which is methodologically preferable unless legal review establishes otherwise.

The exact number and definitions must be frozen before annotation.

### 7.4 Temporal applicability

The expert-supported determination of which legal provision/version governs a scenario at a reference date, given the relevant legal and factual conditions. It is not reducible to choosing the latest text or checking a single `valid_from` date.

### 7.5 Compliance consequence

The implication of the temporally applicable provision for the facts and legal question in a specific scenario. It must be annotated separately from materiality.

### 7.6 Expected and observed change

For a paired scenario evaluation:

```text
ExpectedChange in {0, 1}
ModelChange    in {0, 1}
```

- `ExpectedChange = 1`: expert ground truth says the compliance answer should change between the evaluated legal conditions.
- `ExpectedChange = 0`: expert ground truth says the answer should remain stable.
- `ModelChange = 1`: the model's normalized compliance conclusion changes.
- `ModelChange = 0`: the model's normalized compliance conclusion remains stable.

### 7.7 Drift outcomes

- **Correct update:** `ExpectedChange = 1` and `ModelChange = 1`.
- **Correct stability:** `ExpectedChange = 0` and `ModelChange = 0`.
- **False stability:** `ExpectedChange = 1` and `ModelChange = 0`.
- **False instability:** `ExpectedChange = 0` and `ModelChange = 1`.
- **Citation drift:** the conclusion or answer may be stable or changed, but the cited authority/version is incorrect, superseded, temporally inapplicable, or inconsistently propagated.
- **Explanation drift:** the conclusion may be correct, but the rationale relies on the wrong version, date, amendment, materiality reasoning, or compliance consequence.

### 7.8 Required conceptual flow

```text
AMENDMENT
  -> MATERIALITY
  -> TEMPORAL APPLICABILITY
  -> SCENARIO
  -> COMPLIANCE CONSEQUENCE
```

The implementation may compute supporting evidence in another technical order, but the benchmark must preserve these distinct judgments and their dependencies.

---

## 8. Temporal Legal Model

### 8.1 Version graph

Retain the provision-version graph:

```text
Legal Instrument
  -> Provision lineage
  -> Provision versions
  -> Amendment events
  -> Temporal applicability determinations
```

Every derived node and edge must trace to immutable authoritative evidence.

### 8.2 Temporal semantics

The model must not represent legal time only through `valid_from` and `valid_to`. It must be able to record, when supported:

- publication;
- enactment or assent;
- commencement;
- applicability to the scenario;
- legal effect;
- retrospective effect;
- transitional provisions;
- deferred commencement;
- partial commencement;
- explicit uncertainty or unresolved conflict; and
- the authoritative evidence supporting each temporal assertion.

The plan does not prescribe a legal hierarchy among sources or dates. Such rules must be validated by a qualified legal reviewer and documented in a versioned temporal-semantics registry.

### 8.3 Central temporal query

> **Given legal scenario S and reference date T, which legal provision/version governs S, and what authoritative evidence establishes that applicability?**

The resolver must return both a determination and its evidence. Where the evidence is incomplete or ambiguous, the correct result is an unresolved or escalated status, not a silently inferred date.

### 8.4 Reconstruction and applicability are separate

- **Reconstruction** establishes the text and lineage of provision versions.
- **Applicability resolution** establishes which reconstructed version governs the scenario.

A historically accurate version graph can still yield an incorrect compliance result if applicability is resolved incorrectly.

---

## 9. System Architecture

```mermaid
flowchart TD
    A[Authoritative Indian legal sources]
    B[Acquisition and immutable provenance]
    C[Parsing, OCR controls, and normalization]
    D[Legal instrument and provision identity]
    E[Provision lineage and version graph]
    F[Temporal semantics registry]
    G[Temporal applicability resolver]
    H[Amendment representation and aligned pre/post pairs]
    I[Materiality annotation and modelling]
    J[Controlled compliance scenarios]
    R[Obligation and consequence assessment]
    K[LLM evaluation conditions]
    L[Compliance conclusion normalization]
    M[Drift, citation, and explanation metrics]
    N[Expert validation and reproducible benchmark]
    O[Optional monitoring agent]

    A --> B --> C --> D --> E
    E --> G
    F --> G
    E --> H --> I
    G --> J
    I --> J
    J --> R
    J --> K --> L --> M --> N
    R --> M
    E --> O
    G --> O
    I --> O
```

### Architectural boundaries

- Raw source evidence is immutable.
- Parsing errors are quarantined rather than accepted silently.
- Version reconstruction does not decide materiality.
- Materiality does not decide applicability.
- Applicability does not decide the compliance consequence without scenario facts.
- Compliance risk is computed from the applicable obligation, facts, and consequence, with uncertainty and escalation; no drift-score shortcut is permitted.
- Model output does not become gold truth.
- Expert validation is part of the core, not an optional post-processing step.
- The monitoring agent is downstream of validated benchmark components.

**Current integration boundary (inspected 2026-10-12):** `rag/rag_pipeline.py` now calls the graph-v4 consumer for aligned amendment fragments, while `risk/` still uses a narrow, versioned obligation registry rather than a legally approved point-in-time determination for every request. `orchestration/pipeline.py` produces a structured case run, but its real-corpus applicability stage explicitly reports no approved temporal facts. Live India Code query-time lookup supplements local retrieval; it does not reconstruct historical applicability or run daily ingestion. The frontend is a single-prompt React/Vite assistant with risk and case-review views; exact PDF-coordinate clause highlighting remains unimplemented. None of these paths warrants an end-to-end validated-law claim.

### Deliverable-chain status at the audited checkout

| Requested component | Current status | Evidence / missing link |
|---|---|---|
| Gazette and authoritative-source ingestion | Bounded engineering pipeline | `ingestion/` records source, hash, deduplication, failures and human-review queue; the scheduler is one-shot and no persistent 24-hour Gazette/India Code job has been demonstrated. |
| Legal amendment extractor | Machine candidate extractor | `amendment_extraction/` has a versioned extraction artifact; source fidelity and unresolved cases still require review. Consult the current checkpoint for counts. |
| Temporal legal knowledge graph | Technical fragment graph | `versioning/temporal_graph.py` and the graph-v4 consumer link source-backed fragments; transitions are not independently legally validated or complete historical consolidations. |
| Materiality classification | Proposed rubric and silver triage | 50 frozen machine cases and versioned disagreement audit; no legally validated classifier or gold metric. |
| Compliance risk assessment | Deterministic conditional baseline | `risk/` models obligations, facts, consequence, urgency and abstention for a narrow registry; no corpus-wide or expert-gold outcome set. |
| Explainable LLM | Structured engineering explanation and RAG fallback | `explanations/contract.py` and `orchestration/pipeline.py` record bounded, non-gold case explanations; `rag/` also has optional model generation and an identified extractive fallback. No expert explanation correctness is established. |
| Compliance decision dashboard | Working UI/API components | `frontend/` provides prompt, corpus, drift/score, risk and case-review views; exact source-region highlighting and the sprint's source-health view are still planned. |

This table documents **component existence and integration gaps**, not patentability or a complete autonomous legal-decision system.

---

## 10. Data Model

The following is a conceptual schema, not an implemented database.

| Entity | Required conceptual fields |
|---|---|
| `legal_instrument` | instrument ID, title, type, jurisdiction, ministry/authority where supported, official identifier |
| `source_artifact` | source ID, official reference/URL, retrieval time, content hash, media type, publication evidence, raw location |
| `provision` | stable provision ID, instrument ID, structural path, parent ID, lineage ID |
| `provision_version` | version ID, provision ID, exact text, structural representation, source links, extraction method/confidence |
| `amendment_event` | event ID, amending instrument, target provision/version, operation, evidence, relevant legal dates |
| `temporal_fact` | fact ID, event/version ID, fact type, date/condition, source evidence, reviewer status, uncertainty |
| `applicability_determination` | scenario ID, reference date, governing version ID, reasoning, supporting temporal facts, expert status |
| `version_pair` | pair ID, before/after version IDs, amendment event, aligned context, structural and lexical diffs |
| `materiality_annotation` | pair ID, annotator, guideline version, level, dimensions, evidence spans, rationale, confidence |
| `materiality_gold` | pair ID, frozen level/dimensions, agreement, adjudication status, gold rationale |
| `compliance_scenario` | scenario ID, schema version, facts, legal question, reference date, governing version, expected answer, expected consequence, expected change, evidence, expert rationale |
| `obligation_rule` | rule/version ID, provision/version, scope, applicability status and supported dates, obligation, consequence, severity, evidence IDs, operational rationale |
| `compliance_risk` | risk ID, scenario/version, obligation, consequence, severity, urgency, risk level or null, evidence, uncertainty, escalation, legal-validation status |
| `model_run` | model/version, condition, prompt/config versions, temperature, retrieval settings, run time, seed where available |
| `llm_assertion` | run ID, scenario ID, normalized answer, raw answer, citations, explanation, confidence if supplied |
| `evaluation_result` | applicability, version, outcome, materiality, citation, explanation, and drift labels/metrics; reviewer notes |

All derived records must preserve a chain to source artifact hashes, transformation versions, annotation versions, and expert decisions.

The implemented `schemas/risk/` contracts model provisional risk separately from the research benchmark's `schemas/scenario/` contract. The current obligation registry covers only two conditional Section 19 demonstrations. Its `legal_validation` output remains `UNVERIFIED`; it must not be presented as a corpus-wide legal risk knowledge base.

---

## 11. Benchmark Design

### 11.1 Benchmark units

The benchmark contains linked but separately evaluable objects:

1. authoritative source artifacts;
2. provision lineages and versions;
3. amendment events;
4. temporal facts;
5. pre/post version pairs;
6. materiality annotations;
7. applicability determinations;
8. controlled compliance scenarios;
9. expected change/no-change labels;
10. model runs and assertions; and
11. expert evaluation records.

### 11.2 Benchmark tracks

- **Track A - Historical reconstruction:** recover the correct provision text/version and evidence.
- **Track B - Temporal applicability:** select the governing version for scenario S at time T.
- **Track C - Materiality:** classify the amendment level and dimensions.
- **Track D - Compliance consequence:** answer the scenario under the applicable law.
- **Track E - Temporal propagation:** determine whether the model updates appropriately across versions.
- **Track F - Evidence-grounded explanation:** justify version, amendment, materiality, and consequence.
- **Track G - Conditional compliance risk:** where source-backed obligations and scenario facts permit it, evaluate severity, urgency, abstention, and escalation independently of textual drift.

This modular design prevents a single end-to-end score from hiding whether failure originated in parsing, reconstruction, applicability, materiality, or compliance reasoning.

### 11.3 Size and coverage decisions

Phase 0 must approve and justify:

- pilot size: retain the planned 50-pair double-annotated pilot unless legal or corpus evidence requires revision;
- minimum and desired final benchmark targets;
- class distribution and minimum examples per materiality level;
- number and diversity of legal domains and instruments;
- amendment-operation coverage;
- temporal-complexity coverage;
- scenario categories and expected-change balance;
- expert-annotation capacity and budget; and
- held-out split feasibility.

Targets are planning constraints. They must not be described later as achieved until the release manifest proves them.

### 11.4 Release policy

Each frozen release needs:

- a release version;
- source/provenance manifest;
- schema versions;
- annotation-guideline version;
- scenario-schema version;
- split manifests;
- known limitations;
- permitted redistribution statement; and
- checksums for released artifacts.

---

## 12. Annotation Protocol

### 12.1 Annotators

- two independent annotators with relevant legal training for the pilot and gold-labelled subset;
- a qualified third reviewer/adjudicator for guideline-resolvable disagreement and legally material edge cases;
- preserved annotator identities or stable pseudonymous IDs in the research record; and
- conflict-of-interest and qualification documentation appropriate to the study.

### 12.2 Annotation record

Preserve:

- individual materiality level;
- materiality dimensions;
- amendment operation;
- before/after evidence spans;
- rationale;
- confidence/uncertainty;
- temporal concerns noticed by the annotator;
- compliance-consequence notes, stored separately from materiality;
- guideline version; and
- adjudication history.

### 12.3 Taxonomy rules

The frozen guideline must define for `High`, `Medium`, `Low`, and `None`:

- inclusion criteria;
- exclusion criteria;
- positive examples;
- negative examples;
- boundary cases;
- interaction with multiple affected dimensions;
- handling of insufficient evidence; and
- adjudication rules.

Do not silently substitute the historical eCFR categories `cosmetic`, `substantive`, or `contested`. Any schema change requires explicit approval, mapping, versioning, migration, and revalidation.

### 12.4 Pilot procedure

1. Select 50 pairs according to approved diversity rules.
2. Annotate independently.
3. Preserve all labels, rationales, and evidence spans.
4. Measure agreement using the statistic appropriate to the number of annotators, label scale, missingness, and study design. Candidates include Cohen's kappa, Fleiss' kappa, and Krippendorff's alpha; not all must be used.
5. Analyse disagreement by level, dimension, amendment operation, and evidence sufficiency.
6. Revise the guideline only through a recorded version change.
7. Re-annotate affected pilot items after substantive changes.
8. Freeze the taxonomy and guideline before full annotation.

Low agreement is a methodological finding and gate failure requiring diagnosis; it must not be hidden through undocumented adjudication.

---

## 13. Compliance Scenario Design

Compliance scenarios are first-class benchmark objects, not illustrative prompts added after materiality modelling.

### 13.1 Scenario schema

Each scenario should contain:

- scenario ID;
- scenario-schema version;
- facts;
- legal question;
- reference date;
- applicable legal version;
- expected answer;
- expected compliance consequence;
- expected change/no-change;
- supporting legal evidence;
- expert rationale;
- temporal/applicability notes; and
- review/adjudication status.

### 13.2 Required scenario categories

The benchmark should deliberately sample, where supported by verified legal evidence:

- material amendment where the compliance outcome changes;
- material amendment where the scenario outcome remains unchanged;
- non-material amendment where the answer should remain stable;
- temporal traps;
- transitional-rule cases;
- deferred or partial commencement cases;
- retrospective/applicability cases where legally appropriate;
- citation traps; and
- explanation-drift cases.

No actual legal example should be added until it is supported by authoritative source evidence and expert review.

### 13.3 Scenario controls

- Hold scenario facts constant across paired pre/post evaluations unless the experiment explicitly studies fact variation.
- Separate the legal reference date from document retrieval or model-run date.
- Record which legal version experts expect to govern.
- Record why the answer should or should not change.
- Avoid scenarios whose expected answer cannot be reliably adjudicated.
- Balance changed and unchanged expected outcomes sufficiently to make both false-stability and false-instability rates meaningful.

### 13.4 Compliance-risk extension and current coverage

For a risk assessment, additionally specify organization type, industry, jurisdiction, activity, exposure, applicable provision, and the facts needed by an evidence-linked obligation rule. Keep expected **compliance outcome** and expected **risk** separate from amendment materiality. The deterministic baseline must select an applicable rule using explicit date/scope evidence, evaluate the scenario facts, attach obligation/consequence evidence, and return provisional risk, urgency, uncertainty, and escalation—or abstain. Unknown risk is `null`, not a zero/`None` risk level. Drift percentages must not enter the risk calculation.

The existing `data/risk/compliance_scenarios.v1.json` converts 13 source templates into structured **abstention** cases and adds two conditional Section 19 demonstration inputs. It does not contain 13 substantive, independently validated expected legal outcomes. `data/risk/obligation_registry.v1.json` and `src/temporal_legal_drift/risk/` implement a bounded operational model, not legal gold. The next research work is source-grounded scenario authorship, historical applicability validation, independent expected-outcome review where available, and wider rule coverage. See `reports/risk/checkpoint.v1.md` and `protocols/compliance_risk_protocol.v1.md`.

---

## 14. Baselines

The baseline suite must be feasible for the final data scale and task formulation. Planned candidates are:

1. majority and class-prior baselines;
2. edit-distance and lexical-difference features;
3. amendment-operation features;
4. rule-based legal cues for duties, prohibitions, thresholds, dates, definitions, exceptions, procedures, and penalties;
5. a generic document-revision classifier;
6. zero-shot LLM materiality and compliance baselines;
7. few-shot LLM baselines;
8. a legal encoder;
9. a long-context encoder;
10. a baseline inspired by the closest verified legal-change benchmark methodology; and
11. the proposed materiality model, if resources permit.

Requirements:

- Do not describe a prior method as reproduced unless its implementation and validation actually support that statement.
- Record deviations from prior methodologies.
- Use the same frozen benchmark definitions and split manifests for comparable methods.
- Include strong non-neural baselines.
- Treat the proposed model as optional to the benchmark's scientific validity.
- Evaluate whether materiality predictions add explanatory value to temporal compliance propagation; do not make materiality accuracy the only headline result.

---

## 15. Temporal LLM Evaluation

### 15.1 Controlled conditions

Where technically and legally appropriate, evaluate each selected model under:

1. no legal context;
2. pre-amendment legal context;
3. post-amendment legal context;
4. both versions;
5. both versions plus explicit reference date; and
6. reconstructed temporally applicable legal context.

The conditions are designed to distinguish:

- knowledge failure;
- retrieval failure;
- temporal reasoning failure;
- applicability failure;
- compliance reasoning failure; and
- citation/explanation propagation failure.

### 15.2 Experimental controls

For comparisons intended to isolate context effects:

- hold model and model version constant;
- hold prompt template constant except for the condition-specific context;
- hold temperature and decoding settings constant;
- hold retrieval configuration constant or document the intended difference;
- preserve raw prompts and outputs;
- version system instructions, schemas, normalization rules, and evaluators;
- record run date and provider/API version where available;
- repeat stochastic runs according to a Phase 0 power/variance decision; and
- prevent model outputs from entering gold labels.

### 15.3 Answer normalization

Define a pre-registered normalization procedure that maps raw answers to the benchmark's expected compliance-answer representation. Human review must resolve ambiguous mappings on a blinded subset. Normalization must not be changed after inspecting final model rankings without a documented protocol amendment.

### 15.4 Failure attribution

Each failure should be attributed, where possible, to one or more layers:

- wrong source/retrieval;
- wrong version reconstruction;
- wrong temporal applicability;
- wrong amendment/materiality interpretation;
- wrong scenario reasoning;
- wrong normalized conclusion;
- wrong citation; or
- unfaithful explanation.

---

## 16. Explanation Evaluation

### 16.1 Explanation content

An explanation should identify:

- legal instrument;
- provision path;
- applicable date;
- version ID;
- before evidence;
- after evidence;
- amendment operation;
- affected materiality dimension;
- materiality level;
- compliance consequence;
- confidence; and
- uncertainty/escalation reason.

### 16.2 Fluency versus faithfulness

- **Fluency** concerns readability and coherence.
- **Faithfulness** concerns whether claims are supported by the correct authoritative evidence and reasoning chain.

A fluent explanation with the wrong version, date, citation, or legal consequence is a failure.

### 16.3 Evaluation dimensions

- evidence correctness;
- temporal correctness;
- entailment by cited evidence;
- completeness;
- materiality reasoning;
- compliance reasoning;
- citation precision;
- uncertainty handling; and
- usefulness/contestability for a legal reviewer.

Automated checks may support evaluation, but legal correctness must not rely exclusively on LLM-as-judge. A qualified expert must assess an approved subset using a versioned rubric and blinded procedure where feasible.

---

## 17. Metrics

### 17.1 Reconstruction and applicability

- provision identity accuracy;
- provision-version reconstruction accuracy;
- amendment-event linkage accuracy;
- temporal-fact extraction accuracy by fact type;
- temporal applicability accuracy;
- evidence/provenance completeness; and
- unresolved/abstention rate.

These metrics determine whether downstream evaluation is based on the right law. A model cannot receive credit for a correct final answer grounded in an incorrect or unsupported version.

### 17.2 Materiality

- per-class precision, recall, and F1;
- macro-F1;
- confusion matrix;
- calibration where scores are produced;
- high-materiality false-negative rate; and
- performance by dimension, amendment operation, domain, and agreement stratum.

High-materiality false negatives receive separate attention because treating a legally significant amendment as negligible can suppress a required compliance update. They must not be equated automatically with false stability, which is scenario-dependent.

### 17.3 Compliance and temporal propagation

For paired items:

```text
FalseStabilityRate = count(ExpectedChange=1 and ModelChange=0)
                     / count(ExpectedChange=1)

FalseInstabilityRate = count(ExpectedChange=0 and ModelChange=1)
                       / count(ExpectedChange=0)
```

Also report:

- compliance outcome accuracy;
- correct-update rate;
- correct-stability rate;
- results by materiality level;
- results by temporal-complexity category;
- results by evaluation condition; and
- abstention/invalid-output rate.

False stability measures failure to propagate a required legal change. False instability measures unnecessary answer change when the legally correct outcome should remain stable. Reporting both avoids rewarding systems that simply change every answer after any textual amendment.

### 17.4 Citation and version metrics

- version accuracy;
- citation accuracy;
- citation precision and recall where multiple authorities are expected;
- citation-drift rate;
- superseded-authority rate; and
- unsupported-citation rate.

### 17.5 Explanation metrics

- evidence correctness;
- temporal correctness;
- entailment/faithfulness;
- completeness;
- materiality-reasoning correctness;
- compliance-reasoning correctness;
- citation precision; and
- expert acceptability with uncertainty reported.

### 17.6 Agreement and uncertainty

Use an agreement statistic appropriate to the annotation design. Report confidence intervals and the denominator for every rate. Preserve an explicit unresolved/insufficient-evidence category at workflow level even if it is not a materiality label.

### 17.7 Conditional compliance-risk assessment

On an independently adjudicated scenario set, evaluate applicable-rule/version selection, obligation identification, consequence accuracy, risk-level accuracy, urgency, evidence validity, escalation/abstention, false positives, and false negatives. Report denominators, class/domain coverage, and uncertain cases. Until such gold exists, report only deterministic-contract and synthetic-fixture results—not legal risk accuracy. The existing risk baseline's expected engineering behavior is intentionally distinct from expert legal outcomes. Report textual drift and materiality separately; do not use either as a risk proxy.

---

## 18. Leakage and Statistical Controls

### 18.1 Split strategies

At minimum, consider and justify:

- random split for comparability only;
- Act-held-out split;
- amendment-event-held-out split;
- provision-lineage-held-out split;
- temporal holdout; and
- domain-held-out split.

A random split must not be the only evaluation.

### 18.2 Leakage checks

Audit across:

- exact duplicates;
- near duplicates;
- the same amendment event;
- the same Act;
- provision lineage;
- source documents;
- adjacent versions;
- paraphrased or template-generated scenarios; and
- repeated evidence passages.

Splits must be generated from grouping keys before model training. Any unavoidable overlap must be disclosed and analysed.

### 18.3 Statistical analysis

- pre-register primary metrics and comparisons before final test evaluation;
- report confidence intervals, not only point estimates;
- use paired bootstrap, McNemar's test, or another justified paired procedure for model comparisons;
- use correction or a clearly limited hypothesis family when many comparisons are made;
- report class and domain support counts;
- separate confirmatory from exploratory analyses;
- analyse annotator-agreement strata; and
- document missing, excluded, or unresolved cases.

The final procedure depends on benchmark size and outcome distributions decided in Phase 0. No power or significance claim should be made before those inputs exist.

---

## 19. Phase-by-Phase Implementation Plan

Every phase is sequentially gated. Downstream work may be prototyped for feasibility, but results must not be treated as valid until all upstream gates pass.

### Phase 0 - Research contract and novelty audit

**Objective**

Freeze the research problem, scope, terminology, novelty position, benchmark targets, and validation strategy.

**Inputs**

- current project context and manuscripts;
- Review 1 deck;
- adversarial reviews and historical materiality plan;
- verified primary literature gathered during the novelty audit; and
- legal/research-methodology reviewer input.

**Implementation tasks**

- approve the primary RQ and four core RQs;
- verify RegTrack and closest temporal/legal-change work;
- build the novelty and claim-to-evidence matrix;
- freeze in-scope corpus categories and date range;
- decide pilot, minimum, and desired benchmark targets with justification;
- resolve the ten-versus-eleven dimension discrepancy;
- separate materiality dimensions from compliance consequence;
- define success thresholds for reconstruction, applicability, agreement, and reproduction;
- approve temporal semantics and expert-validation protocols; and
- register core versus optional work.

**Outputs**

- approved research contract;
- novelty-audit matrix;
- scope and exclusions;
- terminology and temporal-semantics registry v1;
- benchmark-size/coverage decision;
- risk register;
- pre-registered primary metrics and comparison plan; and
- claim-to-evidence matrix.

**Validation checks**

- no active eCFR primary-corpus framing;
- no unsupported first-ever claim;
- materiality is intermediate, not the sole novelty;
- applicability and scenarios are first-class;
- exact label/dimension definitions are internally consistent; and
- expert roles and resources are feasible.

**Gate**

Proceed only after the research lead and qualified legal reviewer approve the research contract and novelty position.

**Failure conditions**

- closest work duplicates the intended contribution without a defensible distinction;
- corpus access or legal expertise is infeasible;
- benchmark targets are unjustified; or
- core concepts remain contradictory.

**Dependencies**

None.

### Phase 1 - Authoritative corpus/source protocol

**Objective**

Define how authoritative Indian legal evidence is identified, acquired, stored, verified, and cited.

**Inputs**

- Phase 0 scope;
- authoritative-source candidates; and
- legal-review rules.

**Implementation tasks**

- define source acceptance and priority rules without inventing unsupported hierarchy;
- define immutable raw storage and hashing;
- capture official identifiers, URLs/references, retrieval times, and media types;
- define treatment of scanned/OCR documents;
- define publication, enactment/assent, commencement, and legal-effect evidence capture;
- select the pilot corpus; and
- manually verify a sample end to end.

**Outputs**

- source protocol;
- provenance schema;
- pilot source manifest;
- immutable source artifacts with versioned provenance; and
- exception/quarantine policy.

**Validation checks**

- every pilot item has authoritative evidence and a hash;
- identifiers and retrieval records reconcile;
- OCR status is explicit;
- missing or contradictory evidence is flagged; and
- redistribution constraints are recorded.

**Gate**

Proceed only when a legal reviewer accepts the pilot sources as sufficient to support reconstruction work.

**Failure conditions**

- source authenticity cannot be established;
- relevant historical evidence is inaccessible;
- evidence is silently replaced by current consolidated text; or
- provenance cannot be reproduced.

**Dependencies**

Phase 0.

### Phase 2 - Parsing and normalization

**Objective**

Transform authoritative source artifacts into structured legal records without losing text fidelity or provenance.

**Inputs**

- approved pilot source artifacts and manifest;
- source protocol; and
- structural schema.

**Implementation tasks**

- parse legal instrument hierarchy;
- preserve exact source text and page/section anchors where available;
- normalize structural paths and cross-references;
- identify amendment verbs and candidate targets;
- record extraction method and confidence;
- quarantine parse/OCR failures; and
- create hand-checked fixtures and tests.

**Outputs**

- normalized pilot records;
- parse-error and quarantine reports;
- source-to-normalized trace map; and
- parser validation fixtures.

**Validation checks**

- exact-text and hierarchy reconciliation against the source;
- idempotent re-processing;
- stable IDs under repeated runs;
- no silent OCR correction;
- cross-reference spot checks; and
- stage counts reconcile.

**Gate**

Proceed only when the approved sample meets Phase 0 parsing/fidelity thresholds and all material discrepancies are resolved or quarantined.

**Failure conditions**

- systematic text loss;
- unstable structure or IDs;
- untraceable normalization;
- unacceptable OCR error; or
- unexplained record loss/duplication.

**Dependencies**

Phases 0-1.

### Phase 3 - Provision identity and temporal version reconstruction

**Objective**

Construct reliable provision lineages, versions, and amendment-event links.

**Inputs**

- normalized legal records;
- authoritative amendment evidence; and
- versioning rules.

**Implementation tasks**

- define stable provision and lineage identity;
- align amendment targets to affected provisions;
- create provision-version nodes;
- represent insertions, substitutions, omissions, repeals, renumbering, and splits/merges where supported;
- link every transition to authoritative evidence;
- build a manually verified reconstruction set; and
- implement point-in-time reconstruction queries during later implementation.

**Outputs**

- provision-lineage graph;
- amendment-event records;
- version-transition records;
- reconstruction gold sample; and
- unresolved-link report.

**Validation checks**

- expert comparison with authoritative documents;
- no unexplained cycles or orphan versions;
- no silent conflation of renumbering with substantive replacement;
- every transition has evidence;
- source and stage counts reconcile; and
- reconstruction error analysis is documented.

**Gate**

**Historical provision reconstruction must work.** Proceed only when a qualified legal reviewer confirms that the approved sample reconstructs the correct provision text and lineage under the Phase 0 thresholds.

**Failure conditions**

- provision identities are unstable;
- amendment targets cannot be linked reliably;
- reconstructed text conflicts with authoritative evidence;
- transition provenance is missing; or
- unresolved cases exceed the approved tolerance.

**Dependencies**

Phases 0-2.

### Phase 4 - Temporal applicability resolver

**Objective**

Determine which reconstructed provision version governs scenario S at reference date T using authoritative temporal evidence.

**Inputs**

- version graph;
- temporal-semantics registry;
- publication, enactment/assent, commencement, applicability, legal-effect, retrospective, transitional, deferred, and partial-commencement evidence where relevant; and
- expert-reviewed pilot scenarios.

**Implementation tasks**

- represent temporal facts and conditions separately from version text;
- implement applicability determinations with traceable reasoning;
- support unresolved/ambiguous outcomes and escalation;
- distinguish publication from commencement and scenario applicability;
- model retrospective and transitional effects only when supported; and
- validate determinations against legal-expert ground truth.

**Outputs**

- applicability schema and resolver specification;
- applicability gold sample;
- temporal reasoning traces;
- uncertainty/escalation report; and
- temporal error taxonomy.

**Validation checks**

- correct governing-version selection;
- complete evidence trace;
- correct handling of temporal traps in the pilot;
- no latest-version heuristic masquerading as applicability;
- unresolved cases remain unresolved; and
- expert agreement is measured.

**Gate**

**Temporal applicability must be legally validated.** No compliance scenario may enter the benchmark without an approved applicability determination or an explicit unresolved label.

**Failure conditions**

- date semantics are collapsed into `valid_from/valid_to`;
- unsupported legal hierarchy is encoded;
- governing versions cannot be expert-validated;
- evidence is incomplete; or
- ambiguous cases are forced into confident answers.

**Dependencies**

Phases 0-3.

### Phase 5 - Amendment representation and materiality annotation

**Objective**

Create structured pre/post amendment pairs and freeze a reliable four-level materiality taxonomy.

**Inputs**

- validated version pairs;
- amendment events;
- Phase 0 dimension decision;
- authoritative evidence; and
- draft annotation guideline.

**Implementation tasks**

- generate lexical and structural diffs;
- represent operation, affected text, context, and legal dimensions;
- complete the 50-pair double-annotated pilot;
- preserve individual labels, rationales, evidence spans, and confidence;
- measure appropriate inter-annotator agreement;
- adjudicate under written rules;
- revise and version the guideline; and
- re-annotate affected items after substantive revisions.

**Outputs**

- structured amendment-pair schema;
- pilot annotations;
- agreement and disagreement report;
- annotation guideline and taxonomy version; and
- frozen materiality schema.

**Validation checks**

- `High/Medium/Low/None` definitions are complete;
- inclusion/exclusion and boundary rules are usable;
- dimensions are separate from compliance consequence;
- evidence spans support rationales;
- disagreements and adjudications are traceable; and
- pilot coverage matches the approved sampling plan.

**Gate**

**The annotation taxonomy must be frozen.** Full annotation and modelling cannot begin until agreement and guideline quality meet Phase 0 criteria or the research contract is explicitly revised.

**Failure conditions**

- unresolved ten-versus-eleven dimension conflict;
- materiality and scenario consequence are collapsed;
- low agreement is unexplained;
- individual labels/rationales are discarded; or
- obsolete category labels are introduced without schema approval.

**Dependencies**

Phases 0-4.

### Phase 6 - Controlled compliance-scenario construction

**Objective**

Build expert-validated scenarios that isolate whether legally applicable change should alter a compliance answer.

**Inputs**

- validated applicability determinations;
- frozen amendment/materiality records;
- scenario schema; and
- legal-expert authorship/review.

**Implementation tasks**

- construct scenario facts and legal questions;
- assign reference dates and governing versions;
- write expected answers, consequences, and evidence-backed rationales;
- label expected change/no-change;
- cover required scenario categories;
- create paired pre/post variants with controlled facts; and
- conduct independent legal review and adjudication.

**Outputs**

- versioned scenario set;
- expert gold answers and applicability links;
- expected-change labels;
- scenario coverage report; and
- scenario-quality/adjudication log.

**Validation checks**

- scenario facts are sufficient and internally consistent;
- governing versions match Phase 4;
- expected answer and change are evidence-supported;
- material amendments with unchanged outcomes are represented;
- expected-change balance is adequate for drift metrics; and
- no invented legal example lacks authoritative support.

**Gate**

Proceed only when the approved scenario subset has independent legal validation and a stable scenario-schema version.

**Failure conditions**

- ambiguous gold answers;
- circular use of model outputs as rationales;
- wrong or unsupported applicability;
- fact drift across paired conditions; or
- insufficient coverage of stability and update cases.

**Dependencies**

Phases 0-5.

### Phase 6R - Conditional compliance-risk assessment (new deliverable)

This supplemental workstream follows scenario construction; it does not renumber the original research phases. An engineering prototype already exists in `src/temporal_legal_drift/risk/`, but its research gate remains open.

**Objective**

Assess scenario-specific obligations, consequences, urgency, and escalation **independently of drift magnitude**.

**Inputs**

- authoritative obligation and consequence evidence;
- a governing provision/version and date established by the approved applicability process;
- complete scenario facts and scope; and
- a versioned risk rule and evaluation rubric.

**Implementation tasks**

- preserve the current deterministic engine, strict scenario/output schemas, source hashes, and abstention behavior;
- audit existing obligation models against exact source spans and dates;
- author substantive, source-backed versions of the 13 scenario scaffolds without overwriting their present abstention records;
- define expected obligation, consequence, severity, urgency, risk, and expert rationale independently of engine predictions;
- test deadline boundaries, out-of-scope cases, missing facts/evidence, contradictions, and false-positive/false-negative behavior; and
- compare later intelligent assessments with the deterministic baseline only on an adjudicated benchmark.

**Outputs**

- versioned scenario/rule/evidence records and a risk evaluation set;
- reproducible baseline traces and uncertainty/escalation outcomes;
- source-to-version-to-scenario-to-risk provenance; and
- an explicit legal-validation status and error analysis.

**Validation checks**

- no risk is inferred from drift score or materiality class alone;
- unknown risk remains null and is escalated, not recoded as `None`;
- every assessed obligation and consequence has source evidence and supported applicability;
- expected answers are not copied from model outputs; and
- reported legal metrics use an independently reviewed set, not synthetic tests or scaffolds.

**Gate**

Engineering gate: deterministic contracts, provenance, abstention, and regressions pass. **Research gate: open** until substantive scenarios and applicable legal outcomes are independently validated. The existing `reports/risk/checkpoint.v1.json` records engineering checks true and research checkpoint false.

**Failure conditions**

- unsupported historical applicability or source text;
- high drift or materiality used as a risk shortcut;
- an unresolved case presented as no risk; or
- conditional demonstrations described as legal-gold benchmark results.

**Dependencies**

Phases 0-6 for research claims. The bounded engineering implementation can remain available with `legal_validation: UNVERIFIED` while those dependencies are unresolved.

### Phase 7 - Benchmark freeze and leakage audit

**Objective**

Freeze benchmark objects, releases, and leakage-resistant evaluation splits before model comparison.

**Inputs**

- reconstructed versions;
- applicability records;
- frozen materiality annotations;
- scenarios;
- risk evidence/expectations if Track G is included; and
- approved split strategy.

**Implementation tasks**

- reconcile all stage counts;
- remove or group exact and near duplicates;
- generate random, Act-held-out, amendment-event-held-out, lineage-held-out, temporal, and domain splits where feasible;
- audit source and adjacent-version leakage;
- version benchmark schemas and manifests;
- write the data card and limitations; and
- compute release checksums.

**Outputs**

- benchmark release candidate;
- frozen split manifests;
- leakage-audit report;
- data card;
- provenance manifest; and
- release-version record.

**Validation checks**

- no unexplained count mismatch;
- no same-event or lineage leakage in claimed held-out splits;
- class/domain/scenario support is reported;
- unresolved cases follow the approved policy;
- source permissions are documented; and
- test labels are access-controlled during model development.

**Gate**

**The benchmark and splits must be frozen.** Any later label, scenario, or split change requires a new release version and rerun of affected experiments.

**Failure conditions**

- random-only evaluation;
- hidden duplicates or source leakage;
- unstable labels or applicability records;
- missing release provenance; or
- inadequate test support for primary metrics.

**Dependencies**

Phases 0-6; Phase 6R is additionally required for a claimed risk benchmark track.

### Phase 8 - Baselines and materiality modelling

**Objective**

Establish strong, reproducible amendment-materiality baselines and test whether a proposed model adds value.

**Inputs**

- frozen benchmark and splits;
- baseline specifications;
- experiment protocol; and
- compute/resource constraints.

**Implementation tasks**

- implement feasible baselines from Section 14;
- verify closest-work-inspired methodology and document deviations;
- train/tune only on allowed data;
- record configurations, seeds, prompts, dependencies, and model versions;
- evaluate held-out splits;
- perform ablations and error analysis; and
- report calibration and high-materiality false negatives where applicable.

**Outputs**

- reproducible baseline runs;
- optional proposed-model runs;
- materiality metrics and confidence intervals;
- ablation/error report; and
- model cards/configuration manifest.

**Validation checks**

- identical frozen splits and label definitions;
- no test-set tuning;
- baseline implementations pass sanity checks;
- no unsupported reproduction claim;
- statistical comparisons are appropriate; and
- results do not redefine the project around classifier ranking.

**Gate**

Proceed when the baseline suite is reproducible and sufficient to contextualize temporal-drift experiments. A proposed model need not outperform all baselines for the project to continue.

**Failure conditions**

- data leakage;
- irreproducible configurations;
- missing strong baseline without justification;
- invalid metric computation; or
- test-set-driven method changes.

**Dependencies**

Phase 7.

### Phase 9 - Temporal LLM drift benchmark

**Objective**

Evaluate whether LLM compliance reasoning propagates legally required changes under controlled context conditions.

**Inputs**

- frozen scenarios and benchmark;
- selected models;
- six context conditions where feasible;
- versioned prompts/configurations; and
- answer-normalization protocol.

**Implementation tasks**

- execute controlled model runs;
- preserve prompts, context, retrieval output, and raw responses;
- normalize conclusions under the pre-registered procedure;
- score version, applicability, outcome, citation, and expected/model change;
- compute false stability and false instability;
- attribute failures by layer;
- repeat stochastic conditions as approved; and
- perform condition/model comparisons with uncertainty.

**Outputs**

- model-run manifest;
- raw and normalized assertions;
- temporal-drift metrics;
- citation/version results;
- failure-attribution analysis; and
- reproducible experiment package.

**Validation checks**

- scenario facts are held constant across paired conditions;
- only intended context variables change;
- model and decoding settings are controlled/documented;
- gold labels are independent of model output;
- metric denominators and invalid outputs are reported; and
- run artifacts reproduce aggregate results.

**Gate**

**LLM drift evaluation must be controlled and reproducible.** Headline conclusions cannot be drawn until a fresh rerun reproduces the primary metrics within the Phase 0 tolerance.

**Failure conditions**

- prompt/config drift;
- untracked retrieval changes;
- fact variation confounds pre/post comparisons;
- ambiguous answer normalization;
- missing raw outputs; or
- irreproducible metrics.

**Dependencies**

Phases 4, 6-8.

### Phase 10 - Evidence-grounded explanation evaluation

**Objective**

Determine whether explanations are faithful to authoritative evidence and temporally correct, not merely fluent.

**Inputs**

- Phase 9 assertions and explanations;
- authoritative source links;
- version/applicability/materiality/scenario gold records; and
- versioned expert rubric.

**Implementation tasks**

- extract structured explanation claims;
- check cited version and evidence alignment;
- score evidence correctness, temporal correctness, entailment, completeness, materiality reasoning, compliance reasoning, and citation precision;
- select an appropriate expert-validation subset;
- conduct blinded expert review where feasible;
- measure reviewer agreement; and
- create an explanation-drift error taxonomy.

**Outputs**

- explanation evaluation dataset/records within the benchmark release;
- automated-support metrics;
- expert evaluation results;
- disagreement analysis; and
- explanation-drift report.

**Validation checks**

- explanations trace to authoritative evidence;
- correct conclusions with stale rationales are marked as explanation drift;
- LLM-as-judge is not the sole legal evaluator;
- expert rubric and sample selection are documented; and
- uncertainty and disagreement are reported.

**Gate**

**Explanations must be evidence-grounded.** No explanation-quality claim is permitted if version, citation, or authoritative-evidence support is not independently checked.

**Failure conditions**

- fluency substituted for faithfulness;
- wrong version or date accepted;
- unsupported legal entailment;
- no expert validation; or
- opaque evaluation criteria.

**Dependencies**

Phases 4, 6-9.

### Phase 11 - Expert validation and reproducibility release

**Objective**

Validate the complete research chain independently and release reproducible benchmark artifacts.

**Inputs**

- frozen benchmark;
- all experiment outputs;
- expert protocols;
- source/provenance manifest; and
- fresh execution environment.

**Implementation tasks**

- conduct independent legal review of sampled reconstruction, applicability, materiality, scenarios, consequences, citations, and explanations;
- reproduce data transformations and metrics from source manifests where redistribution permits;
- run experiments in a fresh environment;
- reconcile paper tables/figures to result manifests;
- finalise data/model cards, limitations, and legal/ethical statement;
- verify citations and novelty claims from primary sources; and
- archive checksums and release versions.

**Outputs**

- independent expert-validation report;
- reproducible benchmark release;
- environment and experiment manifests;
- verified result tables;
- final claim-to-evidence matrix; and
- documented limitations/failure cases.

**Validation checks**

- independent reviewers can trace sampled conclusions to evidence;
- fresh-environment reproduction meets the Phase 0 tolerance;
- release counts/splits/checksums reconcile;
- reported results match generated outputs;
- no unverified citation or novelty claim remains; and
- core completion criteria are demonstrated.

**Gate**

**Independent expert validation and fresh-environment reproduction must succeed.** Failure blocks core project completion and publication claims.

**Failure conditions**

- material expert disagreement left unresolved or undisclosed;
- irreproducible metrics;
- missing provenance;
- paper/release mismatch;
- source-rights violation; or
- unsupported legal or novelty claims.

**Dependencies**

Phases 0-10.

### Phase 12 - Optional monitoring agent

**Objective**

Demonstrate a human-in-the-loop monitoring extension after the core benchmark and evaluation framework are validated.

**Inputs**

- validated acquisition, reconstruction, applicability, materiality, explanation, and escalation components; and
- approved operational-risk controls.

**Implementation tasks**

- monitor approved authoritative sources;
- detect candidate amendments;
- reconstruct affected versions;
- determine or escalate applicability;
- classify materiality;
- generate evidence-grounded impact reports;
- assign confidence;
- escalate uncertain/high-impact changes; and
- maintain immutable audit logs and human approval records.

**Outputs**

- optional monitoring prototype;
- audit and escalation records;
- source-outage/contradiction tests;
- duplicate-alert controls; and
- separate agent evaluation report.

**Validation checks**

- no silent autonomous legal conclusion;
- provenance and confidence are mandatory;
- uncertain cases fail safely;
- duplicate processing is idempotent;
- human approval is enforced; and
- agent results are not mixed with benchmark/model results.

**Gate**

Proceed to any demonstration only after Phase 11 passes and operational controls are reviewed. This gate is not part of core completion.

**Failure conditions**

- bypassed human review;
- missing audit trail;
- unsupported source or applicability inference;
- silent failure during source outage; or
- presentation of the prototype as autonomous legal advice.

**Dependencies**

Phase 11.

---

## 20. Phase Gates

| Phase | Non-negotiable gate |
|---|---|
| 0 | Research contract, novelty audit, scope, benchmark targets, concepts, and validation thresholds approved |
| 1 | Pilot authoritative-source protocol accepted by legal review |
| 2 | Parsing fidelity and provenance meet approved thresholds |
| 3 | Historical provision reconstruction works and is expert-validated |
| 4 | Temporal applicability is legally validated; ambiguity is escalated |
| 5 | Four-level taxonomy and dimensions are frozen after the double-annotated pilot |
| 6 | Controlled scenarios and expected-change labels receive independent legal validation |
| 6R | Risk remains separate from drift; source-backed obligations, scenario outcomes, abstention, and escalation are validated before legal-risk claims |
| 7 | Benchmark, schemas, release version, and leakage-resistant splits are frozen |
| 8 | Baselines are reproducible; proposed-model success is not required |
| 9 | LLM drift evaluation is controlled and reproducible |
| 10 | Explanation claims are grounded in correct evidence and expert-validated on an approved subset |
| 11 | Independent expert validation and fresh-environment reproduction succeed |
| 12 | Optional agent passes human-approval, provenance, audit, and fail-safe controls |

When a gate fails, downstream results remain exploratory and must not be used for final claims. A gate may be revised only through a recorded research-contract amendment.

---

## 21. Reproducibility

The future implementation must record:

- source artifact identifiers and hashes;
- acquisition and transformation versions;
- temporal-semantics registry version;
- schema versions;
- annotation-guideline version;
- scenario-schema version;
- benchmark release version;
- split manifests;
- prompt and evaluator versions;
- model/provider identifiers;
- environment/dependency lock;
- seeds and decoding settings where available;
- raw and normalized outputs;
- metric definitions and scripts;
- exclusion and adjudication logs; and
- result-table generation lineage.

Required quality controls:

1. canonical terminology registry;
2. temporal semantics registry;
3. schema versioning;
4. annotation-guideline versioning;
5. scenario-schema versioning;
6. prompt/config versioning;
7. benchmark release versioning;
8. immutable provenance chains;
9. stage-count reconciliation;
10. leakage audits;
11. legal-review gates;
12. drift-metric definitions;
13. expert-validation protocol;
14. claim-to-evidence matrix;
15. artifact consistency checks; and
16. fresh-environment reproduction.

---

## 22. Legal and Ethical Considerations

- The benchmark is a research resource and not legal advice.
- Qualified legal experts must validate temporal applicability, gold compliance consequences, and an appropriate explanation subset.
- The project must not infer an unsupported hierarchy of Indian legal sources or dates.
- Ambiguity, disagreement, insufficient evidence, and contested interpretation must be preserved and reported.
- Source terms, copyright, redistribution, and institutional requirements must be reviewed before release.
- If raw source redistribution is unsuitable, release permitted identifiers, hashes, extraction procedures, and derived records with clear limitations.
- Annotator qualifications, conflicts, privacy, compensation, and consent must follow the approved institutional protocol.
- Model outputs must not become annotation ground truth.
- Any use of commercial LLM APIs must document data-handling constraints and avoid sending restricted data.
- The optional agent must use human approval and must not silently publish autonomous legal conclusions.

---

## 23. Optional Agent

The autonomous **legal-conclusion agent** is explicitly secondary. It is not required for scientific validity, TRL 4 core completion, or the benchmark release. The scheduled, incremental **source-acquisition service** required by §0.7 is a separate engineering deliverable and must not publish legal conclusions.

Only after Phase 11 succeeds may it:

- monitor approved authoritative sources;
- detect amendments;
- reconstruct versions;
- classify materiality;
- determine or escalate temporal applicability;
- generate evidence-grounded impact reports;
- assign confidence;
- escalate uncertain/high-impact changes; and
- maintain audit logs.

The agent must never:

- bypass provenance;
- force an answer when applicability is unresolved;
- treat model confidence as legal certainty;
- publish a legal conclusion without required human approval; or
- obscure which component produced an error.

---

## 24. Known Risks and Current Project Issues

| Priority | Risk / issue | Required treatment |
|---|---|---|
| Resolved foundation issue | No implementation existed at the initial audit | Phase 0-11 engineering infrastructure now exists; do not confuse implemented machinery or the non-gold smoke run with missing gold data and scientific evaluation |
| Critical | A technical release dry run exists but no frozen scientific benchmark | Do not report silver labels, scaffolds, or technical-release counts as legal-gold benchmark performance |
| Critical | Historical Indian provision reconstruction may be difficult or incomplete | Pilot source availability and reconstruction before modelling |
| Critical | Graph v4 contains machine-checked amendment fragments, not complete historical consolidations, and no independently legally validated transitions are established | Keep fragments distinct from complete historical consolidations; resolve source/date evidence and validate before legal claims; use the graph-v4 checkpoint for current counts |
| High | Phase 4 has 19 original rule disagreements, five confirmed extraction/alignment defects, and no supported real `None` class | Audit source spans, preserve frozen v1 silver data, abstain where incomplete, and do not report rule agreement as legal accuracy |
| High | Risk implementation covers 13 abstention scaffolds and two conditional Section 19 demonstrations, not 13 substantive expert-gold outcomes | Author source-backed scenario facts/obligations, retain unknown risk as null, and independently validate expected consequences |
| High | RAG can consume graph-v4 fragment alignment, but risk and real-corpus applicability are not legally integrated | Preserve the bounded graph-consumer interface, require approved temporal facts for applicability, and test any risk integration before claiming validated historical-law reasoning |
| Critical | Temporal applicability may require nuanced legal interpretation | Use a temporal-semantics registry, qualified review, and unresolved/escalation outcomes |
| High | Older repository notes centre eCFR and a standalone materiality classifier | Treat eCFR material as historical methodology only; it must not define the active project |
| High | Ten-versus-eleven materiality-dimension discrepancy | Resolve in Phase 0 and separate compliance consequence from materiality |
| High | Materiality and expected compliance change can be incorrectly conflated | Store and evaluate them as separate labels |
| High | Closest-work position, including RegTrack and recent temporal benchmarks, is not yet formally verified | Complete the primary-source novelty audit before implementation/publication claims |
| High | Expert annotation and validation capacity may limit scale | Set justified minimum/desired targets and report limitations |
| High | Leakage across Acts, amendment events, provision lineages, documents, and adjacent versions | Freeze group-aware splits and audit before modelling |
| High | LLM/provider changes can break reproducibility | Record versions, dates, prompts, configs, raw outputs, and rerun tolerance |
| Medium | Current and Professional Edition DOCX files are near-duplicates, with an older backup | Choose a manuscript source of truth later; do not treat backups as separate evidence |
| Medium | `paper/flowsight_transactions_april_2026.csv` is not CSV and is byte-identical to the review PDF | Never treat it as a dataset; correct/remove only under separate explicit authorization |
| Medium | `paper.zip` is an archive snapshot matching current archived files | Treat it as a snapshot, not a newer or independent source |
| Medium | Citation verification remains required, especially for recent/emerging work | Verify bibliographic and novelty claims from primary sources before submission |
| Medium | Local Git history and `origin` are present; remote CI and latest remote state were not fetched or verified in the 2026-10-12 audit | Check remote state separately before claiming CI or synchronization; do not treat local tracking status as a remote verification |
| Medium | LaTeX and DOCX manuscript coverage differ | Choose and synchronize a publication source of truth under a separate documentation task |

---

## 25. Target Repository Layout

The tree below remains a **target** layout, not an inventory of folders already present. The actual package also contains `ingestion/`, `amendment_extraction/`, `materiality/`, `rag/`, `risk/`, and `evaluation_agent/`; the React/Vite source is in `frontend/` and compiled assets in `web/`. Phase 5-8 research artifacts remain non-gold workloads or dry runs. Phase 9-10 contain an executed non-gold LLM smoke run and automated support diagnostics, not a frozen benchmark or legal-quality result. Phase 11 contains saved engineering-reproduction evidence but no independent expert validation.

```text
project/
  context.md
  plan.md
  README.md
  pyproject.toml or equivalent environment lock
  configs/
    experiments/
    prompts/
    temporal_semantics/
  data/
    raw/                    # immutable authoritative evidence
    normalized/             # parsed legal structure
    interim/                # lineages, versions, temporal facts, pairs
    annotations/            # individual and adjudicated records
    scenarios/              # controlled scenario objects
    releases/               # frozen benchmark releases
  schemas/
    source/
    temporal/
    annotation/
    scenario/
    evaluation/
  src/
    acquisition/
    parsing/
    identity/
    versioning/
    applicability/
    amendment_representation/
    annotation/
    scenarios/
    baselines/
    models/
    llm_evaluation/
    explanations/
    metrics/
    reproducibility/
    webapp/                 # local connected research APIs
    monitoring/             # optional
  frontend/                 # React/Vite source (already present)
  web/                      # generated frontend assets (already present)
  tests/
    fixtures/
    unit/
    integration/
    legal_validation/
    leakage/
    reproducibility/
  experiments/
  reports/
  paper/
```

---

## 26. Core Completion Criteria

The core project is complete only when a fresh, documented run can:

1. ingest authoritative Indian legal evidence;
2. reconstruct provision versions;
3. identify amendment events;
4. determine temporal applicability;
5. construct pre/post amendment pairs;
6. classify materiality using the frozen taxonomy;
7. construct controlled compliance scenarios;
8. evaluate LLM reasoning across legal versions and context conditions;
9. measure false stability and false instability;
10. measure version accuracy, citation drift, and explanation drift;
11. generate evidence-grounded explanations;
12. reproduce reported metrics from frozen manifests; and
13. pass independent legal-expert validation.

For the newer compliance-risk deliverable, a supported fresh run must additionally select an evidence-backed applicable obligation, apply it to structured scenario facts, report consequence/severity/urgency, preserve unknown risk and escalation, and reproduce risk metrics on independently adjudicated cases. The present deterministic risk engine and two conditional demonstrations do **not** satisfy this research condition. Risk metrics must not be derived from textual drift percentages.

Additional completion conditions:

- no core gate remains failed or undocumented;
- benchmark and scenario releases are versioned;
- leakage audits pass for claimed held-out evaluations;
- all headline paper claims map to verified evidence or reproducible results;
- legal and ethical limitations are explicit; and
- the monitoring agent is not required.

---

## 27. Open Research-Readiness Checklist

Engineering implementation has already begun. The unchecked items below are **not claims that no code exists**; they are open approvals and evidence requirements before scientific benchmark, legal-validity, or TRL 4 claims. Resolve or explicitly defer each with an owner and rationale; do not retroactively mark it complete merely because an engineering gate passed.

### Research contract

- [ ] Approve the primary RQ and RQ1-RQ4.
- [ ] Approve the core novelty wording.
- [ ] Confirm that materiality is an intermediate component.
- [ ] Confirm that the optional agent is outside core completion.
- [ ] Record TRL 2 starting status and TRL 4 target evidence requirements.

### Novelty and literature

- [ ] Verify RegTrack from primary sources.
- [ ] Verify the closest legal-change/materiality benchmark work.
- [ ] Verify recent temporal legal reasoning and changing-law benchmarks.
- [ ] Compare task, corpus, temporal model, scenarios, metrics, and release artifacts.
- [ ] Freeze the claim-to-evidence matrix.

### Corpus and evidence

- [ ] Approve authoritative-source protocol.
- [ ] Approve legal domains, instruments, and date range.
- [ ] Confirm access to historical provision and commencement evidence.
- [ ] Define raw-source hashing, provenance, OCR, and quarantine rules.
- [ ] Review redistribution and institutional constraints.

### Benchmark design

- [ ] Approve the 50-pair pilot or document the reason for changing it.
- [ ] Set justified minimum and desired benchmark targets.
- [ ] Set class, domain, amendment, and temporal-complexity coverage targets.
- [ ] Approve required scenario categories and expected-change balance.
- [ ] Approve split strategies and leakage grouping keys.

### Concepts and schemas

- [ ] Freeze definitions of materiality, temporal applicability, and compliance consequence.
- [ ] Resolve the ten-versus-eleven dimension discrepancy.
- [ ] Confirm `High/Medium/Low/None` as the active taxonomy.
- [ ] Define temporal facts beyond `valid_from/valid_to`.
- [ ] Approve provision-lineage, applicability, annotation, scenario, and evaluation schemas.
- [ ] Version the temporal-semantics and terminology registries.

### Validation and statistics

- [ ] Confirm two independent legal annotators and an adjudication path.
- [ ] Choose agreement measures appropriate to the final annotation design.
- [ ] Approve expert-validation sampling and rubric.
- [ ] Pre-register primary metrics, denominators, comparisons, and confidence intervals.
- [ ] Define fresh-environment reproduction tolerance.
- [ ] Define drift-metric normalization and answer-mapping rules.
- [ ] Define a risk evaluation rubric and independent expected-outcome protocol; keep unknown risk distinct from `None`.
- [ ] Specify risk false-positive/false-negative denominators and abstention reporting on source-backed cases.

### Implementation readiness

- [ ] Reconcile the current local Git baseline with the remote and inspect actual CI runs before claiming remote verification.
- [ ] Lock and document the implementation environment, including frontend dependency resolution.
- [ ] Review existing test/CI coverage, data-access, and secret-management policies; add missing checks only through a scoped change.
- [ ] Confirm compute/API budget and provider data-handling constraints.
- [ ] Assign owners and dependencies for the remaining research gates, including Phase 6R.

Until this checklist and the Phase 0 gate pass, all technical work should be treated as exploratory prototyping rather than valid benchmark construction.

## Implementation status note (2026-10-12)

The live-pipeline sprint (daily e-Gazette/India Code pipeline, drift-metrics-v3, query-specific clause comparison and UI) is recorded in `docs/implementation-plan.md` and `docs/verification.md`. This note changes no research acceptance criterion. Live e-Gazette ingestion has not yet succeeded (TLS chain issue). The legal/research gate remains UNVERIFIED.

## Implementation status note (2026-10-13, rag-answer-v2)

The assistant's evidence selection and its four determinations are described in ADR 0014 and `reports/rag_audit/integrated_audit.v1.md`. This changes no research acceptance criterion. Legal validation remains UNVERIFIED.

## Implementation status note (2026-10-13, rag-answer-v3)

The Legal Change Fingerprint is described in ADR 0015 and `reports/fingerprint/fingerprint_report.v1.md`. This changes no research acceptance criterion. Legal validation remains UNVERIFIED.
