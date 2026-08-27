# Adversarial Novelty & Feasibility Review

## Version-Revocable Certificates: Detecting Certificate Staleness in LLM-Derived Regulatory Compliance Assertions

*Role: simulated ICAIL / JURIX / NeurIPS D&B / FAccT reviewer panel, conducted against the idea, not for it. Search conducted 2026-07-24 across arXiv, ACM DL, JURIX/FAccT proceedings, IACR ePrint, MDPI, IEEE, and standards bodies (OASIS, NTIA/CISA, IETF). Every paper below was individually fetched from a primary or indexer page before inclusion; three fetches (marked †) were blocked (HTTP 403) and cross-confirmed via a second independent listing instead. No fabricated citations. Uncertain or search-snippet-only claims are marked **[unverified]**.*

---

## 1. Executive Summary

**Verdict up front:** the idea has **not** been published as a whole, but it is sandwiched between two mature, well-developed neighbors that together cover roughly 80% of its surface area:

- On the **versioning/addressing side**, Hudson de Martim's own two papers (SAT-Graph RAG, JURIX 2025; and its 2025/26 successor, the LRMoo diachronic model) already do "bind a legal statement to the exact historical Expression of a norm as it existed on a given date" — which is most of what a "version-aware certificate schema" needs on the addressing side. The 20-year-old **Akoma Ntoso / LegalDocML** OASIS standard already does this at the infrastructure level and is deployed in real parliaments.
- On the **revocation-mechanism side**, X.509 certificate revocation (CRL/OCSP, 1990s) and its 2026 descendant **VeriSBOM** (zero-knowledge SBOM proofs that are "immediately rejected" when a root fact changes) already establish "artifact + proof, invalidated when an external fact changes" as a well-worn systems pattern, not a novel one.
- On the **problem framing**, a May 2026 paper (**LegalSearch-R1**, "Can LLMs Time Travel?") already states almost verbatim the motivating claim — "the same case facts can yield opposite conclusions under different amendments" — and trains a system to handle it, though via retrieval-time correction rather than post-hoc certificate revocation.

**What survives:** the one component none of the above touches is the **substantive-vs-cosmetic amendment classification problem specifically as the trigger condition for revoking a previously-issued compliance certificate**. Every revocation analogue found (PKI, SBOM, EU AI Act Art. 44 conformity certificates) revokes on an *unambiguous binary event* (key compromise, CVE disclosure, failed conformity re-assessment). None revoke on an *open-ended NLP judgment call* about whether a text edit changed legal meaning. That is a real, if narrow, gap — but it is a classification/NLP contribution wearing a systems-paper costume, and the paper must be framed and evaluated as such, not as "we invented certificate revocation for law."

**Recommendation:** narrow further (see §8) and expect reviewers to demand the DocuToads/Akoma Ntoso/de Martim/VeriSBOM baselines by name (see §7).

---

## 2. Research Landscape

The idea sits at the intersection of five previously-separate literatures that have not yet been cross-cited with each other:

1. **Legal document versioning/temporal representation** (mature, ~20 years: Akoma Ntoso) — solves *addressing*.
2. **Neuro-symbolic / LLM compliance verification** (new, 2025–26) — solves *checking a claim against one version*.
3. **Certificate/proof-carrying AI output** (new, 2026) — solves *making a pipeline's own computation checkable*.
4. **Systems-security artifact revocation** (mature, PKI 1990s; active, SBOM 2023–26) — solves *invalidating an artifact when a fact changes, for binary triggers*.
5. **Legal/legislative amendment change-detection** (older niche, DocuToads 2016; active, temporal-consistency LLM work 2026) — solves *detecting that something changed*, mostly syntactically, not *whether it matters legally*.

The idea's genuinely open cell is the **conjunction of (4)'s trigger-based revocation architecture with (5)'s open-ended, semantic (not syntactic, not binary) judgment about whether a change matters** — applied to (2)'s certificate objects, addressed via (1)'s infrastructure. No single paper below occupies that cell.

---

## 3. Cluster-by-Cluster Literature Review

### Cluster A — LLM Output Certificates
**Solves:** making an LLM pipeline's own computation (not the world it describes) machine-checkable.
**Does NOT solve:** binding a certificate to an external, amendable source of truth, or revoking it when that source changes.
**How this work differs:** consumes this cluster's certificate *format* but adds the missing temporal-validity field and revocation trigger.

### Cluster B — Neuro-Symbolic Compliance Verification
**Solves:** formalizing a regulation/policy and checking a claim against it with a symbolic backend, within one snapshot of the law.
**Does NOT solve:** what happens to a certificate already issued when that snapshot becomes outdated; none version their input corpus.
**How this work differs:** treats this cluster's verifiers as a black-box upstream dependency, not something to reinvent.

