# Architecture decision records

These ADRs are **retrospective descriptions of decisions visible in the current code**, not minutes of historical decision meetings. They do not claim why earlier authors made a choice unless a checked-in protocol or code comment says so. “Observed” statements cite implementation or artifacts; trade-offs beyond that are explicitly inference. Future changes need their own dated ADR rather than rewriting this audit as history.

| ADR | Observed boundary |
| --- | --- |
| [0001](0001-source-provenance-and-versioned-index.md) | Content hashes, source provenance, and version-coupled RAG index |
| [0002](0002-temporal-evidence-and-abstention.md) | Temporal applicability uses approved evidence and can abstain |
| [0003](0003-separate-drift-materiality-and-risk.md) | Text drift, materiality, and scenario risk are different outputs |
| [0004](0004-local-rag-and-llm-fallback.md) | Local hybrid retrieval, optional live supplement and LLM fallback |

Audit base: commit `68030875a719aa626fb05f294880de2953084781`, 2026-10-12. Verification limits: [../verification.md](../verification.md).
