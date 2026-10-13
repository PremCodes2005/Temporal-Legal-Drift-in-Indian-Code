# Verification record

Audit base: commit `68030875a719aa626fb05f294880de2953084781`, local `main`, 2026-10-12. This separates **executed now** from **saved historical reports**. Commands were run from the repository root; `PYTHONPATH=src` was set and `.venv/bin/python` was used. No test log file was created by this documentation task.

| Executed in this audit | Observed result | Meaning / limit |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | Exit 0; `Ran 115 tests in 11.875s`; `OK`. | Current local unit/integration suite passed. The tool display truncated some individual lines, but the process summary and exit code were observed. No coverage percentage measured. |
| `PYTHONPATH=src .venv/bin/python -m temporal_legal_drift.cli validate-contract` | Exit 0; `structurally_valid: true`, `engineering_check_passed: true`, `research_legal_gate_passed: false`. | CLI structural/engineering acceptance, not research approval. Blockers include corpus scope/size, dimension count, thresholds and legal review approval. |
| `PYTHONPATH=src .venv/bin/python -m temporal_legal_drift.cli check-gates` | Exit 0; `engineering_gates_passed: true`, `qualified_review_complete: false`; Phase 0–11 engineering entries true. | Machine gate checks pass. Review blockers remain; does not prove legal accuracy, benchmark performance or independent validation. |
| `git status --porcelain=v2 --branch`, `git log`, source/config/report inspection | Initial tree clean; HEAD `68030875a719aa626fb05f294880de2953084781`, local `main` and upstream `origin/main` shown with +0/-0. | No remote fetch or GitHub Actions lookup; upstream state is locally known only. |

`check-gates` output was lengthy and truncated by the tool; do not assert every field was manually reviewed. The checked-in gate and checkpoint files were inspected separately. For the current known limitations, see [handoff.md](handoff.md).

## Existing pipeline and saved logs, not executed now

`.github/workflows/tests.yml` triggers on push/PR, matrix Python 3.11, 3.12, 3.13, installs with `pip install --no-deps -e .`, then runs `tldrift validate-contract`, `tldrift check-gates`, and `python -m unittest discover -s tests -v`. The workflow definition is present; remote run status and logs were **not** verified. There is no frontend build step in that workflow.

`reports/phase11/reproducibility.lock.json` and `data/releases/reproducibility-v0.1.0/manifest.json` report a previous three-step fresh-environment engineering reproduction, 115 tests and research gate false. Those are saved artifact assertions, not a reproduction performed here. `reports/phase9/gate_status.md` reports 78 controlled model executions, all abstaining on incomplete scaffolds, with no legal performance metrics. `reports/phase10/gate_status.md` reports 78 automated explanation-support checks and 0 expert evaluations. `reports/risk/checkpoint.v1.json` reports risk engineering checks true and research checkpoint false. Their claims were read, not independently rerun.

## Not run / not established

No frontend `pnpm install`, `pnpm run build`, browser end-to-end test, API server smoke test, live India Code request, local/remote LLM invocation, corpus redownload, PDF fidelity/OCR validation, Chroma integration, remote CI inspection, or fresh-environment reproduction was performed. The Phase 4 optional real-model LLM assessment is reported as incomplete in `reports/materiality/implementation_status.md`. No independent legal review was available; legal accuracy, real-corpus precision/recall/F1, temporal-drift performance, and expert explanation validity remain unknown.

## Recheck without overwriting artifacts

Run `git status` first, use the three executed commands above, and inspect any output paths before running builder or `verify-reproducibility` commands. Rebuilding the frontend writes `web/`; RAG reindex and ingestion write runtime/data artifacts. Record environment, full output/exit codes and Git diff in any future verification report. A pass in unit tests or `check-gates` must remain labelled an engineering result.

## Stage 3A addendum (2026-10-12, base `bd43b4d`, uncommitted working tree)

Executed with `.venv/bin/python` (Python 3.14.7, outside the CI 3.11–3.13 matrix) and `PYTHONPATH=src`:

| Command | Result |
| --- | --- |
| Baseline before edits: `unittest discover -s tests`, `validate-contract`, `check-gates` | 115 tests OK; both CLI checks exit 0 (matches the table above). |
| `vite build --outDir <scratchpad>` (not `web/`) | Built; asset hashes identical to committed `web/assets`. |
| `tldrift build-amendment-extraction-v2.1` (twice) | Exit 0; second run accepted as byte-identical. |
| `tldrift audit-materiality-disagreements` | Exit 0; wrote v2.4 audit. |
| After edits: `unittest discover -s tests` | 118 ran, **1 failure**: `test_gates` because the Phase 11 check `artifact_checksums_reconcile` is false. |
| After edits: `validate-contract` / `check-gates` | Exit 0 / **exit 2** (Phases 0–10 true, Phase 11 false). |

