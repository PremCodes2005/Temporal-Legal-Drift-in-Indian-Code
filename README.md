# Temporal Legal Drift in the Indian Code

Research software foundation for evaluating whether LLM-based compliance systems correctly propagate legally applicable changes in Indian law over time.

The repository is at TRL 2. Phases 0–11 provide configuration, source provenance, immutable acquisition storage, deterministic parsing/normalization, a technical provision-version graph, an evidence-constrained applicability resolver, a materiality-annotation workload, scenario-authoring scaffolds, a leakage-audited technical release dry run, baseline infrastructure, controlled temporal-LLM execution, explanation-support evaluation, and fresh-environment engineering reproduction. A fourteen-document India Code technical pilot is available, but it is not a legally validated corpus or frozen benchmark. A 78-run non-gold LLM smoke experiment has executed; it verifies pipeline operation but provides no model-performance or legal-correctness result. The repository does not contain materiality gold labels, completed expert scenarios, independent legal validation, or a monitoring agent.

## Implemented boundary

- **Phase 0:** draft research contract, terminology/temporal registries, novelty-audit template, gate status, and structural validation.
- **Phase 1:** source-policy enforcement, HTTP transport abstraction, SHA-256 provenance, content-addressed immutable raw storage, and metadata verification.
- **Phase 2:** plain-text, HTML, XML, and optional PDF parsing; deterministic normalization; quarantine records; normalized output storage; unit/integration tests.
- **Phase 3:** stable provision identity, consolidated-snapshot versions, amendment-event candidates, graph invariants, evidence links, unresolved-link escalation, and exact-version reconstruction.
- **Phase 4:** typed temporal facts, scenario/date applicability queries, evidence traces, conditional/partial commencement handling, unresolved escalation, and automated cross-source amendment-propagation checks.
- **Phase 5:** canonical materiality draft, evidence-linked 50-task annotation workload, annotation schemas, and explicit missing-evidence states without machine-generated gold labels.
- **Phase 6:** controlled-scenario schema, coverage registry, and evidence-linked authoring scaffolds without invented legal facts or outcomes.
- **Phase 7:** deterministic technical release manifest, duplicate-aware dry-run splits, leakage audit, data card, checksums, and enforced refusal to freeze non-gold inputs.
- **Phase 8:** registered baseline suite, dependency-free non-neural baselines, deterministic features, classification metrics, calibration support, and unsupported-result safeguards.
- **Phase 9:** six-condition controlled run planning and execution, 78 preserved schema-valid responses, strict answer normalization, and exact false-stability/false-instability metrics. Performance remains unscored without gold.
- **Phase 10:** 78 automated explanation-support evaluations, evidence/version/date/citation checks, explanation-drift detection, and explicit separation of diagnostics from expert legal review.
- **Phase 11:** artifact checksum manifest and fresh-virtual-environment reproduction of Phase 0–10 gates and tests; independent expert validation remains unavailable.

Engineering gates through Phase 11 pass independently. Legal/research gates remain unavailable or incomplete as recorded in `reports/phase0` through `reports/phase11`; software checks and a real LLM smoke run do not convert machine-produced candidates into legal gold or performance results.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,pdf]'
python -m unittest discover -s tests -v
```

The package requires no third-party dependency for text, HTML, or XML processing. PDF text extraction is optional and uses `pypdf`.

## CLI

```bash
tldrift validate-contract
tldrift acquire --url URL --official-id ID --instrument-type TYPE
tldrift normalize --metadata PATH_TO_SOURCE_METADATA
tldrift download-corpus
tldrift materialize-corpus
tldrift normalize-corpus
tldrift corpus-report
tldrift build-version-graph
tldrift build-temporal-candidates
tldrift validate-cross-version
tldrift build-annotation-workload
tldrift build-scenario-scaffolds
tldrift build-technical-release
tldrift prepare-baselines
tldrift build-llm-evaluation-plan
tldrift execute-llm-evaluation
tldrift score-drift-pairs --pairs PATH_TO_COMPLETED_PAIRS
tldrift build-explanation-evaluation-plan
tldrift verify-reproducibility
tldrift resolve-applicability --facts PATH --scenario-id ID --lineage-id ID --reference-date YYYY-MM-DD
tldrift check-gates
```

Acquisition is deny-by-default. The user-approved bounded pilot permits only `www.indiacode.nic.in`; every other host remains blocked. `download-corpus` is resumable through an integrity-checked checkpoint. The pilot manifest is not legal gold and does not establish sufficient benchmark coverage.

Raw and normalized processing artifacts are local runtime data and are ignored by version control. `materialize-corpus` creates integrity-checked, Git-trackable copies with readable filenames under `data/corpus/pdfs` while leaving immutable raw evidence unchanged. `corpus-report` writes a deterministic lock report containing the authoritative URLs, identifiers, SHA-256 hashes, sizes, parser provenance, and known extraction risks.

`check-gates` is the executable Phase 0–11 engineering acceptance check used by CI. Phase 4 checks amendment-evidence consistency; Phases 5–7 verify workload, scenario, release and leakage safeguards; Phases 8–10 verify baseline, controlled LLM execution and explanation-support evaluation; and Phase 11 verifies the reproducibility record. These are technical checks, not independent legal review or legal gold.

## Safety and scope

- Raw evidence is content-addressed and never overwritten.
- Every normalized record points to source metadata and a source hash.
- Unsupported, malformed, or checksum-invalid inputs are quarantined.
- Parsing does not decide materiality or compliance consequence. Phase 3 identity and Phase 4 applicability outputs retain evidence and unresolved states and require expert confirmation.
- This is research infrastructure, not legal advice.

See `plan.md` for the definitive implementation and research plan.
