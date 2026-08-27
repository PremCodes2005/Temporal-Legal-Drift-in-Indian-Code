# Phase 0 Initial Novelty Audit

**Audit status:** Initial primary-source comparison completed on 2026-08-27; refresh required before paper submission.

This audit constrains the project position. It does not claim exhaustive literature coverage or first-ever novelty.

| Work | Verified source | Primary task and corpus | Relationship to this project |
|---|---|---|---|
| RegTrack | ACL 2026 proceedings, `https://aclanthology.org/2026.acl-srw.0.pdf`, pp. 764–778 | Alignment and six-class change classification over 4,772 annotated EU-regulation provision pairs | Establishes that fine-grained legal-change classification is adjacent prior work. Materiality/change classification cannot be the sole novelty here. |
| LawShift | NeurIPS 2025, `https://papers.nips.cc/paper_files/paper/2025/hash/adf82a0a1d52d93961476458b9566a2b-Abstract-Datasets_and_Benchmarks_Track.html` | Legal judgment prediction under statutory revisions, with 31 fine-grained change types | Establishes prior evaluation of model adaptability under statute shifts. This project instead targets versioned Indian-law applicability, controlled compliance consequences, and drift errors. |
| When Do LLMs Apply the Wrong Law? | arXiv:2608.14610 | Temporal applicable-law determination and diagnosis of current-law bias | Directly adjacent temporal-applicability work. This project must compare jurisdiction, temporal evidence, scenario construction, and compliance-drift metrics rather than claim the task is new. |
| LexKairos | arXiv:2608.09106v2 | Nine temporal legal tasks using Chinese cases and statutes | Establishes broader temporal legal capability benchmarking. This project is narrower: authoritative Indian provision versioning and pre/post compliance propagation. |

## Defensible positioning after the audit

The proposed contribution is a temporally versioned India Code benchmark and evaluation framework for whether LLM compliance reasoning propagates legally applicable changes. Its differentiating combination is planned to include authoritative evidence chains, historical provision reconstruction, temporal applicability, controlled pre/post compliance scenarios, false stability/false instability, and citation/explanation drift.

The benchmark and evaluation framework must remain scientifically useful without a novel materiality model. The final paper must repeat and expand this audit, verify all bibliographic metadata, and maintain a claim-to-evidence matrix.