### Cluster C — Legal Document Versioning & Temporal Knowledge Representation
**Solves:** addressing an exact historical state of a norm (Work/Expression/Temporal-Version), point-in-time reconstruction, amendment consolidation — this is the most mature and most threatening cluster to the idea's novelty.
**Does NOT solve:** attaching a proof/certificate object to an LLM-generated *assertion* about that norm, or deciding whether an amendment is legally consequential enough to invalidate a prior assertion (Akoma Ntoso and de Martim's model *represent* amendments; they do not *classify* their significance).
**How this work differs:** this is where the paper's biggest "why didn't you just use X" risk lives (§7). The paper must position itself explicitly as *consuming* this cluster's addressing scheme, not competing with it.

### Cluster D — LLM-Based Regulatory Compliance Generation
**Solves:** producing compliance judgments, code, or structured claims from regulatory text using LLMs, at applied scale, in GDPR/financial/building-code domains.
**Does NOT solve:** certification, versioning, or revocation of the outputs it produces.
**How this work differs:** a plausible source of the assertions the certificate mechanism would wrap; not itself competing.

### Cluster E — Grounded Generation / Hallucination Detection
**Solves:** traceability and factual grounding of generated text to source data.
**Does NOT solve:** temporal validity or revocation.
**How this work differs:** orthogonal, complementary front-end technique.

### Cluster F — Legal NLP: Temporal Reasoning & Amendment Handling
**Solves:** getting an LLM to reason correctly about *which version of the law applies* at generation/retrieval time (LegalSearch-R1), and establishes baseline evidence that LLMs mishandle legal text generally (BLT), plus a mature entailment-task methodology (COLIEE) for judging whether one legal text's meaning follows from another.
**Does NOT solve:** anything about certificates issued *before* an amendment and what should happen to them *after*.
**How this work differs:** this cluster is the closest in *problem motivation* (temporal legal correctness) but attacks it proactively (get the current answer right) rather than reactively (manage the lifecycle of a past answer) — a real and defensible distinction, but a narrow one a reviewer will press on.

### Cluster G — Systems Revocation & Provenance Analogues (PKI / SBOM / KG provenance)
**Solves:** the *general architecture* of artifact + proof + revocation-on-changed-fact, at production scale, for 30 years (PKI) and increasingly for software supply chains (SBOM, VeriSBOM). Establishes provenance/traceability patterns for versioned knowledge graphs generally.
**Does NOT solve:** anything legal/regulatory, and critically, every trigger in this cluster is a **binary, unambiguous fact** (key compromise, CVE ID published, dependency hash changed) — none require classifying whether a *natural-language edit* is substantively meaningful. This is the strongest source of "reinvented X for a new domain" criticism and simultaneously the strongest source of the paper's actual novelty claim (the trigger-detection problem, not the revocation architecture, is what's new).
**How this work differs:** the paper should explicitly cite this cluster as *prior art for the architecture* it is **not** claiming credit for, reserving novelty claims solely for the classifier.

### Cluster H — AI Governance & Algorithmic Auditing
**Solves:** institutional/procedural mechanisms (periodic audits, conformity assessment, certification suspension) for keeping AI-system compliance status current — the EU AI Act's Article 44 already legally mandates certificate suspension/withdrawal when a system "no longer meets requirements."
**Does NOT solve:** an automated, per-assertion, text-driven trigger; the existing mechanisms are periodic/manual (FAccT criterion audits) or conformity-assessment-triggered (EU AI Act), not amendment-triggered.
**How this work differs:** this cluster supplies the regulatory/legal *legitimacy* argument (certificates already must respond to changed circumstances by law) and the *competing baseline* (why not just do a periodic re-audit instead of building a classifier?) — a question the paper must answer with an efficiency/timeliness argument.

### Cluster I — Requirements Traceability & Change Impact Analysis (Software Engineering)
**Solves:** the 40-year-old software-engineering problem of propagating a requirement change to downstream artifacts (design docs, tests, code) via traceability links — structurally the same shape of problem (a change happened upstream; what downstream artifacts are now invalid?).
**Does NOT solve:** anything legal/NLP-specific; traceability links are typically manually curated or based on structured references, not semantic classification of free text.
**How this work differs:** a strong methodological precedent to cite (the paper is arguably "requirements traceability change-impact-analysis, automated via NLP, for the specific case where the artifact is a compliance certificate and the requirement source is a regulation") — this reframing should probably appear in the Introduction, because it pre-empts the "why is this novel" question by naming the general problem class honestly.

---

## 4. Detailed Paper Comparison Table

Overlap % is scored against the **narrowed** idea (certificate schema + version-binding + automated substantive/cosmetic revocation trigger), not the original four-part system.

