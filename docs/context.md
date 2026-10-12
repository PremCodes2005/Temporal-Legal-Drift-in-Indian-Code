# Current repository context

Audit basis: checkout `68030875a719aa626fb05f294880de2953084781` on `main`, inspected 2026-10-12. **Verified** means observed in checked-in code, contracts, artifacts, or a command executed during this audit. Saved reports are identified as *reported by artifact*, not independently revalidated legal conclusions. **Inference**, **unknown**, and **proposal** are called out separately.

## What is actually built

| Component | Verified implementation and evidence | Limit |
| --- | --- | --- |
| Acquisition/ingestion | `acquisition/`, `ingestion/`, `corpus/`; source registry, bounded download, hash/dedup, immutable records and review queue. `reports/phase1/ingestion_checkpoint.v1.json` reports a 25-document pipeline checkpoint. | Approval and completeness of the legal corpus are not established. |
| Parsing and amendment extraction | `parsing/`, `amendment_extraction/`; normalized provenance and explicit unresolved reasons. `reports/phase2/amendment_extraction_checkpoint.v1.json` records 37 amending Acts, 864 machine events, 1,525 unresolved reason records. | Real-corpus legal accuracy is null; IT 2008 PDF extraction has documented glyph problems (`reports/phase2/gate_status.md`). |
| Temporal graph/applicability | `versioning/temporal_graph.py`, `applicability/resolver.py`; source-linked entities, transitions, point-in-time query, abstention for missing/ambiguous commencement. Saved Phase 3 checkpoint records 100 sources, 5,657 provisions, 5,891 versions, 66 machine-validated transitions, 6 dated transitions, 747 unresolved transitions. | These are amendment-fragment transitions, not complete historical consolidations; 0 independently legally validated transitions (`reports/phase3/gate_status.md`). The separate resolver requires approved temporal facts; live candidate facts are unreviewed. |
| Materiality | `materiality/` and `configs/annotation/proposed_materiality_rubric.v1.json`; four draft classes, silver-label and disagreement workflows, optional structured LLM assessment. | 50 frozen **machine** labels, 31/50 rule agreements, 19 original disagreements; no legal gold or real `None` example. See `reports/materiality/implementation_status.md`. |
| Scenarios, benchmarks, evaluation | `scenarios/`, `benchmark/`, `baselines/`, `llm_evaluation/`, `explanations/`, `metrics/`; versioned dry-run artifacts and 78 controlled LLM/explanation records are reported. | Phase 7 scientific benchmark freeze refused; Phase 8 trained/evaluated models absent; Phase 9/10 legal performance unscored (`reports/phase7`–`phase10`). |
| Compliance risk | `risk/`; deterministic scenario/rule/evidence models, assessment service, CLI and API. | Thirteen source scenarios are structured abstention scaffolds, plus two conditional Section 19 demonstrations; no expert legal validation or corpus-wide risk model (`reports/risk/checkpoint.v1.md`). Risk does not consume drift scores. |
| RAG/web | `rag/`, `webapp/`, `frontend/src/`; single-prompt query API, hybrid local retrieval, optional live India Code supplement, Ollama/OpenAI-compatible generation with extractive fallback, React UI. | Local embeddings are deterministic 256-dimensional feature hashes, **not** a pretrained semantic encoder. Live current-law sections are not historical pairs. Model availability and answer quality were not exercised in this audit. |

## Data flow and interface

`configs/corpus/pilot_v1.json` and authoritative URLs → acquisition/PDFs in `data/corpus/pdfs/` → parsing/normalized evidence → amendment events → version graph and applicability candidates → silver materiality/scenario and risk records → retrieval/evaluation → API → React UI. This is a set of implemented paths, not proof that every source traversed every stage with legal approval.

The Python package is `temporal-legal-drift` 0.6.0, Python >=3.11, entrypoint `tldrift` (`pyproject.toml`). Core dependencies are empty; optional extras are `pypdf>=5.0` and `chromadb>=0.5`. `frontend/package.json` declares React, React DOM, Vite, and Vite React plugin at `latest`; `frontend/vite.config.js` builds into `web/` and proxies `/api` and `/corpus` to `127.0.0.1:8765`. The backend uses `http.server` (`webapp/server.py`), not a framework. Neither an external SQL database nor a complete India Code database mirror was found. The optional Chroma backend is selected by `TLD_VECTOR_BACKEND=chroma`; default storage is a versioned local JSON index under `data/runtime/` (`rag/retriever.py`). Its identity includes corpus and graph fingerprints and refuses an incompatible index. **Integration boundary:** the RAG index currently reads `data/interim/version_graph.v1.json`, not the newer `temporal_legal_knowledge_graph.v2.json`; risk assessment reads a versioned obligation registry rather than invoking the point-in-time graph resolver per request. The `data/manifests/baseline.v0.1.json` values (100 documents/6,320 snapshots/76 events/175 unresolved/56 of 58 tests) describe a **historical frozen baseline**, not current counts.

