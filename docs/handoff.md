# Claude Code handoff

## Exact stopping point

Audit date: 2026-10-12. Last verified commit: `68030875a719aa626fb05f294880de2953084781` (`main`, same as local `origin/main` at inspection; no remote fetch was performed). Its subject is `pre migration commit`; it added the earlier generic `CLAUDE.md`. The preceding substantive commit is `befa8cb` (`phase 5 completed with phase 4(19 test seperate)`), which added risk, materiality, reports, frontend risk view and tests. Git was clean **before** this documentation task. At handoff, only `CLAUDE.md` and newly created `docs/` files should differ; verify with `git status` before further work. No application code, configuration, dependencies, tests or existing architecture were intentionally changed.

The repository has 100 tracked local legal PDFs under `data/corpus/pdfs/`, a Python package/API, React/Vite frontend, schemas/protocols, and many versioned research artifacts. This is not a complete, legally validated historical India Code mirror. For architecture/contracts see [context.md](context.md); for decisions visible in code see [adr/README.md](adr/README.md).

## Verification performed in this audit

With `.venv/bin/python` and `PYTHONPATH=src`, 115 unittest tests ran and passed (exit 0); `validate-contract` exited 0 with structural and engineering checks true but research/legal gate false; `check-gates` exited 0 with Phase 0–11 engineering gates true and qualified review false. Exact commands and limits are in [verification.md](verification.md). No frontend build, live India Code query, Ollama/OpenAI request, remote CI run, clean-environment reproduction, or independent legal review was executed in this audit.

## Known blockers and discrepancies

- Research/legal gate remains open: no independent expert validation, no legally approved materiality taxonomy/gold labels, no frozen scientific benchmark, no real legal performance scores. `reports/phase7/gate_status.md`, `reports/phase11/gate_status.md`.
- Phase 2 notes unreadable/garbled glyphs in the 2008 IT amendment PDF and lack of hand-checked source-derived extraction fixtures. `reports/phase2/gate_status.md`.
- Phase 3 records 747 unresolved transitions, 6 dated transitions and zero human-validated transitions; fragment-level point-in-time results must not be called complete statutory versions. `reports/phase3/temporal_graph_checkpoint.v2.json`.
- Phase 4 has 50 frozen machine silver cases, 19 original Low/Medium disagreements; v2.3 audit reports five extraction/alignment defects and remaining review needs. Real `None` class unevaluated; full 50-case LLM assessment not completed. `reports/materiality/implementation_status.md`.
- Compliance risk has 13 structured abstention scaffolds and two conditional demonstrations, not 13 legal-gold scenarios. `reports/risk/checkpoint.v1.md`.
- Root `context.md` is stale and says no app exists; `README.md` describes the earlier dual-upload emphasis. Both were preserved. [context.md](context.md) records current implementation; [implementation-plan.md](implementation-plan.md) is a proposal, not accomplished work.
- The RAG index consumes `version_graph.v1.json`, not the newer temporal legal graph v2. The risk API uses a server-owned obligation registry rather than a per-request graph query. The system diagram should not imply those modules are fully wired end to end without this distinction (`rag/retriever.py`, `risk/service.py`).
- Saved `data/manifests/baseline.v0.1.json` has earlier counts and 56/58 tests; these are historical freeze values, not the current 115-test result. Saved Phase 11 reproduction claims are historical artifact claims, not a new execution here.

## Immediate next task

Start with the source-fidelity/extraction audit in [implementation-plan.md](implementation-plan.md): trace the IT 2008 PDF and the five Phase 4 v2.3 defects to source spans, determine whether OCR/alignment repair is justified, and preserve the frozen v1 silver artifact. Only then propose targeted code and new versioned data changes with regression tests. If the needed original legal text cannot be read reliably, record an unresolved evidence issue rather than manufacture an old/new clause or claim expert validation.

Unknown at handoff: status of remote GitHub Actions, runtime availability of Ollama/India Code, whether the current React source builds cleanly, completeness of all India Code amendments, and legal correctness of the generated outputs. These need separate verification.

## Stage 3A status (2026-10-12)

Started the recommended source-fidelity audit; see [../reports/phase2/source_fidelity_audit.v1.md](../reports/phase2/source_fidelity_audit.v1.md). The extractor in Git did not reproduce the frozen v1 artifact; it is now labelled v2.1 and written to `data/processed/amendments/v2.1/` beside an untouched v1. IT 2008 events and page-furniture-contaminated operands are routed to review. New v2.4 materiality audit added. The Phase 11 engineering gate is red until a new reproducibility release is cut without overwriting v0.1.0. Legal/research gate unchanged: UNVERIFIED.

## Stage 3B status (2026-10-12)

- Graph **v3** (`data/interim/temporal_legal_knowledge_graph.v3.json`) is built from extraction v2.1. Source-fidelity-flagged events (IT 2008 OCR, page furniture) never become transitions.
- Graph v2 is preserved but is not reproducible from current code.
- The Phase 11 gate validates the registered active release, v0.2.0. Any change to checksummed code, schemas, tests, protocols, frontend or web needs a new release ID (`tldrift verify-reproducibility --release-id <new>`).
- A clean checkout must run `tldrift restore-release-inputs` before the tests.
- RAG still indexes `version_graph.v1`, and risk still uses its obligation registry. Neither consumes v3.
- Legal/research gate: UNVERIFIED.
- Details: [../reports/phase3/temporal_graph_v3_checkpoint.md](../reports/phase3/temporal_graph_v3_checkpoint.md).

## Phase A/B status (2026-10-12)

- **Phase A:** pypdf pinned to 6.16.2 and frontend deps pinned; release v0.2.1 is bound to commit `63f81ed`. CI now also builds the frontend and diffs it against `web/`. Remote CI on `58c9868` was observed green.
- **Phase B:** extraction **v2.2** adds a bounded compound splitter, the "respectively" fix and layout-aware furniture exclusion. An OCR *candidate* for IT 2008 is frozen; it is unverified and not used.
- `build-amendment-extraction-version --version <current> --previous <frozen>` writes a new extraction version; it refuses any version other than the current extractor's.
- See [../reports/phase2/extraction_v2.2_checkpoint.md](../reports/phase2/extraction_v2.2_checkpoint.md).

## Phases C–G status (2026-10-12)

- **C:** graph **v4**, an evidence-strength policy (`protocols/temporal_graph_protocol.v3.md`) and `graph-consumer-v1`.
- **D:** materiality re-assessment **v2.5** (50 cases), None search v2, and LLM assessments v2.
- **E:** risk tests extended. Section 19 demonstrations are confirmed to rest on stipulated applicability.
- **F:** RAG drift only on aligned versions, honest UI labels, source-fidelity warnings.
- **G:** benchmark freeze still refused (no gold).
- See `docs/claims_evidence_matrix.md` and the per-phase checkpoint reports. The legal/research gate remains UNVERIFIED.
