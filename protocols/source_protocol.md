# Phase 1 Authoritative Source Protocol

**Status:** Draft; gate not passed.

## Acceptance

1. A source request must provide an HTTPS URL, official identifier, and instrument type.
2. The URL host must be explicitly approved in `configs/source_policy.v1.json`.
3. Host approval is an acquisition-control decision, not a claim of legal hierarchy or sufficiency.
4. Redirect targets must independently satisfy the same host policy.
5. Every response is size-limited and hashed with SHA-256 before storage.

## Immutable storage

- Raw bytes are stored by content hash.
- Existing bytes are never overwritten.
- Each acquisition receives immutable metadata with request URL, final URL, retrieval timestamp, media type, byte length, content hash, official identifier, instrument type, and response headers needed for provenance.
- Repeated acquisition of identical bytes may share the raw blob while retaining separate acquisition metadata.

## Evidence limitations

- Acquisition proves what bytes were retrieved from an approved endpoint at a recorded time; it does not prove temporal applicability or legal effect.
- Publication, enactment/assent, commencement, retrospective effect, transitional rules, deferred commencement, and partial commencement must be represented later as evidence-backed temporal facts.
- The software does not encode an authoritative legal hierarchy.

## OCR and malformed artifacts

- A scanned PDF is retained unchanged.
- OCR output, when later introduced, must be a derived artifact with its own method/version/confidence and must never replace raw evidence.
- Failed, unsupported, oversized, checksum-invalid, or malformed artifacts are quarantined with an error record.

## Gate

The Phase 1 gate remains pending until a qualified reviewer approves the source policy and a pilot source sample is manually verified end to end.

