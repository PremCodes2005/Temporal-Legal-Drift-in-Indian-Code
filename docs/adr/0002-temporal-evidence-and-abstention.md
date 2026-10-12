# ADR 0002 — Applicability requires temporal evidence

Status: **documented existing implementation**, not a reconstructed historical approval. Audit base: `6803087`.

## Observed decision

Publication or assent alone cannot establish applicability in `src/temporal_legal_drift/applicability/resolver.py`. Resolution uses approved, non-uncertain temporal facts, scenario attributes, effective dates, and explicit supersession paths; transitional or ambiguous cases return unresolved. The separate Phase 3 graph (`versioning/temporal_graph.py`) distinguishes source snapshots from amendment-controlled fragments and maintains unresolved transitions. See `reports/phase3/gate_status.md` and `reports/phase4/gate_status.md` for saved gate boundaries.

## Consequence and boundary

The system can answer only supported point-in-time queries and must expose uncertainty. **Inference:** abstention reduces the risk of treating a newly published or consolidated text as governing every scenario. It does not establish complete historical consolidations or independent legal applicability validation: the saved graph records 6 dated transitions and 0 human-validated transitions; real temporal candidates are unreviewed.
