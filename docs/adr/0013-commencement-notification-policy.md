# ADR 0013: Conservative commencement-notification discovery with separate, unreviewed facts

Status: **accepted 2026-10-13**. See `docs/methodology/commencement_policy.v1.md`.

## Decision

- **Discovery:** discover commencement notifications only from precise subject phrases that name an enactment.
- **Extraction:** extract each appointed date as its own `unreviewed` `TemporalFact`, from quarantine-cleaned English text, with the verbatim provisions span.
- **Separation:** keep publication, commencement and applicability separate. Applicability is never set by monitoring.
- **Review gate:** legal effect requires a reviewer's approval. The existing resolver already ignores unreviewed facts, so this is enforced structurally, not by convention.
- **Conflicts and uncertainty:** record conflicts and unparsed wording; never resolve them automatically.

## Consequences

- Commencement evidence is now collected, but it changes nothing in the graph, the index or applicability until a review mechanism exists. That mechanism is open work.
