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