Phase 11 compares the working tree byte-for-byte with `data/releases/reproducibility-v0.1.0/manifest.json`, so any source edit fails it until a new release is cut. `verify-reproducibility` currently rewrites the v0.1.0 manifest and lock in place (`atomic_replace`), so it was **not** run. Details: [../reports/phase2/source_fidelity_audit.v1.md](../reports/phase2/source_fidelity_audit.v1.md).

## Stage 3B addendum (2026-10-12)

A clean `git worktree` of HEAD failed: 94 tests ran with 14 errors and 1 failure, and `check-gates` exited 2, because tests and gates read gitignored data. Reproducibility now uses release **v0.2.0**, registered in `data/releases/active_release.json`. Its inputs are hash-verified and restored with `tldrift restore-release-inputs`; CI runs that step first.

The following were executed after Stage 3B:
- **Working tree:** 119 tests OK; `validate-contract` and `check-gates` both exit 0.
- **`verify-reproducibility --release-id v0.2.0`:** 7 steps, all exit 0, in a clean copy with a venv that had no site-packages.
- **Independent clean copy** (rsync of `git ls-files --cached --others --exclude-standard`, new venv, no pypdf): the extraction tests passed *before* restore. After restore, `validate-contract` and `check-gates` both exited 0, 119 tests passed, and a second restore succeeded.
- **Refusal paths:** a tampered input was refused by restore and failed the Phase 3 and Phase 11 gates; re-cutting v0.2.0 or v0.1.0 was refused.
- **v0.1.0:** its manifest and lock hashes are unchanged.

Remote GitHub Actions has still not been observed. See [../reports/phase3/temporal_graph_v3_checkpoint.md](../reports/phase3/temporal_graph_v3_checkpoint.md).

## Sprint S0–S6 addendum (2026-10-12)

- **Executed locally:**
  - full suite (count in the release manifest), `validate-contract`, `check-gates`;
  - `npm run build`;
  - a real bounded `monitor-run` / `monitor-backfill` against India Code: about 20 requests, 3 PDFs;
  - headless Chrome screenshots at 1440px and 500px. 500px is headless Chrome's minimum window width; narrower captures crop.
- **Not executed:**
  - live e-Gazette ingestion (access-limited);
  - an always-on scheduler host;
  - keyboard and screen-reader testing in a real browser;
  - an LLM provider in the RAG flow (tests force the extractive fallback).

## Live-pipeline sprint addendum (Phases 1–6, 2026-10-12)

- **Executed locally:**
  - Full Python suite and `validate-contract` (exit 0). `check-gates` fails only Phase 11 `artifact_checksums_reconcile` until release v0.8.0 is cut; this is expected after code changes, and the gate was not weakened.
  - `npm test` (vitest, 8 component tests): query-specific evidence, score explanation, no-pair, source failure, timeout/fallback, keyboard reachability, mobile CSS rules.
  - `npm run build`; backend `serve-dashboard` served the new bundle.
  - Real query "Compare Section 19 before and after the IT Amendment Act, 2008." returned `CONSOLIDATED_FOOTNOTE_RECONSTRUCTION`, `SUBSTITUTE`, `section:19`, overall 54.8 and PDF page links that resolve (HTTP 200, `application/pdf`).
  - Headless Chrome screenshots at 1440px and 500px.
  - Mocked end-to-end test `tests/integration/test_monitoring_e2e.py`: listing → download → processing → overlay → retrieval → 24 h rule → unchanged-not-refetched; plus the layout-change failure path.
- **Live smoke:** e-Gazette live run on 2026-10-12T16:26Z: `SOURCE_UNAVAILABLE`. Python's TLS verification failed because egazette.gov.in serves its leaf certificate without the Let's Encrypt YR2 intermediate. Browsers and curl fetch that intermediate themselves; OpenSSL does not. Verification was **not** disabled. The 24 h rule set the next attempt to 2026-10-13T16:26Z. India Code was not due (next eligible 2026-10-13T14:21Z), so it was not contacted.
- **Not executed:**
  - a successful live e-Gazette ingestion;
  - Enter-to-toggle on `<summary>` in jsdom (it is not implemented there; native in browsers, not separately driven);
  - screen-reader testing;
  - viewports below 500px;
  - remote CI for this commit (until observed).

## e-Gazette TLS, live ingestion, deployment and browser accessibility addendum (2026-10-12)

