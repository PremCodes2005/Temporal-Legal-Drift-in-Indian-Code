# Temporal Legal Drift in the Indian Code

Research software foundation for evaluating whether LLM-based compliance systems correctly propagate legally applicable changes in Indian law over time.

The repository is at TRL 2. Phases 0–2 provide configuration, source provenance, immutable acquisition storage, and deterministic parsing/normalization. They do not contain a legal corpus, benchmark, version graph, applicability resolver, model, experimental result, or monitoring agent.

## Implemented boundary

- **Phase 0:** draft research contract, terminology/temporal registries, novelty-audit template, gate status, and structural validation.
- **Phase 1:** source-policy enforcement, HTTP transport abstraction, SHA-256 provenance, content-addressed immutable raw storage, and metadata verification.
- **Phase 2:** plain-text, HTML, XML, and optional PDF parsing; deterministic normalization; quarantine records; normalized output storage; unit/integration tests.

All legal/research gates remain pending until the decisions and expert reviews specified in `reports/phase0/gate_status.md` occur.

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
```

Acquisition is deny-by-default. `configs/source_policy.v1.json` contains no approved hosts until the Phase 1 source protocol receives legal/research approval.

## Safety and scope

- Raw evidence is content-addressed and never overwritten.
- Every normalized record points to source metadata and a source hash.
- Unsupported, malformed, or checksum-invalid inputs are quarantined.
- No parser decides provision identity, temporal applicability, materiality, or compliance consequence.
- This is research infrastructure, not legal advice.

See `plan.md` for the definitive implementation and research plan.

