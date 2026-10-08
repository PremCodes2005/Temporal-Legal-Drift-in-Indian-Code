# Temporal Legal Knowledge Graph Protocol v2

The graph represents `Act → Provision → ProvisionVersion` and `AmendmentAct → AmendmentEvent → VersionTransition`. Every event and transition links to an immutable `LegalSource`; every event receives a `CommencementEvent`, including an explicit unresolved status when no effective date is established.

Two version scopes are kept separate:

- `COMPLETE_CONSOLIDATED_SOURCE_SNAPSHOT` is text directly extracted from a downloaded consolidated source, but its historical interval is unknown unless separate temporal evidence establishes it.
- `AMENDMENT_CONTROLLED_FRAGMENT` contains only wording whose before/after state is established by an amendment instruction. It must not be presented as a complete historical section.

A transition is machine-evidence validated only when its silver label is accepted, the principal Act and target provision resolve, the operation has reconstructable wording, source hashes exist and the forward operation passes a deterministic round-trip check. Effective dates are never inferred from assent or publication. Missing commencement remains `COMMENCEMENT_UNRESOLVED`.

Point-in-time queries consider only transitions with evidence-supported effective dates. Unsupported queries return `UNRESOLVED`; supported fragment queries return `RESOLVED_FRAGMENT` with a scope warning, amendment event and authoritative source chain.

The twenty-record validation set is a deterministic machine-evidence review queue. Its records are not human or legal gold until a human reviewer records an independent decision.
