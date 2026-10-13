# Implementation roadmap (Phase 0–10)

**Purpose.** This is the actionable execution roadmap: implementation order, dependencies, gates, current status and next work. The research contract and completion criteria live in [../plan.md](../plan.md); the two must agree. Every status cell points to code, an artifact, a test, or a labelled saved report. A file existing is not completion.

- **Revision:** 2026-10-12, rev 3 (adds the S0–S6 sprint status).
- **Git baseline:** `c0832d2` on `main`, equal to `origin/main`. Remote CI passed on `c0832d2`, `a683a1e`, `74aef24`, `58c9868` and `a2d03b1`; all four jobs were observed.
- **Active release:** `data/releases/active_release.json` → v0.5.0, bound to `53ce12d`.
- **Evidence sources:** the per-phase checkpoint reports linked below, [claims_evidence_matrix.md](claims_evidence_matrix.md), and [verification.md](verification.md).

Status vocabulary:
- **VERIFIED** — implemented, with tests or gates observed passing.
- **UNDER-TESTED** — implemented, but material behaviour lacks tests.
- **CONDITIONAL** — implemented only as a stipulated or conditional demonstration.
- **MISSING** — proposed but not implemented.
- **BLOCKED-SOURCE** — needs better source evidence.
- **BLOCKED-LEGAL** — needs independent legal validation.

## Current versus target inventory

| Component | Current state (evidence) | Status | Gap to target |
| --- | --- | --- | --- |
| Reproducibility | Commit-bound releases v0.2.1–v0.5.0; restore, rebuild and refusal tests (`tests/unit/test_reproducibility.py`); CI runs Python 3.11–3.13 plus a frontend build-diff job | VERIFIED | Re-cut a release after each code/schema change |
| Source ingestion | `ingestion/` registry, discovery, downloader, dedup/revision, failure log, `HUMAN_REVIEW_PENDING` queue (`tests/unit/test_ingestion.py`); 100 tracked PDFs | VERIFIED (bounded) | Not comprehensive India Code coverage; no continuous monitoring (out of scope until Phase 9 passes) |
| Text fidelity | Layout furniture v1, OCR candidate v1 (IT 2008), `source_text_unreliable` | VERIFIED (detection) / BLOCKED-SOURCE (IT 2008 text) | OCR needs manual verification against page images |
| Amendment extraction | v2.2: 1,150 events, 232 UNKNOWN, 1,953 unresolved records (`reports/phase2/extraction_v2.2_checkpoint.md`) | VERIFIED (machine) | Nested `(A)/(i)` and "respectively" clauses abstain; commencement extracted only Act-wide |
| Temporal graph | v4: 136 transitions, 86 machine-checked, 5 dated, 1,014 unresolved, 0 human-validated (`reports/phase3/temporal_graph_v4_checkpoint.md`) | VERIFIED (machine) / BLOCKED-LEGAL | 218 same-provision candidates need ordered reconstruction |
| Applicability | `applicability/resolver.py` with approved-fact semantics; 10 tests covering publication-only, assent-only, deferred, partial, transitional, retrospective, conflicting, uncertain and multiple-active cases | VERIFIED (engine) / BLOCKED-LEGAL | No approved facts exist for the real corpus |
| Graph consumer | `versioning/consumer.py` (`graph-consumer-v1`), used by RAG drift | VERIFIED | Risk does not consume it |
| Materiality | Silver v1 frozen; re-assessment v2.5 (50 cases); LLM v2 (37/50 valid, High-biased) (`reports/materiality/phase_d_checkpoint.md`) | VERIFIED (silver workflow) / BLOCKED-LEGAL | None class unevaluated; no gold labels |
| Compliance risk | Deterministic engine, 26 tests, 13 abstention scaffolds, 2 Section 19 demonstrations (`reports/risk/phase_e_checkpoint.md`) | VERIFIED (engine) / CONDITIONAL (demonstrations) | Substantive scenarios need supported facts and outcomes |
| Explainable LLM | RAG answers with honest labels and fallback disclosure; explanation-support *evaluator* (`explanations/evaluator.py`) | UNDER-TESTED | **MISSING:** a structured explanation contract over the full chain (provision/version/date, amendment, materiality status, obligation, consequence, risk, citations, uncertainty, escalation) with an anchor validator |
| Orchestration | Components connected by files; no run record | MISSING | Versioned end-to-end run with correlation IDs, stage provenance, idempotent restart and safe failure |
| Human review / audit | Review states exist as fields only | MISSING | Append-only reviewer actions (identity, timestamp, prior state, reason) through the API; a click is never legal approval |
| Dashboard | RAG assistant, corpus, drift explanation, risk tab; honest labels (`reports/rag/phase_f_checkpoint.md`) | UNDER-TESTED | Review workflow views; no browser or mobile audit yet |
| Benchmark | Phase 7 technical dry run on older inputs; freeze refused without gold | CONDITIONAL / BLOCKED-LEGAL | Engineering dry run on current inputs with a split and leakage audit |