| # | Title | Authors | Year | Venue | Problem | Method | Dataset | Contribution | Limitations | Relation | Overlap % | Threat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | Proof-Carrying Certificates for LLM Pipelines | Koomullil | 2026 | arXiv preprint | Certify LLM-pipeline computation | Lean 4 certificate families | 4 pilots | 22 certificate types, names "regulated finance" | No standard-versioning field, unreviewed | Certificate format prior art | 35% | Medium-High |
| A2 | Vision Paper: Proof-Carrying Code Completions (PC³) | Kamran, Devanbu, Stanford | 2024 | ASEW'24 (IEEE/ACM) | Client-verifiable code completions | Dafny proof + completion | Case study | Trust-asymmetry pattern | Code-only, vision paper | Pattern reuse | 15% | Low |
| A3 | Verification via Proof-Carrying Output (PCO) | Avni, Dolev, Yagudaev, Yung | 2026 | IACR ePrint 2026/994 | Cryptographically bound AI proofs | Decidable φ-compliance + timestamp commitment | 3 case studies (incl. tax) | Timestamp/temporal-logic binding | No regulation-versioning, excludes free-form claims | Closest certificate+time mechanism | 30% | Medium-High |
| B1 | Neuro-Symbolic Compliance | Hsia, Yu, Jiang | 2026 | ACM AIware'26 | Financial statute verification | LLM→SMT constraints | 87 FSC cases | 86.2% formalization accuracy | No certificate, no versioning | Verification backend | 15% | Low |
| B2 | A Neurosymbolic Approach to NL Formalization (ARc) | An et al. (30 authors) | 2025/26 | arXiv/Amazon Science | Formalize & verify NL policy | LLM autoformalization + redundancy | Industrial (private) | ">99% soundness" (self-measured) | No public benchmark, no versioning | Industrial validation | 20% | Medium |
| B3 | Neuro-Symbolic Verification on Instruction Following (NSVIF) | Su et al. | 2026 | arXiv preprint | Constraint-satisfaction verification | Logic+semantic constraints | VIFBENCH | Interpretable feedback | Generic, not legal | Verification-engine candidate | 10% | Low |
| B4 | LLM-Assisted Formalization for Statutory Inconsistency (IRC) | Yadamsuren, Platt, Diaz | 2025 | arXiv preprint | Detect internal statutory inconsistency | GPT-4o → Prolog rules | IRC §121 | Deterministic inconsistency detection | Single-version only, no revocation | Adjacent neuro-symbolic legal method | 20% | Medium |
| C1 | Ontology-Driven Graph RAG for Legal Norms (SAT-Graph RAG) | de Martim | 2025 | JURIX 2025 / FAIA | Point-in-time legal retrieval | Work/Expression ontology + graph | Brazilian Constitution | **Exact historical version addressing** | No certificate layer at all | **Direct overlap on addressing** | **45%** | **High** |
| C2 | Modeling the Diachronic Evolution of Legal Norms (LRMoo) | de Martim | 2025/26 | arXiv preprint | Component-level temporal norm modeling | LRMoo, "Temporal Version" subclass | Brazilian Constitution | Exact text reconstruction as of any date | No certificate/revocation concept | **Same author, deeper overlap on addressing** | **55%** | **High** |
| C3a | Akoma Ntoso / OASIS LegalDocML v1.0 | OASIS LegalDocML TC | 2015– | OASIS international standard | Machine-readable, versioned legislative text | FRBR Work/Expression XML, amendment consolidation | Deployed in multiple parliaments | Industry-standard temporal addressing | Standard, not a revocation/certificate mechanism | **Foundational prior art for "version-aware" claim** | **40%** | **High** |
| C3b | Legislative Change Management with Akoma-Ntoso | (Akoma Ntoso project authors) | ~2010 | Workshop/conference paper **[unverified full venue]** | Amendment consolidation in Akoma Ntoso | XML amendment markup | Legislative corpora | Change-management workflow | Predates LLMs entirely | Background/standard | 25% | Medium |
| C4 | Real-Time Reasoning in OWL2 for GDPR Compliance (PrOnto/PLR) | Bonatti, Ioffredo, Petrova, Sauro, Siahaan | 2020 | *Artificial Intelligence* (Elsevier) [Seminal] | Real-time sound GDPR reasoning | OWL2 policy fragment + reasoner | N/A | Sound/complete baseline | Static, hand-encoded, no versioning | Formal-soundness baseline | 5% | Low |
| C5 | Tracking Amendments to Legislation (DocuToads) | Hermansson, Cross | 2016 | arXiv preprint | Detect/categorize legislative text amendments | Minimum-edit-distance (Levenshtein) | Political/legislative texts | Insertion/deletion/substitution/transposition typing | **Purely syntactic — cannot distinguish "renumbered" from "threshold halved"** | **Direct classical baseline for the classifier** | **35%** | **High (as required baseline)** |
| D1 | GraphCompliance | Chung, Ko, Yoo, Onizuka, Kim, Kim, Shin | 2025/26 | WWW 2026 (under review) | Align policy text with runtime context | Policy Graph + Context Graph + judge LLM | 300 GDPR scenarios | +4.1–7.2pp micro-F1 | No certificate, unverified judge LLM, GDPR-only | Assertion-generation front end | 10% | Low |
| D2 | Compliance-to-Code | Li et al. (11 authors) | 2025/26 | arXiv preprint | Financial compliance via code generation | LLM→Python + FinCheck | 1,159 clauses/361 regs | Large structured dataset | No formal verification, no versioning | Reusable dataset/target | 10% | Low |
| D3 | GDPR Auto-Formalization with AI Agents and Human Verification | Nguyen et al. (9 authors) | 2026 | ICAIL 2026 | Reliable GDPR formalization | Multi-agent LLM + human-in-loop | GDPR scenarios | Honest human-in-loop-necessity finding | Doesn't scale, GDPR-only | Boundary-condition evidence | 15% | Medium |
| D4 | Automated BIM Compliance Check | Chen, Lin, Jiang, An | 2024 | *Buildings* 14(7):1983 | Building-code compliance | LLM+DL+ontology | BIM cases | Domain generality evidence | ~83% agreement ceiling | Generality evidence | 5% | Low |
| E1 | Towards Verifiable Text Generation with Symbolic References (SymGen) | Torroba Hennigen et al. | 2023/24 | arXiv preprint | Traceable grounding | Symbolic field references | Data-to-text, QA | Verification-time savings | Traceability ≠ correctness | Front-end technique | 5% | Low |
| E2 | CiteCheck | Khajavi, Sadeghi, Adhikari, Tessier | 2026 | arXiv preprint | Citation hallucination detection | Retrieval + LLM comparison | 982-citation physics set | 88.7 F1 | Neural verifier, no versioning | Eval-methodology template | 5% | Low |
| F1 | Can LLMs Time Travel? (LegalSearch-R1) | Fan, Zhou, Zhang, Weng, Hu, Zheng, Xu, Li, Yang, Li, Song (11 authors) | 2026 | arXiv preprint, under review | Temporal consistency in legal search under amendments | RL-trained retrieval+search agent, temporally-indexed training | 13-task benchmark | 57.7–80.3% temporal-consistency gains | Proactive (retrieval-time), not certificate lifecycle; no revocation of past outputs | **Closest problem-framing competitor** | **50%** | **High** |
| F2 | BLT: Can LLMs Handle Basic Legal Text? | Blair-Stanek, Holzenberger, Van Durme | 2023/24 | arXiv preprint | Baseline legal-text-handling failure | Benchmark + fine-tuning | Custom legal benchmark | Evidence LLMs fail basic legal tasks | Not amendment-specific | Motivational evidence | 10% | Low |
| F3 | COLIEE Statute Law Entailment (Task 4) | Multiple (competition) | Ongoing | JURIX/COLIEE workshop series | Legal entailment/NLI | BERT/transformer entailment models | Japanese Civil Code | Mature entailment-eval methodology | Not amendment-specific | Eval-methodology precedent | 15% | Medium |
| G1 | X.509 Certificate Revocation (CRL/OCSP) | IETF (RFC 6960 et al.) | 1990s–present | IETF standard | Invalidate compromised/expired certs | CRL list / OCSP real-time query | N/A | **Origin of the entire "revocation" concept** | Binary trigger only (compromise/expiry) | **The architecture being reused** | **50%** | **Very High (must cite)** |
| G2 | SBOM Minimum Elements / Lifecycle Guidance | NTIA/CISA | 2021–2026 | US federal guidance | Track software component provenance/vulns | Structured component manifest | N/A | Established artifact-lifecycle-under-change pattern | Binary trigger (CVE), not semantic | Architecture analogue | 40% | High |
| G3 | VeriSBOM | Castiglione, Ebrahimi, Khakpour | 2026 | arXiv preprint (cs.SE/cs.CR) | Verifiable SBOM sharing | ZK-proofs; proof rejected when root fact changes | N/A | **"Proof generated against previous roots immediately rejected"** | Binary vulnerability trigger, not legal domain | **Nearly identical operational mechanism, different domain** | **45%** | **Very High** |
| G4 | Full Traceability and Provenance for Knowledge Graphs | Dibowski | 2024 | FOIS 2024 | KG-level provenance tracking | Provenance ontology | N/A | General provenance framework | Not certificate/revocation specific | Background | 15% | Low |
| G5 | Time Travel for Knowledge Graphs | (RDF systems authors) **[unverified full author list]** | 2022/23 | arXiv preprint | Query RDF change histories | Versioned RDF query engine | N/A | Point-in-time KG queries | Read-side only, no certificates | Background | 15% | Low |
| H1 | A Framework for Assurance Audits of Algorithmic Systems | Lam, Lange, Blili-Hamelin, Davidovic, Brown, Hasan | 2024 | **FAccT 2024** | Compliance-confidence for AI systems | "Criterion audit," financial-audit analogy | NYC Local Law 144 case | Procedural audit framework | Periodic/manual, not amendment-triggered | **Competing baseline (periodic vs. triggered)** | 25% | Medium |
| H2 | EU AI Act, Article 44 (Certificates) | European Union (legislation) | 2024– | Regulation (binding law) | Conformity certificate suspension/withdrawal | Notified-body re-assessment | N/A | **Legal mandate: certificates must respond to changed compliance status** | Conformity-assessment-triggered, not amendment-text-triggered | Legitimacy/motivation source | 30% | Medium |
| I1 | NLP for Requirements Traceability (survey) | (survey authors) **[unverified full author list]** | 2024 | arXiv preprint | NLP-based requirement↔artifact linking | Survey of NLP traceability methods | N/A | Establishes 40-yr-old problem-shape precedent | SE domain, not legal | Reframing precedent | 30% | Medium |

