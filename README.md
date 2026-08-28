# Temporal Legal Drift in the Indian Code

Research software foundation for evaluating whether LLM-based compliance systems correctly propagate legally applicable changes in Indian law over time.

The repository is at TRL 2. Phases 0–4 provide configuration, source provenance, immutable acquisition storage, deterministic parsing/normalization, a technical provision-version graph, and an evidence-constrained applicability resolver. A fourteen-document India Code technical pilot is downloaded locally, but it is not a legally validated corpus or benchmark. The repository does not contain materiality gold labels, compliance scenarios, model results, or a monitoring agent.

## Implemented boundary

- **Phase 0:** draft research contract, terminology/temporal registries, novelty-audit template, gate status, and structural validation.
- **Phase 1:** source-policy enforcement, HTTP transport abstraction, SHA-256 provenance, content-addressed immutable raw storage, and metadata verification.
- **Phase 2:** plain-text, HTML, XML, and optional PDF parsing; deterministic normalization; quarantine records; normalized output storage; unit/integration tests.
- **Phase 3:** stable provision identity, consolidated-snapshot versions, amendment-event candidates, graph invariants, evidence links, unresolved-link escalation, and exact-version reconstruction.
- **Phase 4:** typed temporal facts, scenario/date applicability queries, evidence traces, conditional/partial commencement handling, unresolved escalation, and automated cross-source amendment-propagation checks.

Engineering gates pass independently. Legal/research gates remain pending until the decisions and expert reviews recorded in `reports/phase0` through `reports/phase4` are completed.

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
tldrift resolve-applicability --facts PATH --scenario-id ID --lineage-id ID --reference-date YYYY-MM-DD
tldrift check-gates
```

Acquisition is deny-by-default. The user-approved bounded pilot permits only `www.indiacode.nic.in`; every other host remains blocked. `download-corpus` is resumable through an integrity-checked checkpoint. The pilot manifest is not legal gold and does not establish sufficient benchmark coverage.

Raw and normalized processing artifacts are local runtime data and are ignored by version control. `materialize-corpus` creates integrity-checked, Git-trackable copies with readable filenames under `data/corpus/pdfs` while leaving immutable raw evidence unchanged. `corpus-report` writes a deterministic lock report containing the authoritative URLs, identifiers, SHA-256 hashes, sizes, parser provenance, and known extraction risks.

`check-gates` is the executable Phase 0–4 engineering acceptance check used by CI. Phase 4 also checks whether amendment-act evidence, consolidated-text amendment notes, and matching effective-date candidates agree for the configured pilot relation. This is internal consistency validation, not independent legal review or legal gold. The unavailable external review is reported explicitly rather than silently treated as passed.

## Safety and scope

- Raw evidence is content-addressed and never overwritten.
- Every normalized record points to source metadata and a source hash.
- Unsupported, malformed, or checksum-invalid inputs are quarantined.
- Parsing does not decide materiality or compliance consequence. Phase 3 identity and Phase 4 applicability outputs retain evidence and unresolved states and require expert confirmation.
- This is research infrastructure, not legal advice.

See `plan.md` for the definitive implementation and research plan.