## Phases

| Phase | Scope | Gate | Status | Next work |
| --- | --- | --- | --- | --- |
| 0 Baseline & reproducibility | Releases, restore, locks, CI | Clean checkout reproduces inputs, tests and gates; refusal paths tested | **PASS** (v0.5.0; CI green on `c0832d2`) | New release per code change |
| 1 Source ingestion | Registry, dedup, versions, failures, review queue | Duplicates reused, revisions versioned, failures recorded, queue populated | **PASS (bounded)**; audit in this revision | Continuous discovery is out of scope |
| 2 Fidelity & extraction | OCR/layout, compound clauses, operands, reasons | Accepted events traceable to reliable text; failures have reasons | **PASS (machine)** | Manual OCR verification (BLOCKED-SOURCE) |
| 3 Temporal graph | Graph v4, policy, point-in-time | Counts reconcile; unsupported versions abstain | **PASS (machine)** | Ordered same-provision reconstruction |
| 4 Materiality | Silver triage, LLM, baselines | Reproducible, evidence-linked triage and abstention | **PASS (silver)** | Gold labels (BLOCKED-LEGAL) |
| 5 Compliance risk | Deterministic conditional risk | Deterministic and evidence-linked; unknown is null | **PASS (engine)** | Supported scenarios (BLOCKED-LEGAL) |
| 6 Explainable LLM | Structured explanation contract and validator | Structurally valid, evidence-bounded, fallback explicit | **PASS** (ADR 0005, `tests/integration/test_orchestration.py`) | Expert explanation review (BLOCKED-LEGAL) |
| 7 Orchestration | End-to-end run with provenance | One traced run source → review state; unreliable source ends unresolved | **PASS** (ADR 0006, `run-case`) | Approved temporal facts (BLOCKED-LEGAL) |
| 8 Dashboard & review | Review workflow and audit trail | Tasks work; API and UI states reconcile; no approval implied | **PASS (headless)** (ADR 0007, `tests/integration/test_review_api.py`) | Qualified reviewer identity |
| 9 Benchmark | Engineering dry run v2, splits, leakage | Manifests, split audit, data card, metric definitions reproducible | Not started | Gold benchmark is BLOCKED-LEGAL |
| 10 Final reproducibility | Full clean-environment run, docs | Every claimed engineering result reproduces | Not started | — |

## Sprint S0–S6 (plan.md §0.6–0.12) — status 2026-10-12