- **Executed:**
  - Chain inspection (`openssl s_client`): leaf only, issued by Let's Encrypt YR2.
  - Intermediate verification: letsencrypt.org bytes = AIA bytes for all 6 Gen-Y intermediates, and `openssl verify` to the system store for all 8 pinned certificates.
  - `tests/unit/test_tls.py` (9 tests): valid chain, missing intermediate, intermediate not an anchor, hostname mismatch, foreign CA, tampered pin, cookie/Referer session.
  - Live: see `docs/sprint/s1_source_access_decision.v3.md`. Two audited manual retries, one audited manual import of a real Gazette PDF through storage, parsing, extraction, the review queue and the overlay, and one TLS-only handshake with the final pin set.
  - Deployment: `tests/unit/test_deploy.py` (9 tests) covering missed-run and stale alerts, the `--check` exit code, unit wiring to real CLI commands, and the alert script's delivery and failure paths. Defect fixed: `monitor-health` loaded graph v4 and failed when it was absent.
  - Real Chrome 154 (headless, DevTools protocol; `frontend/scripts/browser-a11y-check.mjs`): 22 Tab stops, all with a visible focus ring; Enter opens and Space closes the score explanation; no unnamed controls; heading outline and landmarks present; no horizontal scroll at 320, 360, 414 and 480px with the score panel open.
- **Defects found in the browser and fixed:**
  - At ≤414px, unbreakable text in the score panel overflowed: the formula table (425px wide) and a raw enum code.
  - Inserted and removed words were exposed only as `insertion`/`deletion` roles, which major screen readers do not announce by default. They now carry visually hidden "[removed: …]" / "[inserted: …]" text, confirmed in the accessibility tree.
- **Not executed:**
  - listening with VoiceOver or NVDA (only the browser's accessibility tree was inspected);
  - a real systemd host or `systemd-analyze verify`;
  - a scheduled (non-manual) e-Gazette run that downloads an amending Act; none was listed today.

## Text quality, commencement, deployment and observation addendum (2026-10-13, release v0.10.0)

**CI:** GitHub Actions run 38281312499 for `8959a33` (v0.9.0) succeeded, with jobs 3.11, 3.12, 3.13 and frontend-build all green, read from the Actions API. Run 38346672834 for `a5c7667` (v0.10.0) also succeeded on all four jobs. It is the first run with pypdf 6.16.2 installed, so the real-PDF re-parse test ran in CI.

**Text-quality gate:**
- **Fixtures:** real Gazette PDFs CG-DL-E-12102026-277080 (Hindi mis-mapped) and CG-DL-E-10102026-277026 (KrutiDev mojibake), plus a correct-Unicode Hindi control PDF.
- **Corpus calibration:** 278 of 245,761 frozen-corpus lines withheld, every one reviewed as garbage. English lines that must survive are pinned in tests.
- **Remediation:** the operational overlay was rebuilt; the one chunk containing Devanagari was removed.
- **Re-parse test:** a live pypdf re-parse must match the frozen extraction, and CI now installs pypdf 6.16.2.

**Commencement policy:**
- On the real MSMED notification: two `partial_commencement` facts, 2026-10-15 and 2026-12-15, with verbatim provisions, Act 16 of 2026 and S.O. 5575(E).
- The publication fact is kept separate, and applicability stays `NOT_DETERMINED`.
- The resolver escalates (`no_approved_temporal_evidence`) while the facts are unreviewed.
- On the real listing, the discovery rule selected 1 of 18 subjects (the right one).

**systemd (container harness, not a host):**
- Environment: Debian 12 with systemd 252, run with `--network none`.
- Results: `systemd-analyze verify` passed on all units; both timers were scheduled; the monitor job ran once per source and a repeat inside the window started nothing.
- Alerting: the health check exited 3 on `INGESTION_STALE` and then `SCHEDULER_MISSED_RUN`, and `OnFailure=` delivered the alerts.
- Script: `deploy/container-check/run.sh` reran this end to end with PASS.

**TLS:** at 2026-10-13T04:27Z the e-Gazette certificate was not yet renewed (serial `0509D525…`, YR2, notAfter 2026-10-19 09:53Z), and the pinned-chain handshake succeeded.

**Not verified:**
- **Always-on host:** none is authorized or named, so deployment is unverified. Exact install steps are in the runbook.
- **Certificate renewal:** has not happened yet, so TLS after renewal is unverified.
- **Screen readers:** no VoiceOver or NVDA listening pass was done. NVDA is Windows-only. VoiceOver AppleScript control is off on this machine, and enabling it is the user's decision. `frontend/scripts/voiceover-reading-pass.sh` is ready but has not been run.
- **Scheduled live run:** in progress on a session-scoped hourly scheduler on a laptop (not an always-on host). Results are appended below when observed.