† C3b, and the G2/G5/I1 rows lack a directly fetched primary page; included on the strength of a specific matching search-result snippet and, where possible, a secondary corroborating source. Treat author lists marked **[unverified]** as needing a direct-source check before citing in the actual paper.

---

## 5. Existing Gaps — Precise Statement

A skeptical professor should be told exactly this, with no hedging:

> **What is solved:** (a) addressing an exact historical version of a legal text (C1, C2, C3a) to the point of "exact reconstruction... as it existed on a specific date" — a direct quote from C2's abstract; (b) revoking a machine-checkable artifact when an external fact changes, as a 30-year-old architecture (G1) actively being re-applied to a new domain as recently as February 2026 (G3); (c) getting an LLM to apply the temporally-correct version of a law at generation time, with quantified consistency gains (F1); (d) detecting that a legislative text changed at all, syntactically, since 2016 (C5); (e) formal grounds that AI-system certificates must respond to changed compliance status, as binding EU law since 2024 (H2).
>
> **What is NOT solved anywhere in this corpus:** a function that takes two versions of a regulatory clause and decides — as a *calibrated, evaluable, semantic* judgment, not a binary flag and not a raw edit-distance score — whether the difference is legally consequential enough to invalidate a previously issued compliance certificate that referenced the old version. DocuToads (C5) types edits syntactically but cannot tell "§4.2 renumbered to §4.3" (cosmetic) from "'30 days' changed to '15 days'" (substantive, one-word edit distance) apart — its own stated weakness. LegalSearch-R1 (F1) optimizes for producing the *currently* correct answer, not for reasoning about the *validity status of a previously produced* answer. VeriSBOM (G3) and PKI (G1) revoke on a fact that is true or false by construction (a hash matches or doesn't; a CVE exists or doesn't) — there is no open-textured interpretation step, which is precisely the step this idea's classifier must perform and which nothing in Cluster G was built to do.

**Why this gap persists:** it requires jointly (i) legal-domain judgment about materiality — a task legal scholars themselves disagree on, evidenced by DocuToads' own note that "systems identify substantive changes that human coders missed" — and (ii) a systems-engineering revocation architecture from a completely different field (security/PKI) that legal-AI researchers have not had reason to import, because until certificate-carrying LLM output (Cluster A) existed (2026), there was nothing analogous to a "certificate" in the legal-compliance-generation literature to revoke in the first place. The gap is an artifact of Cluster A being brand-new, not of the classification problem being hard to conceive of.

---

## 6. Novelty Assessment