| Stage | Result | Evidence |
| --- | --- | --- |
| S0 Freeze & inspect | **PASS** — baseline `62f7bfd`, 156 tests, gates exit 0, v0.6.0 active, CI green on `af16acd` | `docs/verification.md` |
| S1 Source feasibility | **PASS (scoped)** — India Code via DSpace REST; e-Gazette `ACCESS_LIMITED` (manual import); served-rendition checksum addendum | `docs/sprint/s1_source_access_decision.v1.md` |
| S2 Scheduled incremental pipeline | **PASS** — 24 h gate, cross-process lease, revisions, stage cache, review queue, no auto-activation; real bounded run took 3 documents to review and a repeat reprocessed nothing | `monitoring/`, `tests/unit/test_monitoring.py`, ADR 0008, `docs/operations/source_monitoring_runbook.md` |
| S3 Score contract | **PASS** — drift-metrics-v2: no hidden substitutes, removed a corpus-specific term hack, spelling normalisation, unavailable states, recomputable trace, frozen fixtures | `rag/metrics.py`, `tests/unit/test_drift_scoring.py` |
| S4 Clause comparison | **PASS** — comparison-record-v1 with support class, honest roles, spans, abstention codes | `rag/rag_pipeline.py`, `tests/unit/test_rag.py` |
| S5 UX integration | **PASS (headless)** — comparison view, unavailable states, source health, shareable links; desktop 1440px and 500px screenshots | `frontend/src/ComparisonPanel.jsx`, `tests/unit/test_frontend_contract.py` |
| S6 Integrated release | Release cut after this update (see `data/releases/active_release.json`) | `docs/verification.md` |

Not achieved in the sprint:
- page-region (PDF-coordinate) highlighting; it is explicitly declared unavailable;
- live e-Gazette synchronization;
- an always-on deployment host (the runbook names the requirement);
- browser keyboard and screen-reader testing;
- viewports below 500px.

## Open decisions

1. **Who may record a legal-review decision.** Until a qualified reviewer is identified, reviewer actions are recorded as `reviewer_role: unqualified_engineering_review`, and the legal gate stays UNVERIFIED.
2. **Whether the risk engine consumes graph applicability.** This needs a risk schema v2 and an expert-reviewed applicability policy. It is deferred.
3. **Whether IT 2008 OCR text may replace the embedded text layer** after manual verification. This needs a reviewer.

## Change log

- **rev 2 (2026-10-12).** Re-based on the Phase 0–10 architecture target supplied by the project lead. Its historical counts were replaced by verified current figures. The full original proposal document was not attached to the request, so it is not stored. This revision supersedes rev 1 (audit-based next-work list, base `6803087`), which remains in Git history.

## Live-pipeline sprint (Phases 1–6) — status 2026-10-12

| Phase | Result | Evidence |
| --- | --- | --- |
| 1 Access + 24 h contract | **PASS (scoped)** — e-Gazette `SUPPORTED_FRAGILE_HTML_DISCOVERY` | `docs/sprint/s1_source_access_decision.v2.md` |
| 2 State machine + dedup | **PASS** — 16 monitoring tests | `monitoring/service.py`, ADR 0009 |
| 3 Drift methodology | **PASS** — drift-metrics-v3, fixtures v2, config parity test | `docs/methodology/drift_score.v3.md` |
| 4 Clause evidence | **PASS** — operation, provision, event ID, hashes, offsets, `AMBIGUOUS_CANDIDATES` | `rag/rag_pipeline.py`, `tests/unit/test_rag.py` |
| 5 UI | **PASS (headless + jsdom)** — version status, four separate indicators, clause metadata, PDF-at-page, legend, score explanation | `frontend/src/{ResultInsights,SourceHealth,ComparisonPanel}.jsx`, `frontend/src/__tests__/` |
| 6 E2E + ops | **PASS (mocked)**. Live e-Gazette: **FAILED (TLS chain)**, recorded and not bypassed | `tests/integration/test_monitoring_e2e.py`, `docs/verification.md` |

## Follow-up sprint: e-Gazette TLS, live ingestion, deployment, accessibility (2026-10-12)

