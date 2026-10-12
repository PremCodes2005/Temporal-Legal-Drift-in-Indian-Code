# Stage 3B checkpoint — reproducibility release v0.2.0 and temporal graph v3

Date: 2026-10-12. Base commit `bd43b4d` (`main`) plus uncommitted Stage 3A/3B working-tree changes. Engineering results only; **legal/research gate UNVERIFIED**.

## Verified starting state and root causes

- **Clean-checkout breakage was wider than reported.** A `git worktree` of HEAD (tracked files only) ran 94 tests with 14 errors and 1 failure, and `check-gates` exited 2 (Phase 3 `temporal_graph_v2_hash_reconciles`, transition-queue checks; Phase 11 checksums). The 15 tests and the Phase 3/11 gates read gitignored `data/normalized/`, `data/interim/` and `data/raw/`. The v0.1.0 "fresh environment" was a fresh venv run against the developer's own working tree, so it never exercised a clean checkout. Remote CI was not inspected; by inference it fails at HEAD.
- **Graph v2 is not reproducible from current code.** A rebuild differs in 10 events' `target_path_detail`: the frozen graph predates the `clause\b` fix (`clause:s`). Rebuilds also still produce `sub-section:s`.
- **Normalization is not byte-reproducible.** pypdf is unpinned (`>=5.0`) and the original version was never recorded. Re-normalizing the tracked PDFs with pypdf 6.16.2 matches 99/100 documents; `it-amendment-act-2008` page 18 differs by one space (`• 7.` vs `•7.`).
- `version_graph.v1.json` does rebuild byte-identically.
- `verify-reproducibility` and `build-temporal-knowledge-graph` both used `atomic_replace` on the v0.1.0 release and on graph v2 respectively, i.e. in-place overwrite.

## Changes

**Release path (Phase 11)**
- `verify-reproducibility --release-id <new>` now writes `data/releases/reproducibility-<id>/` and `reports/phase11/reproducibility-<id>.lock.json` once. Existing IDs are refused, including v0.1.0.
- `data/releases/active_release.json` is an explicit registry (ID, manifest, lock, manifest SHA-256). The Phase 11 gate reads only that release and checks registry, manifest and lock hashes agree.
- Gitignored inputs are declared in the manifest and shipped as gzip files under `inputs/`. There are 208: 100 normalized docs, 100 raw-metadata files, 1 raw checkpoint, 7 interim graph/candidate files.
- `restore-release-inputs` materializes them only when their SHA-256 matches, and rebuilds the 100 raw PDF blobs from the tracked `data/corpus/pdfs/` by content hash. CI runs it before the checks.
- Verification copies only checkout files (`git ls-files --cached --others --exclude-standard`) into a temp directory and creates a venv without system site-packages. It then restores, re-runs three write-once builders (each must regenerate byte-identical output), runs `check-gates`, and runs the full test suite.
- A provisional record exists only inside the throwaway copy; the real record is written only after every step succeeds.

**Graph v3 (Phase 3)**
- `build-temporal-knowledge-graph --graph-version v3` reads the frozen v2.1 extraction and the new field-silver labels `data/processed/amendments/v2.1/silver_labels.v2.1.json`.
- Events with `source_text_unreliable` or `operand_contains_page_furniture` carry `source_fidelity_flags`, are forced to ABSTAIN, and become unresolved transitions with that reason.
- Graph writers are now write-once.
- `_target_path_detail` gains `\b` for `sub-section`/`sub-clause`.
- Abstaining point-in-time queries now return the provision's unresolved transitions with exact source evidence.
- Phase 3 gate adds four v3 checks: checkpoint passed; graph and queue hashes; input hashes; no flagged event became a transition.

**Clean-checkout tests**
- The pipeline test uses `tests/fixtures/amendment_pipeline/`: a 36 KB verbatim block subset of two normalized documents, with the full-document SHA-256 in `PROVENANCE.json`. It checks the 37-Act result against the hash-locked v2.1 artifact.
- The materiality audit test reads the frozen v2.1 extraction.

## Outcomes for the flagged transitions