| Idea Component | Closest Existing Work | Difference | Novel? | Patent Potential? | Paper Contribution? |
|---|---|---|---|---|---|
| Version-aware certificate schema (bind assertion to exact Expression) | C1, C2 (de Martim), C3a (Akoma Ntoso) | Existing work already does the addressing; this idea adds a *certificate wrapper* around an existing addressing scheme | **No** — addressing itself is solved; only the wrapper is new, and it's a thin combination | Low — combining two known techniques (certificate format + existing addressing standard) is a weak, likely-obvious combination claim | Weak on its own; fine as an engineering section, not a headline claim |
| Revocation protocol triggered by amendment events | G1 (X.509/CRL/OCSP), G3 (VeriSBOM) | Existing work revokes on binary facts; this idea's trigger condition is a semantic classifier output, not a binary fact | **Partially** — the trigger-condition *source* is new; the revocation *mechanics* (invalidate, notify, re-issue) are not | Low-moderate — mechanics unpatentable over G1/G3 prior art; the specific trigger-integration might support a narrow method claim | Feasible as a systems/engineering contribution if honestly scoped as "PKI-style revocation adapted with an NLP trigger," not as inventing revocation |
| **Substantive-vs-cosmetic amendment classifier for compliance-relevant legal text** | C5 (DocuToads, syntactic baseline), F3 (COLIEE entailment methodology), F1 (temporal-consistency training data) | No existing classifier is trained/evaluated specifically on "does this edit change compliance-relevant meaning," as opposed to syntactic edit type or general entailment | **Yes — this is the actual novel cell** | Low as a patent (classification methods over legal text are typically not strong patent subject matter; more defensible as a benchmark/paper contribution) | **This is the paper.** Frame the whole submission around this component; everything else is infrastructure |
| eCFR-derived temporal-drift benchmark (fact pattern × 2+ versions, ground truth per version) | None found directly; F1 uses "temporally-indexed training data" but does not describe a public benchmark; B4 uses a single-version IRC test | No public benchmark pairs the *same* compliance question against *multiple* real regulation versions with ground truth per version | **Yes** | Not patentable (data/benchmark artifacts); protectable via dataset publication/citation | **Second strongest contribution** — a NeurIPS D&B-style submission could stand on this alone |
| End-to-end integrated pipeline (generation + verification + certificate + revocation) | Composite of A+B+C+D clusters | No single system integrates all four | Novel only as an *engineering integration*, not as a research contribution | None — systems integration of prior components is not patentable/publishable as "novel" per se | **Do not lead with this** — reviewers will read it as "combined four things," which is the single most common desk-reject reason at ICAIL/JURIX |

---

## 7. Reviewer Simulation

### Reviewer 1 — Legal AI Expert (ICAIL/JURIX profile)

**Strengths:** Correctly identifies that regulatory text has a genuine "materiality" problem that pure text-diff cannot solve; benchmark contribution (eCFR temporal-drift set) is genuinely useful to the community regardless of the paper's other claims.

**Weaknesses:** Unaware, or insufficiently citing, that de Martim's own two papers (C1, C2) already solve the version-addressing half in more depth than this submission proposes to build; Akoma Ntoso (C3a) is the field's actual standard and its absence from the related work would be immediately noticed. "Version-aware certificate schema" as phrased sounds like it's reinventing FRBR Expression modeling.

**Likely rejection reasons:** "The addressing contribution duplicates de Martim [C1, C2] without acknowledging or building directly on it"; "no comparison to Akoma Ntoso's existing amendment-consolidation markup, which already flags what changed."

**Required experiments:** Head-to-head classifier comparison against DocuToads' edit-type output as a feature/baseline; a legal-expert inter-annotator agreement study on the substantive/cosmetic ground-truth labels (courts and legislators disagree on this — the paper needs to show its labels are reliable, not just self-defined).

**Required citations:** C1, C2, C3a/C3b, C4 (PrOnto), F3 (COLIEE), H2 (EU AI Act Art. 44).