| Item | Result | Evidence |
| --- | --- | --- |
| e-Gazette `CERTIFICATE_VERIFY_FAILED` | **FIXED** — pinned verified Gen-Y intermediates, full verification kept | ADR 0010, `tests/unit/test_tls.py` |
| Live download → storage → parse → review queue | **PASS (audited manual import)**; scheduled discovery live `OK` (20 rows, none eligible) | `docs/sprint/s1_source_access_decision.v3.md` |
| Always-on deployment + missed-run alerting | **PASS (tests)**; no host provisioned | ADR 0011, runbook, `tests/unit/test_deploy.py` |
| Real-browser keyboard / AX tree / sub-500px | **PASS after 2 fixes**; no listening test | `frontend/scripts/browser-a11y-check.mjs`, `docs/verification.md` |

## Follow-up sprint 2 (2026-10-13, v0.10.0)

| Item | Result | Evidence |
| --- | --- | --- |
| CI for v0.9.0 | **PASS** (run 38281312499, all 4 jobs) | GitHub Actions API |
| Garbled-Hindi gate | **PASS** — all Devanagari text-layer lines and mojibake withheld; real-PDF regressions | ADR 0012, `tests/unit/test_text_quality.py` |
| Commencement policy | **PASS (engineering)**; no review mechanism yet | ADR 0013, `tests/unit/test_commencement.py` |
| Always-on deployment | **UNVERIFIED** — no authorized host; units verified under real systemd in a container | runbook, `deploy/container-check/run.sh` |
| Scheduled live run | see `docs/verification.md` (session scheduler, laptop) | observation log |
| TLS after renewal | **UNVERIFIED** — not yet renewed | `docs/verification.md` |
| VoiceOver/NVDA pass | **UNVERIFIED** — needs the user to enable VoiceOver AppleScript control | `frontend/scripts/voiceover-reading-pass.sh` |

## RAG integration sprint (2026-10-13, rag-answer-v2)

| Phase | Result | Evidence |
| --- | --- | --- |
| 1 Audit and failure taxonomy | **DONE** — 24 cases, 15 strata, RC1–RC5 | `reports/rag_audit/baseline_audit.v1.md` |
| 2 Evidence and contract | **PASS** — question frame, version evidence, rag-answer-v2 schema | ADR 0014, `schemas/rag/rag_answer.v2.schema.json` |
| 3 Determinations | **PASS** — 24/24 expected states; materiality only on exact silver match; risk only via registry | `tests/unit/test_rag_v2.py`, `tests/integration/test_rag_audit.py` |
| 4 Answer generation | **PASS** — deterministic grounded composition; model answers cite every excerpt seen | `rag/compose.py` |
| 5 Frontend | **PASS (jsdom and real Chrome)** — cards, scenario rerun, evidence list; focus and 320px checks | `frontend/src/Determinations.jsx`, `frontend/src/__tests__/answer_v2.test.jsx` |
| 6 Validation and release | 0/0/0 errors; held-out 86/86 pairing | `reports/rag_audit/integrated_audit.v1.md` |

## Legal Change Fingerprint sprint (2026-10-13, rag-answer-v3)

| Phase | Result | Evidence |
| --- | --- | --- |
| Audit and design | Legacy scoring traced; clause-level reconstruction feasible for 86/86 transitions | ADR 0015, methodology v1 |
| Contract | rag-answer-v3, determinations-v2, schema v3; v2 schema kept | `schemas/rag/rag_answer.v3.schema.json` |
| Extraction and scoring | Wording and rule drift; 0 invariant violations over 86 transitions | `reports/fingerprint/` |
| Scenario evaluation | Outcome drift with controlled sets; facts requested when missing | `tests/unit/test_fingerprint.py` |
| UI | Fingerprint cards and panels; UI values equal the API's in real Chrome; 320px fits | `frontend/src/Fingerprint.jsx`, `fingerprint.test.jsx` |
| Release | See `docs/verification.md` | — |
