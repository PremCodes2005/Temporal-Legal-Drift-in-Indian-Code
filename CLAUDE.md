# Claude Code handoff: Temporal Legal Drift in the Indian Code

Read [docs/handoff.md](docs/handoff.md) first, then [docs/context.md](docs/context.md), [docs/verification.md](docs/verification.md), and the existing [plan.md](plan.md). The `docs/` files describe the audited checkout at commit `68030875a719aa626fb05f294880de2953084781` (2026-10-12); recheck Git state before relying on them. `plan.md` is a research specification, not a record of completed work. The older root `context.md` is dated 2026-08-24 and inaccurately says no application exists; do not use it as current implementation evidence.

## Project boundaries

- Research question: whether LLM-assisted compliance reasoning propagates legally applicable changes in Indian law over time. Materiality, temporal applicability, compliance consequence, and operational risk are distinct.
- Python package in `src/temporal_legal_drift/`; React/Vite source in `frontend/`; generated browser assets in `web/`; versioned artifacts in `data/`, `experiments/`, and `reports/`; contracts in `schemas/`; procedures in `protocols/`.
- Local corpus and live India Code lookup are evidence aids. Neither local coverage nor current-law retrieval proves a complete historical legal version. The temporal graph explicitly stores amendment fragments and unresolved transitions.
- Engineering gates passing does **not** mean legal gold, approved applicability, expert validation, benchmark performance, or legal advice. Do not convert silver labels, generated scenarios, or machine-corroborated transitions into those claims.
- Preserve immutable/versioned artifacts and existing user work. Inspect `git status` before edits; make minimal, scoped changes and add new versions instead of silently replacing frozen records.

## Safe verification

From the repository root, in a Python 3.11+ environment with the package installed (or with `PYTHONPATH=src`):

```sh
python -m unittest discover -s tests -v
python -m temporal_legal_drift.cli validate-contract
python -m temporal_legal_drift.cli check-gates
```

The GitHub Actions workflow runs those checks on Python 3.11–3.13. It does not build the frontend. `verify-reproducibility`, ingestion, indexing, and several build commands write artifacts; inspect their targets before running them. Do not claim an unobserved CI, live India Code, Ollama, or legal-review result.

## Working practice

State assumptions and uncertainty. Prefer the smallest change that meets the task; do not refactor adjacent code. For a code change, define a concrete failure case, test it, and report what actually ran. Keep evidence identifiers and SHA-256 provenance intact. On unresolved legal applicability, insufficient evidence, or model failure, retain abstention and escalation rather than manufacturing a conclusion.