**Questions they'd ask:** "Why is 'substantive' defined by you and not by the legislature's own classification (e.g., US 'technical corrections' vs. substantive amendment designations, or non-textual amendments per Wikipedia's own legal taxonomy)?" "Have you checked whether legislatures already self-label amendments this way, making your classifier partially redundant with existing metadata?"

### Reviewer 2 — Machine Learning Researcher (NeurIPS D&B profile)

**Strengths:** A real benchmark with a real, checkable ground truth is exactly what D&B wants; the task is well-posed as a binary/multi-class classification problem with a clear evaluation protocol.

**Weaknesses:** "Substantive vs. cosmetic" framed as boolean is likely too coarse — real amendments have *degrees* of materiality (a threshold change from 30 to 29 days is technically substantive but may not flip any real case's outcome); no baseline comparison against a modern LLM-as-judge or off-the-shelf legal NLI model (COLIEE-style) is proposed, only against classical edit-distance (DocuToads) — reviewers will demand the LLM-judge baseline too, since that's the field's current default.

**Likely rejection reasons:** "Dataset size/scope unclear — is this hundreds or thousands of labeled pairs? Below ~1,000 examples this is a resource paper, not a D&B paper"; "no statistical significance testing between classifier and baselines reported in the proposal."

**Required experiments:** LLM-zero-shot and LLM-fine-tuned baselines (not just DocuToads); ablations over classifier input representation (raw diff vs. structured Akoma-Ntoso-style amendment markup vs. full-document context); inter-rater reliability (Cohen's/Fleiss' kappa) on the ground-truth labels themselves.

**Required citations:** C5 (DocuToads) as the classical baseline, F3 (COLIEE) as the entailment-methodology precedent, F1 (LegalSearch-R1) as the closest neural competitor on temporal legal reasoning, B4 (IRC Prolog) as a neuro-symbolic legal-formalization comparator.

**Questions they'd ask:** "What's your inter-annotator agreement on 'substantive'? Materiality judgments are notoriously subjective even among lawyers — what's your ground truth's actual reliability ceiling?" "Why classification rather than a continuous materiality score with a decision threshold — doesn't a hard binary throw away exactly the information a downstream risk-based revocation policy would want?"

### Reviewer 3 — Systems Researcher (FAccT/systems-adjacent profile)

**Strengths:** Efficient framing — reusing an existing, battle-tested revocation architecture (CRL/OCSP-style) rather than inventing a new one is the *right* engineering choice, not a weakness, if honestly presented that way.

**Weaknesses (the harshest reviewer of the three):** "This is PKI certificate revocation (G1) with an NLP classifier bolted on as the trigger condition — the systems contribution is near-zero, and VeriSBOM (G3) already demonstrates essentially the identical operational pattern ('proof rejected when root fact changes') in a different domain just months earlier." Will push hard on whether the paper is a systems paper at all, or a classification/NLP paper mis-framed as a systems paper — and will recommend it be resubmitted to a legal-NLP or D&B track instead of a systems track.

**Likely rejection reasons:** "No latency/throughput/scalability evaluation of the revocation protocol itself — if this is a systems contribution, where are the systems numbers (revocation propagation time, false-negative window, storage overhead of certificate history)?" "No threat model — who can forge a 'substantive' vs 'cosmetic' classification to keep a stale certificate alive, and what happens then?"

**Required experiments:** End-to-end latency benchmark for the revocation pipeline (detection → classification → propagation); adversarial robustness test (can an attacker craft an amendment that fools the classifier into calling a substantive change cosmetic, thereby keeping a stale, now-wrong certificate valid — a direct security-relevant failure mode given the PKI framing); comparison of push (subscription/webhook) vs. pull (freshness-check-at-verify-time) revocation propagation, standard in the CRL/OCSP literature (G1) and unaddressed in the proposal.

**Required citations:** G1 (X.509/CRL/OCSP — mandatory, will be assumed known and will be checked), G3 (VeriSBOM — mandatory, nearly identical mechanism), G2 (SBOM lifecycle guidance), A1/A3 (the certificate formats being extended).

**Questions they'd ask:** "What stops this from being described, accurately, as 'OCSP for regulations'? If that's a fair one-line summary, is a full paper's worth of novelty really here, or is this a workshop/short paper?" "What is the threat model if the classifier is wrong in the direction that keeps a certificate alive when it shouldn't be?"

---

## 8. Recommended Scope Refinement

Given §5–7, the smallest genuinely defensible unit is:

> **A benchmark and evaluation of substantive-vs-cosmetic legal-amendment classification, applied to the specific downstream task of deciding whether an LLM-issued compliance certificate should be revoked**, explicitly built *on top of* — not competing with — Akoma Ntoso/de Martim-style version addressing (C1–C3) and PKI/SBOM-style revocation mechanics (G1–G3).

Concretely narrow further by:

1. **Dropping** any claim to novelty on the certificate schema or the revocation protocol's mechanics — cite G1/G3/A1/A3 as the architecture being *adopted*, not invented. This defuses Reviewer 3's harshest criticism pre-emptively.
2. **Making the classifier a graded/multi-class or continuous materiality score**, not a binary label, per Reviewer 2 — and reporting inter-annotator agreement on the ground truth as a first-class result, per Reviewer 1.
3. **Explicitly benchmarking against DocuToads-style syntactic edit-distance and an LLM-judge/COLIEE-style entailment baseline** as the two mandatory comparators, since both reviewers named them independently.
4. **Adding an adversarial/security evaluation** (can the classifier be fooled into wrongly calling a substantive change cosmetic) — this converts Reviewer 3's objection into a results section instead of a weakness.
5. **Renaming away from "certificate revocation"** in the title/framing if the systems apparatus stays minimal — consider positioning as a legal-NLP/D&B benchmark paper first, with certificate-lifecycle management as the applied downstream *motivation* in the introduction, not the headline mechanism. This changes the natural target venue from a systems track to JURIX/ICAIL-with-benchmark or NeurIPS D&B, where the actual contribution (classifier + benchmark) is the expected unit of contribution.

---

## 9. Recommended Evaluation

- **Datasets:** eCFR point-in-time API (primary; confirmed public REST API with full amendment history back to 2017, raw XML to 2002) for the temporal-drift benchmark; consider a secondary jurisdiction (e.g., EU EUR-Lex CELEX consolidated-versions data, or UK legislation.gov.uk's versioned API) for a generalization/out-of-domain claim, since Reviewer 1 will ask if this is a US-only artifact.
- **Baselines:** DocuToads-style minimum-edit-distance typing (C5); zero-shot and fine-tuned LLM-judge (GPT-4/5-class); COLIEE-style NLI/entailment model (F3); a naive "revoke on any diff" and "never revoke" pair as trivial floor/ceiling baselines (mirrors the plan already discussed in this project's prior scoping conversation).
- **Metrics:** classifier precision/recall/F1 per class (or calibration error if scored continuously); inter-annotator agreement (Cohen's/Fleiss' kappa) on ground truth; downstream metric — false-revocation rate and missed-revocation rate when the classifier's output drives the actual certificate lifecycle end-to-end.
- **Statistical tests:** paired bootstrap or McNemar's test between classifier and each baseline on the same held-out clause pairs (standard for classification-comparison claims at ACL/EMNLP-adjacent venues, which several of the closest related papers, e.g. F1/F3, target).
- **Ablations:** raw text diff vs. structured Akoma-Ntoso/amendment-markup input; single-clause context vs. whole-section/whole-regulation context; effect of clause domain (financial vs. environmental vs. tax) on classifier transfer.
- **Error analysis:** manual review of false negatives (substantive changes misclassified as cosmetic) as the highest-stakes error class — quantify and characterize, since this is the failure mode Reviewer 3 will fixate on.
- **Limitations/threats to validity:** single-jurisdiction bias if only eCFR is used; ground-truth subjectivity (materiality is contested even among legal experts — report this honestly rather than presenting labels as ground truth); temporal leakage risk if the classifier's underlying LLM was pretrained on post-amendment text (mirrors F1's stated "temporal bias tied to training cutoffs" finding) — must be explicitly tested for.

---

## 10. Final Verdict

**Is it already published?** No, not as an integrated system, and not as the specific classifier-plus-certificate-revocation combination. But roughly 80% of its *individually named* components (version addressing, revocation architecture, temporal-consistency motivation) are independently and recently published, several by the same author (de Martim, C1/C2) or in adjacent domains (VeriSBOM, G3) within months of each other. This is a crowded, fast-moving space — the two most threatening papers (C2, F1, G3) all postdate the original literature review's search session by weeks and are all still preprints, meaning the gap could close further before submission.

**What remains genuinely novel?** The substantive-vs-cosmetic legal-amendment classifier, evaluated as the trigger condition for certificate lifecycle decisions, with a purpose-built temporal-drift benchmark. This is real, is not published, and is publishable — but it is a legal-NLP/benchmark contribution, not a systems or certificate-architecture contribution, and must be reframed and re-scoped accordingly (§8) to survive review.

**Publication-worthy?** Yes, conditional on the narrowing in §8 and the baselines/citations in §7 being addressed before submission — as currently scoped (full four-part pipeline, certificate-and-revocation framed as the headline), it is likely to draw a "combination of known techniques, insufficiently differentiated from de Martim/VeriSBOM/PKI" rejection at any of the four named venues.

---

## 11. Reading Priority List (Top 30, Ranked by Importance to This Idea)

1. de Martim — Modeling the Diachronic Evolution of Legal Norms (LRMoo), arXiv:2506.07853 [C2]
2. de Martim — SAT-Graph RAG, JURIX 2025 [C1]
3. Fan et al. — "Can LLMs Time Travel?" (LegalSearch-R1), arXiv:2605.25920 [F1]
4. Castiglione, Ebrahimi, Khakpour — VeriSBOM, arXiv:2602.13682 [G3]
5. OASIS LegalDocML TC — Akoma Ntoso v1.0 [C3a]
6. IETF — RFC 6960 (OCSP) / X.509 CRL background [G1]
7. Hermansson, Cross — DocuToads, arXiv:1608.06459 [C5]
8. NTIA/CISA — SBOM Minimum Elements & lifecycle guidance [G2]
9. Koomullil — Proof-Carrying Certificates for LLM Pipelines, arXiv:2605.16407 [A1]
10. Avni, Dolev, Yagudaev, Yung — Proof-Carrying Output, IACR ePrint 2026/994 [A3]
11. Kamran, Devanbu, Stanford — PC³, ASEW'24 [A2]
12. Yadamsuren, Platt, Diaz — LLM-Assisted Formalization (IRC), arXiv:2511.11954 [B4]
13. Hsia, Yu, Jiang — Neuro-Symbolic Compliance, ACM AIware'26 [B1]
14. An et al. — ARc Neurosymbolic NL Formalization, arXiv:2511.09008 [B2]
15. Bonatti et al. — PrOnto/OWL2 GDPR, *Artificial Intelligence* 2020 [C4, seminal]
16. European Union — AI Act Article 44 (Certificates) [H2]
17. Lam et al. — Assurance Audits Framework, FAccT 2024 [H1]
18. COLIEE Task 4 (Statute Law Entailment) — competition series [F3]
19. Blair-Stanek, Holzenberger, Van Durme — BLT, arXiv:2311.09693 [F2]
20. Nguyen et al. — GDPR Auto-Formalization, ICAIL 2026 [D3]
21. Chung et al. — GraphCompliance, arXiv:2510.26309 [D1]
22. Su et al. — NSVIF, arXiv:2601.17789 [B3]
23. Li et al. — Compliance-to-Code / FinCheck, arXiv:2505.19804 [D2]
24. Chen, Lin, Jiang, An — Automated BIM Compliance, *Buildings* 2024 [D4]
25. Dibowski — Full Traceability and Provenance for Knowledge Graphs, FOIS 2024 [G4]
26. "Time Travel for Knowledge Graphs," arXiv:2210.02534 [G5] **[unverified full author list]**
27. NLP for Requirements Traceability (survey), arXiv:2405.10845 [I1] **[unverified full author list]**
28. "The Legislative Recipe: Syntax for Machine-Readable Legislation," arXiv:2108.08678 (Rules-as-Code background)
29. Torroba Hennigen et al. — SymGen, arXiv:2311.09188 [E1]
30. Khajavi, Sadeghi, Adhikari, Tessier — CiteCheck, arXiv:2605.27700 [E2]

---

## 12. Bibliography (IEEE Format)

[C1] H. de Martim, "An Ontology-Driven Graph RAG for Legal Norms: A Structural, Temporal, and Deterministic Approach," in *Legal Knowledge and Information Systems (JURIX 2025)*, Frontiers in AI and Applications, IOS Press, 2025.

[C2] H. de Martim, "Modeling the Diachronic Evolution of Legal Norms: An LRMoo-Based, Component-Level, Event-Centric Approach to Legal Knowledge Graphs," arXiv:2506.07853, Jun. 2025 (rev. Jun. 2026).

[C3a] OASIS LegalDocML Technical Committee, "Akoma Ntoso Version 1.0, Part 1: XML Vocabulary," OASIS Standard, 2015+ (public review announced 2015).

[C3b] Akoma Ntoso Project, "Legislative Change Management with Akoma-Ntoso," conference/workshop paper. **[unverified exact venue — confirm before citing]**

[C4] P. A. Bonatti, L. Ioffredo, I. M. Petrova, L. Sauro, and I. R. Siahaan, "Real-Time Reasoning in OWL2 for GDPR Compliance," *Artificial Intelligence*, vol. 289, 2020, doi: 10.1016/j.artint.2020.103389.

[C5] H. Hermansson and J. P. Cross, "Tracking Amendments to Legislation and Other Political Texts with a Novel Minimum-Edit-Distance Algorithm: DocuToads," arXiv:1608.06459, Aug. 2016.

[A1] G. Koomullil, "Proof-Carrying Certificates for LLM Pipelines: A Trust-Boundary Architecture," arXiv:2605.16407, May 2026.

[A2] P. Kamran, P. Devanbu, and C. Stanford, "Vision Paper: Proof-Carrying Code Completions," in *Proc. 39th IEEE/ACM Int. Conf. Automated Software Engineering Workshops (ASEW '24)*, 2024, doi: 10.1145/3691621.3694932.

[A3] H. Avni, S. Dolev, A. Yagudaev, and M. Yung, "Super-Intelligence Survival Guide: Verification via Proof-Carrying Output," Cryptology ePrint Archive, Paper 2026/994, May 2026.

[B1] Y.-S. Hsia, F. Yu, and J.-H. R. Jiang, "Neuro-Symbolic Compliance: Integrating LLMs and SMT Solvers for Automated Financial Legal Analysis," in *Proc. 2nd ACM Int. Conf. AI-Powered Software (AIware)*, 2026, arXiv:2601.06181.

[B2] C. An et al., "A Neurosymbolic Approach to Natural Language Formalization and Verification," arXiv:2511.09008, Nov. 2025 (rev. Jul. 2026).

[B3] Y. Su, K. Xu, Y. Gao, F. Yang, C. Li, M. Yang, and T. Xu, "Neuro-Symbolic Verification on Instruction Following of LLMs," arXiv:2601.17789, Jan. 2026.

[B4] B. Yadamsuren, S. K. Platt, and M. Diaz, "LLM-Assisted Formalization Enables Deterministic Detection of Statutory Inconsistency in the Internal Revenue Code," arXiv:2511.11954, Nov. 2025.

[D1] J. Chung, R. Ko, W. Yoo, M. Onizuka, S. Kim, T.-W. Kim, and W.-Y. Shin, "GraphCompliance: Aligning Policy and Context Graphs for LLM-Based Regulatory Compliance," arXiv:2510.26309, Oct. 2025.

[D2] S. Li et al., "Compliance-to-Code: Enhancing Financial Compliance Checking via Code Generation," arXiv:2505.19804, May 2025 (rev. Jan. 2026).

[D3] H. T. Nguyen et al., "GDPR Auto-Formalization with AI Agents and Human Verification," in *Proc. Int. Conf. Artificial Intelligence and Law (ICAIL 2026)*, 2026.

[D4] N. Chen, X. Lin, H. Jiang, and Y. An, "Automated Building Information Modeling Compliance Check through a Large Language Model Combined with Deep Learning and Ontology," *Buildings*, vol. 14, no. 7, art. 1983, 2024, doi: 10.3390/buildings14071983.

[E1] L. Torroba Hennigen et al., "Towards Verifiable Text Generation with Symbolic References," arXiv:2311.09188, Nov. 2023 (rev. Apr. 2024).

[E2] K. Khajavi, S. Sadeghi, R. Adhikari, and A. Tessier, "CiteCheck: Retrieval-Grounded Detection of LLM Citation Hallucinations in Scientific Text," arXiv:2605.27700, May 2026.

[F1] W. Fan et al., "Can LLMs Time Travel? Enhancing Temporal Consistency in Legal Agentic Search through Reinforcement Learning," arXiv:2605.25920, May 2026.

[F2] A. Blair-Stanek, N. Holzenberger, and B. Van Durme, "BLT: Can Large Language Models Handle Basic Legal Text?" arXiv:2311.09693, Nov. 2023 (rev. Oct. 2024).

[F3] COLIEE Organizing Committee, "Competition on Legal Information Extraction/Entailment (COLIEE), Task 4: Statute Law Entailment," ongoing competition series, JURIX/ICAIL-affiliated workshops.

[G1] Internet Engineering Task Force, "X.509 Internet Public Key Infrastructure Online Certificate Status Protocol (OCSP)," RFC 6960, 2013; and X.509 Certificate Revocation List (CRL) specification background.

[G2] National Telecommunications and Information Administration / Cybersecurity and Infrastructure Security Agency, "Software Bill of Materials (SBOM) Minimum Elements and Lifecycle Guidance," US federal guidance, 2021–2026.

[G3] G. Castiglione, S. Ebrahimi, and N. Khakpour, "VeriSBOM: Secure and Verifiable SBOM Sharing Via Zero-Knowledge Proofs," arXiv:2602.13682, Feb. 2026.

[G4] H. Dibowski, "Full Traceability and Provenance for Knowledge Graphs," in *Proc. Formal Ontology in Information Systems (FOIS 2024)*, 2024.

[G5] "Time Travel for Knowledge Graphs: Live Queries Over RDF Change Histories," arXiv:2210.02534. **[author list unverified — confirm before citing]**

[H1] K. Lam, B. Lange, B. Blili-Hamelin, J. Davidovic, S. Brown, and A. Hasan, "A Framework for Assurance Audits of Algorithmic Systems," in *Proc. 2024 ACM Conf. on Fairness, Accountability, and Transparency (FAccT '24)*, 2024, arXiv:2401.14908.

[H2] European Union, "Regulation (EU) 2024/1689 (Artificial Intelligence Act), Article 44: Certificates," 2024.

[I1] "Natural Language Processing for Requirements Traceability" (survey), arXiv:2405.10845, 2024. **[author list unverified — confirm before citing]**

---

*Verification notes: entries marked [unverified] were located via search-result snippets rather than a directly fetched primary page and require confirmation before use in an actual submission's bibliography — this is a pre-registration/scoping review, not a submission-ready reference list. All other entries were confirmed via direct fetch of arXiv/publisher/standards-body pages, except A2 (ACM DL, 403) and C4/D4 (ScienceDirect/MDPI, 403), each cross-confirmed via a second independent source (search snippet + secondary listing) per the methodology used in the prior literature review for this project. This search, like the first, was a single non-exhaustive session (2026-07-24) and is not PRISMA-registered.*