| v2 transition | v2 status | v3 |
| --- | --- | --- |
| `transition_2014c6dc44b528934e3bbe2e` (IT 2008 s.17, "otrtCen") | INTERNAL_CHECKS_ONLY | Unresolved: `source_text_unreliable` |
| `transition_53226993cc42430fbd1236bb` (IT 2008 ss.66/67, "dahonestly") | INTERNAL_CHECKS_ONLY | Unresolved: `source_text_unreliable` |
| `transition_b8344a08e81a3a697186dfe5` (IT 2008 "digital signature") | **CROSS_SOURCE_CORROBORATED** | Unresolved: `source_text_unreliable` |
| `transition_12f4d76b624696e94e359a16` (page furniture) | INTERNAL_CHECKS_ONLY | Unresolved: `operand_contains_page_furniture` |
| `transition_416b57390ba679cd8e4d5c4f` (Arbitration s.31, after-text `costs`, dated 2015-10-23) | **CROSS_SOURCE_CORROBORATED** | Unresolved: `operand_contains_page_furniture`. This was confirmed defect #2; v2 "corroborated" it only because the word "costs" occurs in consolidated s.31. |

Compound clauses are not split. 340 v2.1 events are `UNKNOWN`. 36 v2 transitions became `operation_not_fragment_reconstructable`, including dated `transition_dbb723f2bd878121cccd9ac5` (Arbitration s.14). 25 transitions are new in v3, and 3 moved from INTERNAL_CHECKS_ONLY to CROSS_SOURCE_CORROBORATED because v2.1 fixed anchor-as-payload operands (e.g. `', the words'` → `'or culture'`).

## Graph v2 vs v3

| Count | v2 | v3 |
| --- | --- | --- |
| Input extraction / silver | v1 `e7cd6fe1…` / v1 | v2.1 `91a453ad…` / v2.1 `1ec6c0d6…` |
| Legal sources / acts / amendment acts | 100 / 63 / 37 | 100 / 63 / 37 |
| Provisions | 5,657 | 5,657 |
| Provision versions | 5,891 (5,657 + 2×117) | 5,827 (5,657 + 2×85) |
| Amendment / commencement events | 864 / 864 | 864 / 864 |
| Transitions | 117 | 85 |
| — CROSS_SOURCE_CORROBORATED | 67 | 56 |
| — INTERNAL_CHECKS_ONLY | 50 | 29 |
| Fully machine-checked ("validated") | 66 | 55 |
| Dated | 6 | 4 |
| Unresolved transitions | 747 | 779 |
| Source-fidelity-flagged events | — | 49 (35 + 14) |
| Human-validated | 0 | 0 |
| Graph SHA-256 | `b7d70f01…` | see `temporal_graph_checkpoint.v3.json` |

Reconciliation: 85 + 779 = 864 events; 57 v2 transitions removed (36 compound, 15 wording/silver changes, 3 IT 2008, 3 page furniture), 25 added. v3 unresolved reason counts: event/target not silver-resolved 735, wording missing 685, operation not reconstructable 350, compound/repeated 36, source_text_unreliable 35, page furniture 14.

Point-in-time: Arbitration s.31 on 2016-01-01 returned the defective `costs` fragment in v2; v3 returns `UNRESOLVED` with the source-anchored unresolved transitions. Arbitration s.7 still resolves as an `AMENDMENT_CONTROLLED_FRAGMENT` with a scope warning.

## Release v0.1.0 vs v0.2.0

- **v0.1.0:** manifest `c85bb0c4…`, lock `7c85db67…` (file hashes), byte-identical to HEAD and still readable. 3 steps, dev working tree.
- **v0.2.0:**
  - lock manifest SHA `da07a1dd…`; 249 checksummed artifacts and 208 declared inputs (21 MB gzip).
  - 7 steps in a clean copy, all exit 0; 119 tests.
  - `supersedes`: 18 changed, 14 added, 0 removed artifacts.
- A first v0.2.0 draft recorded no predecessor. It was deleted before use and regenerated; it was never committed or shared.

## Limits

- **Not removed:** OCR, layout-aware margin-note separation, and compound-clause splitting were not attempted. They need an approved OCR tool and version, coordinate-preserving PDF parsing with re-normalization under a new version, and hand-checked fixtures per clause shape.
- **Weak corroboration:** 10 of 56 cross-source corroborations rest on after-fragments under 15 characters (e.g. `ten years`, `one lakh`). These are weak evidence.
- **Pypdf and dirty-tree caveats:** the pypdf version must be pinned or recorded before normalization can be regenerated rather than shipped. The release was cut from an uncommitted tree (`working_tree_dirty: true`); a commit followed by a new release ID would bind it to a commit.
- **No legal validation:** no transition is legally validated.
