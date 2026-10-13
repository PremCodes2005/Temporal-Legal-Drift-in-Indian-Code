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
| [0014](0014-rag-answer-v2-evidence-and-determinations.md) | Evidence-first answers with four independent determinations (rag-answer-v2) (2026-10-13) |
| [0015](0015-legal-change-fingerprint.md) | Legal Change Fingerprint: wording, rule and outcome drift (rag-answer-v3) (2026-10-13) |
| [0016](0016-analysis-records-and-minimum-facts.md) | Stored analyses, explicit limits and minimum facts (rag-answer-v4) (2026-10-13) |
| [0017](0017-separate-explanation-views-and-rule-drift-v1-2.md) | Separate Drift Explanation and Score Calculation views; rule-drift v1.2 (rag-answer-v5) (2026-10-13) |
| [0018](0018-hybrid-temporal-legal-drift-score.md) | Hybrid Temporal Legal Drift Score (tlds-v1) beside the fingerprint (2026-10-13) |
| [0019](0019-standalone-drift-and-calculation-pages.md) | Standalone Drift explanation and Score calculation pages (2026-10-13) |
| [0020](0020-single-page-assistant.md) | Single-page Legal drift assistant (2026-10-13) |
| [0021](0021-act-only-questions-and-faq.md) | Act-only questions, amendment matching, recent questions and the FAQ (2026-10-13) |

Audit base: commit `68030875a719aa626fb05f294880de2953084781`, 2026-10-12. Verification limits: [../verification.md](../verification.md).