HTTP contracts (`webapp/server.py`, `webapp/service.py`): GET `/api/overview`, `/api/gates`, `/api/corpus`, `/api/demo`, `/api/architecture`, `/api/rag/status`, `/api/audit`, `/api/risk/catalog`; POST `/api/scenarios`, `/api/risk/assess`, `/api/rag/query`, `/api/rag/reindex`, `/api/compare`, `/api/uploads`, `/api/actions/check-gates`, `/api/actions/run-tests`, `/api/actions/score-demo`. `POST /api/rag/query` takes JSON `query` (required, <=4,000 characters) and `mode` (`specific` or `generic`, default `specific`); the answer contains answer sections, retrieved anchors, verification, optional metrics, source guidance and limitations (`rag/rag_pipeline.py`). `POST /api/risk/assess` uses exactly the scenario fields in `schemas/risk/compliance_scenario.v1.schema.json`; output follows `schemas/risk/compliance_risk.v1.schema.json`, includes `legal_validation: UNVERIFIED`, and can abstain. Drift scores are not risk inputs. Other contracts reside in `schemas/` and are versioned; do not infer runtime JSON Schema validation for every path merely from schema files.

RAG retrieval combines feature-hash cosine, lexical overlap, metadata and section cues. The default index is local and persistent; Chroma is optional. Live India Code lookup is enabled unless `TLD_LIVE_INDIA_CODE=0` and supplements local results (`rag/indiacode.py`, `rag/rag_pipeline.py`); it is not an authoritative historical version resolver. LLM generation uses temperature 0.0, `qwen3:4b` through local Ollama if reachable by default, or an OpenAI-compatible endpoint when configured with `TLD_RAG_API_KEY`/`OPENAI_API_KEY`; failures produce an extractive fallback. The response's drift components are lexical, feature-vector cosine, and an LLM score *or legal-cue proxy*; overall drift is weighted RMS, while retrieval/evidence alignment is a separate score (`rag/metrics.py`). These scores are diagnostic, not legal accuracy or calibrated probabilities.

## Discrepancies and unknowns

- The root `context.md` is an August 2026 research-stage snapshot and states no implementation exists; that is contradicted by the current tree. It was preserved as historical work.
- `README.md` still describes a dual-PDF comparison UI as the dashboard's primary flow; current `frontend/src/App.jsx` uses a single-prompt RAG assistant with a risk view. The older `/api/compare` route still exists, but no dedicated comparison tab appears in the current navigation. Its research plan language should not be read as completion evidence.
- The plan's Phase 0–12 numbering is **research-plan numbering**. Current reports and gates use implementation Phase 0–11, including the later Phase 3 temporal graph and a separate compliance-risk checkpoint. Do not equate like-numbered phases without checking scope.
- Live India Code availability, current official-source completeness, remote CI run status, frontend build from this checkout, model behavior, and legal correctness were **not verified** in this audit. API presence does not prove the service is running.
- The saved Phase 11 lock reports a prior fresh-environment engineering reproduction. This audit did not rerun that workflow; see [verification.md](verification.md).

The intended research scope and acceptance criteria remain in [plan.md](../plan.md). Current gate interpretation is in [handoff.md](handoff.md).

## Update (2026-10-12, live-pipeline sprint)

- `monitoring/` now covers India Code (DSpace REST) and e-Gazette (session HTML listing + static PDFs).
  - Discovery runs at most once per source per 24 h.
  - A per-document state machine and content-based deduplication process only new or revised bytes.
  - Processed text is served through a separate, unreviewed overlay index; the base index and graph are untouched.
- Drift scoring is drift-metrics-v3; see `docs/methodology/drift_score.v3.md`.
- Query responses carry clause-level evidence: Act, provision, operation, amendment event, source hash, page and offset. The UI shows it with a separate indicator for each of textual drift, materiality, answer change and risk.
- The last live e-Gazette attempt failed on the server's incomplete TLS chain (see `verification.md`).

## Update (2026-10-12, follow-up)

- **e-Gazette:** live discovery works over a pinned-intermediate TLS context with full verification (ADR 0010).
- **Deployment:** the daily job is packaged as systemd timers with missed-run alerting (ADR 0011).
- **Accessibility:** the comparison view passed real-Chrome keyboard, accessibility-tree and 320px checks.
