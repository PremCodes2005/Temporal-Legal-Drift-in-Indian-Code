# Architecture decision records

These ADRs are **retrospective descriptions of decisions visible in the current code**, not minutes of historical decision meetings. They do not claim why earlier authors made a choice unless a checked-in protocol or code comment says so. “Observed” statements cite implementation or artifacts; trade-offs beyond that are explicitly inference. Future changes need their own dated ADR rather than rewriting this audit as history.

| ADR | Observed boundary |
| --- | --- |
| [0001](0001-source-provenance-and-versioned-index.md) | Content hashes, source provenance, and version-coupled RAG index |
| [0002](0002-temporal-evidence-and-abstention.md) | Temporal applicability uses approved evidence and can abstain |
| [0003](0003-separate-drift-materiality-and-risk.md) | Text drift, materiality, and scenario risk are different outputs |
| [0004](0004-local-rag-and-llm-fallback.md) | Local hybrid retrieval, optional live supplement and LLM fallback |
| [0005](0005-structured-evidence-bounded-explanations.md) | Structured explanations bounded by trace evidence (2026-10-12) |
| [0006](0006-versioned-case-orchestration.md) | Idempotent case orchestration through versioned interfaces (2026-10-12) |
| [0007](0007-append-only-review-ledger.md) | Append-only, hash-chained review ledger (2026-10-12) |
| [0008](0008-incremental-official-source-monitoring.md) | Incremental 24-hour official-source monitoring (2026-10-12) |
| [0009](0009-document-state-machine-and-index-overlay.md) | Document state machine, cross-portal linking, index overlay (2026-10-12) |
| [0010](0010-pinned-intermediates-for-incomplete-tls-chains.md) | Pinned Let's Encrypt intermediates for e-Gazette's incomplete TLS chain (2026-10-12) |
| [0011](0011-always-on-monitoring-deployment-and-alerting.md) | systemd deployment of the daily job with missed-run alerting (2026-10-12) |
| [0012](0012-text-quality-quarantine.md) | Withhold untrustworthy PDF text lines (Hindi text layer, legacy-font mojibake) (2026-10-13) |
| [0013](0013-commencement-notification-policy.md) | Conservative commencement-notification policy with separate, unreviewed facts (2026-10-13) |

Audit base: commit `68030875a719aa626fb05f294880de2953084781`, 2026-10-12. Verification limits: [../verification.md](../verification.md).
