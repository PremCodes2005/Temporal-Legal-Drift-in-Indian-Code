# Phase 1 Gate Status

**Engineering/automated gate: PASSED**

**Qualified legal-review gate: PENDING**

## Implemented

- Deny-by-default HTTPS source policy.
- Required official identifier and instrument type.
- Redirect target validation before download.
- Response-size limit and timeout.
- SHA-256 content addressing.
- Immutable raw blobs and acquisition metadata.
- Integrity verification and injectable transport for offline tests.
- Draft authoritative-source protocol.
- A resumable, manifest-driven fourteen-document India Code technical pilot.
- Fourteen locally downloaded PDFs reconciled by SHA-256 in the corpus lock report.

## Human-review blockers

- `www.indiacode.nic.in` is approved by the user for this bounded technical pilot, but not yet accepted as legally sufficient by a qualified reviewer.
- Corpus domains, instruments, date range, and central/state scope are not frozen.
- The pilot acquisition is technically reconciled; legal sufficiency and temporal evidence remain unverified.
- No qualified legal reviewer has accepted the source protocol.
- Redistribution constraints remain undecided.

The local runtime contains the fourteen-document pilot corpus. Immutable content-addressed raw binaries remain ignored by version control; verified readable copies under `data/corpus/pdfs` are Git-trackable. URLs, identifiers, hashes, byte counts, and normalized-document links are recorded in `reports/corpus/india-code-temporal-pilot-v1.lock.json`.
