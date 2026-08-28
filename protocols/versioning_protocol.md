# Phase 3 Provision Versioning Protocol

**Status:** Engineering implementation complete; qualified legal-validation gate pending.

1. Instrument identity is derived from the official identifier.
2. Provision lineage identity is derived from the instrument and canonical structural path.
3. Version identity includes lineage, immutable source hash and exact-text hash.
4. Every version and amendment event must link to a source artifact, normalized document, block and locator.
5. Duplicate section candidates are recorded for review; the longest extraction is a technical selection, not legal gold.
6. Consolidated snapshots do not establish historical transitions by themselves.
7. A transition requires before and after versions, an amendment event, operation and authoritative evidence.
8. Cycles, orphan nodes, missing evidence and text-hash mismatches fail the graph.
9. Unsupported amendment targets remain unresolved.
10. Legal approval is required before a transition enters a benchmark gold set.
