# Temporal Legal Knowledge Graph Protocol v2

## Entities and relationships

The graph contains `Act`, `Provision`, `ProvisionVersion`, `AmendmentAct`, `AmendmentEvent`, `LegalSource`, and `CommencementEvent` records. Version transitions connect a before version to an after version through the amendment event that caused the change. Every extracted version, event, and commencement fact retains source identifiers and hashes; event evidence includes the exact quoted source text and locator fields where extraction supplies them.

## Evidence and version scope

Two version scopes must never be conflated:

- `COMPLETE_CONSOLIDATED_SOURCE_SNAPSHOT` is extracted from a downloaded consolidated source. Its historical interval is unknown unless temporal evidence establishes it.
- `AMENDMENT_CONTROLLED_FRAGMENT` is only the wording controlled by a specific amendment instruction. It is not the complete provision or the whole Act.

A machine-evidence-validated transition requires an accepted evidence-constrained silver label; a resolved principal Act and provision; reconstructable before/after wording; verified source and text hashes; a deterministic operation-to-evidence round trip; and exact normalized matching of the after-fragment in a separately downloaded consolidated principal-Act source. This is source corroboration, not independent legal adjudication.

## Temporal semantics

Each commencement record has separate typed slots for publication, assent, commencement, applicability, and legal-effect dates. Only commencement is currently extracted; other date types are explicitly `NOT_CAPTURED`, not represented as legally nonexistent. Retrospective effect and transitional-provision status are `NOT_ASSESSED`. The current conservative resolver derives a date only from a single unambiguous, Act-wide commencement statement in the first numbered clause. Partial, deferred, section-specific, retrospective, transitional, or otherwise ambiguous effects remain unresolved unless separately represented and supported. In particular, assent or publication is not treated as commencement, and Act-wide commencement is not automatically a legal conclusion about scenario-specific applicability.

An unresolved date is represented explicitly as `COMMENCEMENT_UNRESOLVED`; unknown temporal semantics are not filled by inference. A date-backed fragment query returns `RESOLVED_FRAGMENT`, an amendment event, source chain, temporal basis (`ACT_WIDE_COMMENCEMENT_NOT_SCENARIO_APPLICABILITY`), and a scope warning. A query without a supported date or a proven fragment chain returns `UNRESOLVED`.

## Validation and status language

The 20 deterministic review cases are machine-corroborated candidates, each with the before fragment, amendment, after fragment, corroborating consolidated version(s), source records, and blank human-review fields. Machine checks and cross-source text matches must not be described as manual validation, expert validation, or legal gold. Human validation counts remain zero until a reviewer records a decision, rationale, identity, and timestamp. The graph is a technical research artifact; it is not legal advice and does not claim complete historical consolidated texts for all provisions or dates.
