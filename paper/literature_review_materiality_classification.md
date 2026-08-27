# Literature Review

## Materiality Classification of Regulatory Amendments: An eCFR Temporal Drift Benchmark for LLM-Derived Compliance Assertions

*This is the literature review for the paper's current, corrected scope — a legal-NLP benchmark and classification task, not a systems/certificate paper. It supersedes `literature_review_certificate_carrying_generation.md` (written for the original, broader "Certificate-Carrying Generation" topic) and consolidates the corpus verified across `adversarial_novelty_review_version_revocable_certificates.md` and `adversarial_review_2_materiality_classifier_benchmark.md`. No new searches were run for this file; all sources below were individually fetched and verified in those two prior review passes. Report date: 2026-07-24.*

---

## 1. Introduction

Regulatory text changes constantly, but not every change carries legal weight. A renumbered subsection, a corrected typo, or an updated cross-reference leaves compliance obligations untouched; a revised threshold, a narrowed exception, or an added penalty does not. Any system that generates, retrieves, or certifies compliance assertions from regulatory text — an LLM answering "does this practice satisfy 21 CFR §X," a retrieval system surfacing "the applicable rule," or a certificate attesting that an assertion was checked against a specific version of a standard — inherits this ambiguity as a silent failure mode: nothing in the current literature tells such a system whether an amendment it just observed actually matters.

This review asks a narrow, falsifiable question: **does a benchmark or classifier already exist for deciding whether a regulatory amendment is legally consequential ("substantive") or merely cosmetic, and if not, what is the smallest defensible contribution that fills the gap?** The answer, established across two rounds of adversarial literature search, is that the *benchmark* does not exist — three flagship legal-NLP benchmark suites were checked directly and confirmed to lack it — but the *task type* is not new. It has been solved three times over in other document domains. The paper's actual contribution is therefore a **domain-transfer and new-benchmark contribution**: applying an established classification task to a domain (regulatory text) where the ground truth is a contested legal-interpretive judgment rather than a checkable factual difference.

### 1.1 Subdomains Covered

1. **General-purpose document-revision/edit classification** — the task's true methodological origin, in non-legal domains.
2. **Legal-NLP benchmark suites** — checked directly to establish that no existing resource covers this task.
3. **Legal document versioning and temporal representation** — the infrastructure this work consumes (point-in-time addressing) without competing with it.
4. **Legal-domain amendment/change detection** — the closest legal-specific prior art, and the paper's central empirical baseline.
5. **Legal NLP temporal reasoning and entailment** — adjacent problem framings and evaluation-methodology precedent.
6. **Long-document legal encoders** — a baseline architecture class.
7. **Downstream motivation (compliance certification/revocation)** — cited only as the applied context motivating the task, not as related work being extended.

---

## 2. Research Background

Two literatures that had not previously been cross-cited converge on this task. The first is a **general NLP subfield on document-revision classification**, which emerged around Wikipedia edit histories (2013), matured with large-scale news-revision corpora (2022), and has recurred independently in educational NLP (student-writing revision, 2019–2023) and in industry (a general-purpose patent on classifying document-version changes by significance). Across all of these, the task shape is identical: given two versions of a text and a diff, classify the edit by type or significance. The second is **legal-AI's temporal/versioning literature**, which has matured rapidly since 2020 around representing *which version of a law applied when* — from a static, hand-encoded compliance ontology (PrOnto/OWL2, 2020) to point-in-time legal knowledge graphs (SAT-Graph RAG, 2025) to reinforcement-learned temporal-consistency retrieval (LegalSearch-R1, 2026). This literature solves *addressing* a version of a text; it does not classify what changed *between* versions.

Legal-domain amendment detection sits at the seam between these two literatures and is thin: essentially one direct precedent (DocuToads, 2016), which is purely syntactic (it types edits as insertions/deletions/substitutions/transpositions via minimum edit distance) and explicitly notes its own failure mode — automated detection can miss changes human coders would flag as substantive, and vice versa. No legal-domain work has imported the *semantic* materiality-classification task from the Wikipedia/news lineage. That is the specific, narrow seam this review locates.

---

## 3. Existing Methods — Annotated Bibliography with Deep Analysis

### Cluster A — General-Purpose Document-Revision & Edit-Materiality Classification (the task's true ancestry)

**[1] Daxenberger and Gurevych (2013), "Automatically Classifying Edit Categories in Wikipedia Revisions," EMNLP 2013, pp. 578–589.**
- *Problem:* Automatically classify the *type* of a Wikipedia edit (e.g., spelling correction, paraphrase, vandalism, content addition) from a version diff.
- *Method:* Supervised classifier trained on features derived from meta-data, textual properties, language properties, and markup differences between the two document versions.
- *Data:* English Wikipedia revision corpus, multi-labeled according to a 21-category taxonomy.
- *Results:* Micro-averaged F1 = 0.62.
- *Strengths:* Establishes, in a peer-reviewed EMNLP paper, the exact feature-engineering and evaluation template this proposal reuses; large, well-studied corpus; taxonomy already distinguishes low-stakes (spelling, formatting) from high-stakes (content, vandalism) categories, structurally parallel to cosmetic/substantive.
- *Weaknesses/Limitations:* Wikipedia edits have a checkable ground truth (did the encyclopedic fact change), unlike legal materiality, which is an interpretive judgment about downstream legal effect, not a verifiable fact; F1 of 0.62 on a 21-way task suggests the underlying feature approach is far from solved even in its home domain; 2013-vintage features predate transformer-based methods entirely.
- *Assumptions:* That edit type is recoverable from surface diff features (metadata, text, markup) without deep semantic/world-knowledge reasoning — an assumption weaker for legal materiality, where a one-word threshold change (e.g., "30 days" → "15 days") is low-edit-distance but high-materiality.
- *Relation to proposed work:* **This is the paper's direct methodological ancestor and must be cited as such**, not discovered independently by a reviewer. The proposed classifier should be positioned explicitly as: this task, transplanted to a domain where the ground truth is categorically harder (interpretive, not factual), with a purpose-built retrained version serving as a mandatory baseline.
- *Opportunity for improvement:* No legal-domain adaptation exists; transformer-era re-implementation as a modern baseline is straightforward and necessary.

**[2] Spangher, Ren, May, and Peng (2022), "NewsEdits: A News Article Revision Dataset and a Document-Level Reasoning Challenge," NAACL 2022.**
- *Problem:* Build a large-scale resource for studying how news articles evolve across revisions, and test whether models can reason about/forecast the *type* of edit made.
- *Method:* Large-scale revision-history mining across many news sources; defines four article-level edit types (Addition, Deletion, Edit, Refactor) via a high-accuracy extraction algorithm; three document-level reasoning/prediction tasks built on top.
- *Data:* 1.2 million articles, 4.6 million versions, 22 English- and French-language sources, 2006–2021.
- *Results:* Humans predict edit actions reasonably well; large NLP models of the time struggle with the document-level reasoning required. A key finding: added/deleted sentences are more likely to contain "updating events," main content, and quotes than unchanged sentences — a materiality-adjacent signal (edits cluster where meaning changes).
- *Strengths:* Demonstrates feasibility and value of a *large-scale, versioned-document benchmark with a reasoning task layered on top* — directly the shape of resource this proposal builds, just orders of magnitude larger (appropriately, since news articles are cheap to label at scale and legal materiality is not); the "updating event" finding is independent evidence that meaning-change and edit-location correlate, supporting the underlying premise that materiality is learnable from diff context.
- *Weaknesses/Limitations:* News domain, not legal; edit-type taxonomy (Addition/Deletion/Edit/Refactor) is structural, not a substantive/cosmetic materiality judgment; no legal-interpretive ground truth challenge, since journalistic "updates" are factual corrections with a checkable source of truth (unlike contested legal materiality).
- *Assumptions:* That edit-type classification generalizes from a large, cheaply-labeled corpus — an assumption this proposal cannot make, since legal-expert annotation is expensive and the benchmark will necessarily be smaller.
- *Relation to proposed work:* The closest available precedent for *benchmark structure and scale-justification argument* (i.e., how to argue that a smaller, expert-annotated legal benchmark is appropriately scoped relative to a large, cheaply-labeled precedent like this one) — cite directly when justifying dataset size.
- *Opportunity for improvement:* No version of this resource exists for regulatory/legal text; the "updating event concentrates near edits" finding has not been tested for a "materiality concentrates near edits" analogue in law.

**[3] Litman-lineage revision-classification work in argumentative/student writing (multiple papers, 2019–2023, incl. "Annotation and Classification of Evidence and Reasoning Revisions in Argumentative Writing," 2021, and "Predicting Desirable Revisions of Evidence and Reasoning in Argumentative Writing," 2023).**
- *Problem:* Classify or predict whether a revision to a student argumentative essay is "desirable" (improves evidence/reasoning quality) from a version pair.
- *Method:* Supervised classification over annotated revision pairs in student-writing corpora.
- *Strengths:* A third independent domain (after Wikipedia and news) applying the identical task shape, reinforcing that edit-significance classification is a recurring, cross-domain NLP problem, not a one-off.
- *Weaknesses/Limitations:* Education domain; "desirable" is a pedagogical judgment, not a legal one; smaller-scale corpora than NewsEdits.
- *Relation to proposed work:* Supporting evidence for the "this task recurs across domains, legal text is the notable absence" framing; secondary citation, not a primary baseline source.

**[4] US Patent 10,713,432 B2 (Adobe Inc.), "Classifying and Ranking Changes Between Document Versions."**
- *Problem/Claim:* A general-purpose, domain-agnostic system for classifying and ranking changes between document versions by significance, explicitly distinguishing "factual changes" from "paraphrasing changes."
- *Strengths (as prior art):* A granted patent, not merely an academic proposal — establishes that the *general* task-level idea of substantive-vs-non-substantive document-change classification is commercially claimed, by a major software company, at the domain-agnostic level.
- *Weaknesses/Limitations:* Not legal-domain-specific; no public evaluation/benchmark; exact grant date and full claim scope require direct verification via Google Patents/USPTO before citing in a submission-ready bibliography.
- *Relation to proposed work:* Not a competing academic contribution, but a **required limitations-section disclosure**: any claim to novelty must be framed as domain-specific (legal materiality) and academic (dataset/benchmark), explicitly not as inventing the general classification mechanism, which is already patented.

### Cluster B — Legal-NLP Benchmark Landscape (checked directly, confirmed absent)

**[5] Guha et al. (40 authors) (2023), "LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models," NeurIPS 2023 (Datasets and Benchmarks track).**
- *Problem:* Provide a comprehensive, collaboratively-built benchmark for evaluating legal reasoning in LLMs.
- *Method:* 162 (later 230+) tasks contributed by 40+ authors, organized into six reasoning categories (issue-spotting, rule-recall, rule-application, rule-conclusion, interpretation, and others), spanning statutes, contracts, and judicial opinions.
- *Strengths:* The largest, most authoritative legal-LLM benchmark; directly and exhaustively checked (full task list reviewed) for this review.
- *Weaknesses/Limitations relevant here:* **Confirmed to contain no amendment-classification, temporal-versioning, or cross-version-comparison task.** The closest tangential match (a "policy_change" task within the OPP-115 privacy-policy suite) measures whether a policy *discloses* changes, not the *nature* of the change itself.
- *Relation to proposed work:* Direct, load-bearing evidence for the benchmark's non-existence — cite as "we reviewed LegalBench's complete task taxonomy and found no analogous task," not as a vague absence claim.

**[6] Chalkidis, Jana, Hartung, Bommarito, Androutsopoulos, Katz, and Aletras (2022), "LexGLUE: A Benchmark Dataset for Legal Language Understanding in English," ACL 2022.**
- *Problem:* A GLUE/SuperGLUE-style standardized benchmark for legal NLU.
- *Method:* Aggregates seven existing legal NLP datasets (ECtHR Tasks A/B, SCOTUS, EUR-Lex, LEDGAR, UNFAIR-ToS, CaseHOLD) into a common evaluation suite, mostly single-document classification.
- *Weaknesses/Limitations relevant here:* All seven tasks are single-snapshot classification or entailment; none involve comparing two versions of the same legal text over time.
- *Relation to proposed work:* Second confirmation that the flagship benchmark landscape does not cover this task.

**[7] Hendrycks, Burns, Chen, and Ball (2021), "CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review," NeurIPS 2021 (Datasets and Benchmarks track).**
- *Problem:* Identify 41 categories of clauses important to contract review from a single contract.
- *Method:* Expert-annotated span extraction over 510 commercial contracts (SEC EDGAR).
- *Weaknesses/Limitations relevant here:* Single-version clause *importance* extraction, not cross-version *change* comparison; contracts, not regulations.
- *Relation to proposed work:* Off-topic as a task, but a useful **scale/rigor precedent** — a 510-document, expert-annotated benchmark is a credible reference class for justifying a similarly-scoped (hundreds to low-thousands of pairs) expert-annotated legal benchmark, rather than requiring NewsEdits-scale (millions) data.

### Cluster C — Legal Document Versioning & Temporal Representation (infrastructure, not competing work)

**[8] de Martim (2025), "An Ontology-Driven Graph RAG for Legal Norms: A Structural, Temporal, and Deterministic Approach" (SAT-Graph RAG), JURIX 2025.**
- *Problem:* Standard retrieval cannot distinguish active from superseded regulation or explain retrieval via legal-citation structure.
- *Method:* Formal ontology distinguishing abstract legal "Works" from versioned "Expressions"; legislative events (amendments, repeals) as queryable graph nodes.
- *Strengths:* Peer-reviewed (JURIX); solves point-in-time *addressing* to the point of "exact reconstruction... as it existed on a specific date."
- *Weaknesses/Limitations relevant here:* Does not classify the *significance* of an amendment event, only its existence and temporal location; single jurisdiction (Brazilian Constitutional law).
- *Relation to proposed work:* **Infrastructure this work could sit on top of, not a competing contribution.** Cite as the addressing scheme that would consume this classifier's output in a downstream system, explicitly not as prior art for the classification task itself.

**[9] de Martim (2025/26), "Modeling the Diachronic Evolution of Legal Norms: An LRMoo-Based, Component-Level, Event-Centric Approach to Legal Knowledge Graphs," arXiv:2506.07853.**
- *Problem/Method:* Extends [8] with a "Temporal Version" subclass of Expression for component-level, date-precise reconstruction of legal text.
- *Relation to proposed work:* Same positioning as [8] — deeper addressing infrastructure, still no materiality/significance classification layer.

**[10] Bonatti, Ioffredo, Petrova, Sauro, and Siahaan (2020), "Real-Time Reasoning in OWL2 for GDPR Compliance," *Artificial Intelligence*, vol. 289. [Seminal]**
- *Problem/Method:* Sound, real-time GDPR compliance reasoning via a hand-encoded OWL2 policy ontology (PrOnto) and specialized reasoner.
- *Weaknesses/Limitations relevant here:* Static, hand-encoded, predates any notion of automated versioning or LLM-derived assertions; brittle to regulatory change by construction — the exact brittleness that later work ([8], [9], and this proposal) exists to address.
- *Relation to proposed work:* Seminal formal-soundness baseline establishing what full rigor costs; background context for why generation-based, text-adaptive approaches emerged.

### Cluster D — Legal Amendment/Change Detection (the direct legal-domain baseline)

**[11] Hermansson and Cross (2016), "Tracking Amendments to Legislation and Other Political Texts with a Novel Minimum-Edit-Distance Algorithm: DocuToads," arXiv:1608.06459.**
- *Problem:* Detect and categorize amendments to legislative and political texts.
- *Method:* Minimum-edit-distance (Levenshtein) algorithms, typing changes as insertions, deletions, substitutions, and transpositions.
- *Strengths:* Directly validated by replicating existing legislative-studies research; demonstrated superior to hand-coded efforts on speed/cost; the single closest legal-domain amendment-detection precedent.
- *Weaknesses/Limitations:* **Purely syntactic** — cannot distinguish "§4.2 renumbered to §4.3" (cosmetic, large edit distance) from "'30 days' changed to '15 days'" (substantive, tiny edit distance); the authors themselves note that automated detection identifies changes human coders miss, and vice versa, evidencing that syntactic typing and semantic materiality diverge.
- *Relation to proposed work:* **The paper's central empirical foil and mandatory baseline.** The contrast between DocuToads' syntactic typing and this proposal's semantic materiality judgment on small-edit/high-materiality cases is the paper's headline empirical hook.
- *Opportunity for improvement:* No semantic/materiality layer exists on top of this syntactic foundation for legal text — directly the gap this proposal fills.

### Cluster E — Legal NLP Temporal Reasoning & Entailment (adjacent problem framings, methodology precedent)

**[12] Fan, Zhou, Zhang, Weng, Hu, Zheng, Xu, Li, Yang, Li, and Song (2026), "Can LLMs Time Travel? Enhancing Temporal Consistency in Legal Agentic Search through Reinforcement Learning" (LegalSearch-R1), arXiv:2605.25920.**
- *Problem:* LLM search agents ignore temporal constraints in law; "the same case facts can yield opposite conclusions under different amendments."
- *Method:* RL-trained retrieval+search agent combining local statute RAG with web search, trained on temporally-indexed data spanning multiple amendment periods.
- *Results:* 7B-parameter agent shows 12.9–29.8% improvement over specialized legal models and 57.7–80.3% improvement on temporal-consistency measures across a 13-task benchmark.
- *Strengths:* States almost verbatim the motivating problem for this proposal's downstream use case; quantified temporal-consistency gains; recent (2026), active area.
- *Weaknesses/Limitations relevant here:* Solves temporal consistency *proactively* at generation/retrieval time (get the currently-correct answer), not *reactively* (classify whether a specific already-observed amendment matters) — a genuinely different task, but close enough in framing that the paper must explicitly differentiate itself from this work in its opening paragraphs.
- *Relation to proposed work:* Closest problem-framing neighbor; cite prominently and differentiate explicitly by task direction (retrieval-time correctness vs. standalone materiality judgment on historical pairs).

**[13] Blair-Stanek, Holzenberger, and Van Durme (2023/24), "BLT: Can Large Language Models Handle Basic Legal Text?" arXiv:2311.09693.**
- *Problem:* Establish whether LLMs can perform basic legal-text-handling tasks (e.g., retrieving a specific passage from a deposition or contract subsection) without fine-tuning.
- *Results:* Major LLMs (GPT-4, Claude) perform inadequately zero-shot; fine-tuning even smaller models on the benchmark's training data achieves near-perfect results.
- *Relation to proposed work:* Motivational evidence that general-purpose LLMs cannot be trusted zero-shot on precise legal-text tasks, supporting the need for a purpose-built, fine-tuned/trained materiality classifier rather than relying solely on prompted LLM judges.

**[14] COLIEE Task 4 (Statute Law Entailment), ongoing competition series, JURIX/ICAIL-affiliated.**
- *Problem:* Recognize entailment between a statute article and a factual statement (yes/no).
- *Method:* BERT/transformer-based entailment models, evaluated in an established shared-task format.
- *Relation to proposed work:* Supplies a mature entailment-evaluation methodology directly adaptable as a baseline — "does the amended clause entail/contradict the compliance-relevant content of the prior clause" reframes materiality classification as a COLIEE-style entailment problem, giving the proposal a well-precedented fine-tuned-model baseline architecture.

### Cluster F — Long-Document Legal Encoders (baseline architecture class)

**[15] Xiao, Hu, Liu, Tu, and Sun (2021), "Lawformer: A Pre-trained Language Model for Chinese Legal Long Documents," *AI Open*, vol. 2, pp. 79–84.**
- *Problem:* Mainstream pretrained language models cannot process the long documents (thousands of tokens) typical of legal text.
- *Method:* Longformer-style long-document pretraining on Chinese legal corpora.
- *Results:* Improvements on judgment prediction, similar-case retrieval, legal reading comprehension, and legal QA.
- *Weaknesses/Limitations relevant here:* Chinese-language only, not directly applicable to English eCFR text.
- *Relation to proposed work:* Represents the architecture *class* (fine-tuned long-document legal encoder) that an English equivalent (Legal-BERT/Longformer-class model) should serve as in the baseline suite — a distinct comparator from both prompted LLM judges and generic edit-classifiers.

### Cluster G — Downstream Motivation Only (compliance certification/revocation — cited in the Introduction, not as related work)

**[16] Koomullil (2026), "Proof-Carrying Certificates for LLM Pipelines: A Trust-Boundary Architecture," arXiv:2605.16407.**
**[17] Castiglione, Ebrahimi, and Khakpour (2026), "VeriSBOM: Secure and Verifiable SBOM Sharing Via Zero-Knowledge Proofs," arXiv:2602.13682.**
**[18] European Union, "Regulation (EU) 2024/1689 (Artificial Intelligence Act), Article 44: Certificates," 2024.**

- *Role:* These establish, respectively, that LLM-pipeline certificates are an active 2026 research direction, that "revoke a proof when a root fact changes" is a proven architecture in an adjacent domain (software supply chain), and that certificate suspension-on-changed-compliance-status is already legally mandated for AI systems in the EU. None classify amendment materiality. Cited exclusively in the paper's Introduction as the applied context motivating why materiality classification matters, never as related work the paper extends or competes with — this separation is deliberate and load-bearing for the paper's framing (see §7).

---

## 4. Comparative Analysis

Overlaying Clusters A–G exposes a clean division: **Cluster A** (Wikipedia/news/writing revision classification) solves the *task shape* but never touches legal text. **Cluster B** (LegalBench/LexGLUE/CUAD) is the legal-NLP field's actual benchmark inventory and, checked directly, does not contain this task. **Cluster C** (SAT-Graph RAG, LRMoo, PrOnto) solves *where* a version of a law lives in time but not *whether* a given transition between versions matters. **Cluster D** (DocuToads) is the one legal-specific amendment-detection precedent, and it is explicitly syntactic, not semantic. **Cluster E** (LegalSearch-R1, BLT, COLIEE) supplies adjacent problem framings and evaluation methodology but attacks a different task (retrieval-time correctness, general legal-text competence, or general entailment) rather than post-hoc materiality judgment. No cluster combines Cluster A's task type with Cluster D's domain and Cluster B's benchmark rigor. That intersection — confirmed unoccupied by direct inspection, not inference — is the paper's contribution.

---

## 5. Research Gaps

1. **No legal-domain adaptation of an established task.** Materiality/significance classification of document edits is solved in Wikipedia (2013), news (2022), and student writing (2019–2023); it has never been applied to regulatory or statutory text. **Why it persists:** legal materiality is a contested interpretive judgment (evidenced by DocuToads' own observation that automated and human amendment-detection disagree), unlike the largely fact-checkable ground truth available in Wikipedia/news domains — this makes annotation expensive and non-trivial in a way the source domains did not have to solve.
2. **No benchmark exists**, confirmed by direct inspection of the three most likely candidates (LegalBench, LexGLUE, CUAD). **Why it persists:** constructing gold labels requires legal-expert annotation with a defensible materiality taxonomy — a cost and methodological burden the general-purpose revision-classification literature did not have to bear (Wikipedia/news labels are comparatively cheap and less contested).
3. **No semantic layer over legal-domain syntactic change detection.** DocuToads types *how* text changed; nothing classifies *whether it matters*. **Why it persists:** this requires exactly the cross-literature move (Cluster A's task onto Cluster D's domain) that, per this review, no prior work has made.
4. **No reported inter-annotator-agreement-honest treatment of legal materiality as a benchmark design choice.** Existing legal-NLP benchmarks (Cluster B) do not, in general, report IAA as a primary result for genuinely contested legal-interpretive tasks; most legal-NLP classification tasks have comparatively higher-consensus ground truth (e.g., statute retrieval, contract clause presence) than "does this amendment change legal meaning."
5. **A general-purpose patent (Adobe, US10,713,432 B2) already exists for domain-agnostic document-change classification**, meaning any claim to novelty at the *general mechanism* level (not the legal-domain application) is foreclosed — a gap in the *academic* literature specifically, not in prior art overall, and one this proposal must navigate by claiming only the domain-specific, benchmark-level contribution.

---

## 6. Critical Discussion

The corpus shows two research communities that have independently solved adjacent halves of this problem without ever citing each other: the general-NLP document-revision-classification community (Cluster A), which has iterated on this exact task shape across three domains over roughly a decade, and the legal-AI temporal-representation community (Cluster C), which has, in the last two years, become highly sophisticated about *addressing* versions of legal text without ever asking whether a given version transition is meaningful. DocuToads (Cluster D) sits at the boundary and is the strongest evidence that this is a real gap rather than an oversight: it is the one paper that tried to detect legal amendments computationally, a decade ago, and it deliberately stopped at syntactic typing — a plausible reading is that semantic materiality judgment was simply out of reach for 2016-era NLP, not that it was judged unimportant. The intervening decade of transformer-based entailment and classification methods (Clusters A, E, F) now makes the semantic version of this task tractable, which is arguably why this gap is closable *now* in a way it was not when DocuToads was published — a useful, honest "why now" argument for the paper's introduction. The one serious risk this discussion must confront honestly: LegalSearch-R1 (Cluster E) is recent (2026) evidence that the broader legal-AI field is actively working on temporal-consistency problems, meaning this specific gap could close from an adjacent direction before this paper is submitted; a literature-monitoring check immediately before submission is warranted.

---

## 7. Motivation for Proposed Work

The motivating scenario — an LLM-issued compliance certificate that should be reconsidered when its underlying regulation is amended — sits downstream of Cluster G (certificate architectures, revocation mechanisms, and the EU AI Act's mandate that certificates respond to changed compliance status) but the paper does not claim any contribution in that cluster. Every certificate/revocation architecture found (PKI-style, SBOM-style, LLM-pipeline-certificate-style) revokes on an unambiguous binary fact (key compromise, CVE disclosure, failed conformity re-assessment); none of them can decide whether an amendment is the kind of event that *should* trigger revocation in the first place, because that decision requires exactly the semantic materiality judgment Cluster A's task type provides and Cluster D's legal-domain literature has not yet built. The proposed benchmark and classifier is the minimal, well-scoped piece that closes this specific, confirmed-unoccupied gap — motivated by, but not claiming to solve, the larger certificate-lifecycle problem.

---

## 8. Summary

Eighteen sources across seven clusters establish that materiality classification of regulatory amendments is a **domain-transfer gap, not an unsolved task type**: the classification task itself is mature (Wikipedia 2013, news 2022, student writing 2019–2023, and a general-purpose 2020-era patent), and has simply never been pointed at legal or regulatory text, where DocuToads (2016) remains the only legal-domain amendment-detection precedent and is explicitly syntactic rather than semantic. Three flagship legal-NLP benchmarks (LegalBench, LexGLUE, CUAD) were checked directly and confirmed to lack this task, and the legal-versioning literature that has matured since 2020 (PrOnto, SAT-Graph RAG, LRMoo) solves *addressing* a version of the law without ever classifying *whether a transition between versions matters*. The defensible contribution is therefore precise: the first benchmark and evaluation of materiality classification for regulatory amendments, built on eCFR's public version history, evaluated against baselines drawn honestly from its true methodological ancestors (a retrained general-purpose revision classifier, DocuToads, a fine-tuned legal-entailment model, and a fine-tuned long-document legal encoder), with inter-annotator agreement reported as a primary result given that legal materiality is a contested judgment even among trained annotators. A general-purpose patent already covers the domain-agnostic version of this mechanism and must be disclosed rather than treated as a novelty claim.

---

## 9. Comparative Table

| # | Paper | Year | Venue | Problem | Method | Dataset | Strengths | Weaknesses | Research Gap Addressed | Relevance |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Daxenberger & Gurevych, "Automatically Classifying Edit Categories in Wikipedia Revisions" | 2013 | EMNLP | Classify Wikipedia edit type from diff | Supervised classifier, diff features, 21-class taxonomy | English Wikipedia revisions | Establishes task shape and evaluation template | Checkable ground truth, not interpretive; pre-transformer | None (this is the ancestor) | Very High — methodological parent |
| 2 | Spangher, Ren, May, Peng, "NewsEdits" | 2022 | NAACL | Predict edit type/reasoning across news revisions | Large-scale revision mining + reasoning tasks | 1.2M articles, 4.6M versions | Scale/structure precedent; materiality-adjacent finding | News domain; not legal-interpretive | None (structural precedent) | High — scale-justification precedent |
| 3 | Litman-lineage, argumentative-writing revision classification | 2019–23 | ACL-affiliated | Classify "desirable" revisions in student writing | Supervised classification | Student essay revisions | Third domain confirming task recurrence | Education domain, not legal | None (supporting evidence) | Medium |
| 4 | US Patent 10,713,432 B2 (Adobe) | granted [unverified date] | USPTO | Classify/rank document-version changes by significance | Proprietary system, "factual" vs "paraphrasing" | N/A | Confirms general task is commercially claimed | Not legal-domain; no public eval | IP disclosure requirement | High — mandatory limitations disclosure |
| 5 | Guha et al., LegalBench | 2023 | NeurIPS D&B | Standardize legal-LLM evaluation | 230+ collaboratively-built tasks | Multi-source legal text | Confirms benchmark gap directly (full task list reviewed) | No amendment/version task | Benchmark-absence evidence | Very High |
| 6 | Chalkidis et al., LexGLUE | 2022 | ACL | Standardize legal NLU evaluation | 7-task GLUE-style suite | ECtHR, SCOTUS, EUR-Lex, etc. | Confirms benchmark gap directly | No change-detection task | Benchmark-absence evidence | High |
| 7 | Hendrycks et al., CUAD | 2021 | NeurIPS D&B | Extract important contract clauses | Expert-annotated span extraction | 510 contracts | Scale/rigor precedent for expert annotation | Single-version, off-topic task | Annotation-scale precedent | Medium |
| 8 | de Martim, SAT-Graph RAG | 2025 | JURIX | Point-in-time legal retrieval | Work/Expression ontology + graph | Brazilian Constitution | Solves version addressing | No significance classification | Addressing infrastructure only | High (as infrastructure) |
| 9 | de Martim, LRMoo diachronic model | 2025/26 | arXiv | Component-level temporal norm modeling | LRMoo "Temporal Version" | Brazilian Constitution | Deeper addressing precision | No significance classification | Addressing infrastructure only | High (as infrastructure) |
| 10 | Bonatti et al., PrOnto/OWL2 GDPR [Seminal] | 2020 | *Artificial Intelligence* | Real-time sound GDPR reasoning | Hand-encoded OWL2 ontology | N/A | Seminal formal baseline | Static, brittle to change | Motivates need for adaptive approaches | Medium |
| 11 | Hermansson & Cross, DocuToads | 2016 | arXiv | Detect/type legislative amendments | Minimum-edit-distance typing | Legislative/political texts | Only direct legal-domain precedent | Purely syntactic, not semantic | **Direct empirical gap and mandatory baseline** | Very High |
| 12 | Fan et al., LegalSearch-R1 | 2026 | arXiv (under review) | Temporal consistency in legal search | RL-trained retrieval agent | 13-task benchmark | Quantified temporal-consistency gains | Proactive, not post-hoc classification | Closest adjacent problem framing | High |
| 13 | Blair-Stanek et al., BLT | 2023/24 | arXiv | Baseline LLM legal-text competence | Benchmark + fine-tuning | Custom legal benchmark | Motivates fine-tuned over zero-shot approaches | Not amendment-specific | Motivational evidence | Medium |
| 14 | COLIEE Task 4 | ongoing | JURIX/ICAIL-affiliated | Statute entailment | Transformer entailment models | Japanese Civil Code | Mature entailment-eval methodology | Not amendment-specific | Baseline-architecture precedent | High |
| 15 | Xiao et al., Lawformer | 2021 | *AI Open* | Long-document legal LM | Longformer-style pretraining | Chinese legal corpora | Long-document architecture class | Chinese-only | Baseline-architecture class | Medium |
| 16 | Koomullil, Proof-Carrying Certificates for LLM Pipelines | 2026 | arXiv | Certify LLM-pipeline computation | Lean 4 certificate families | 4 pilots | Motivates downstream use case | No materiality classification | Motivation only (Introduction) | Low (as related work) |
| 17 | Castiglione et al., VeriSBOM | 2026 | arXiv | Verifiable SBOM sharing/revocation | ZK-proofs, root-fact revocation | N/A | Motivates downstream use case | Binary trigger, not semantic | Motivation only (Introduction) | Low (as related work) |
| 18 | EU AI Act, Article 44 | 2024– | Regulation | Legal mandate for certificate suspension | Conformity re-assessment | N/A | Legal legitimacy for downstream motivation | Conformity-triggered, not amendment-triggered | Motivation only (Introduction) | Low (as related work) |

---

## References (IEEE Format)

[1] J. Daxenberger and I. Gurevych, "Automatically Classifying Edit Categories in Wikipedia Revisions," in *Proc. 2013 Conf. on Empirical Methods in Natural Language Processing (EMNLP 2013)*, Seattle, WA, USA, 2013, pp. 578–589.

[2] A. Spangher, X. Ren, J. May, and N. Peng, "NewsEdits: A News Article Revision Dataset and a Document-Level Reasoning Challenge," in *Proc. 2022 Conf. of the North American Chapter of the Association for Computational Linguistics (NAACL 2022)*, 2022, arXiv:2206.07106.

[3] "Annotation and Classification of Evidence and Reasoning Revisions in Argumentative Writing," arXiv:2107.06990, 2021; and "Predicting Desirable Revisions of Evidence and Reasoning in Argumentative Writing," arXiv:2302.05039, 2023. *[full author lists unverified — confirm before citing]*

[4] Adobe Inc., "Classifying and Ranking Changes Between Document Versions," US Patent 10,713,432 B2, application no. US15/476,640. *[grant date unverified — confirm via Google Patents/USPTO before citing]*

[5] N. Guha, J. Nyarko, D. E. Ho, C. Ré, A. Chilton, et al., "LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models," in *Advances in Neural Information Processing Systems 36 (NeurIPS 2023), Datasets and Benchmarks Track*, 2023.

[6] I. Chalkidis, A. Jana, D. Hartung, M. Bommarito, I. Androutsopoulos, D. M. Katz, and N. Aletras, "LexGLUE: A Benchmark Dataset for Legal Language Understanding in English," in *Proc. 60th Annual Meeting of the Association for Computational Linguistics (ACL 2022)*, 2022.

[7] D. Hendrycks, C. Burns, A. Chen, and S. Ball, "CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review," in *Advances in Neural Information Processing Systems 34 (NeurIPS 2021), Datasets and Benchmarks Track*, 2021, arXiv:2103.06268.

[8] H. de Martim, "An Ontology-Driven Graph RAG for Legal Norms: A Structural, Temporal, and Deterministic Approach," in *Legal Knowledge and Information Systems (JURIX 2025)*, Frontiers in AI and Applications, IOS Press, 2025.

[9] H. de Martim, "Modeling the Diachronic Evolution of Legal Norms: An LRMoo-Based, Component-Level, Event-Centric Approach to Legal Knowledge Graphs," arXiv:2506.07853, Jun. 2025 (rev. Jun. 2026).

[10] P. A. Bonatti, L. Ioffredo, I. M. Petrova, L. Sauro, and I. R. Siahaan, "Real-Time Reasoning in OWL2 for GDPR Compliance," *Artificial Intelligence*, vol. 289, 2020, doi: 10.1016/j.artint.2020.103389.

[11] H. Hermansson and J. P. Cross, "Tracking Amendments to Legislation and Other Political Texts with a Novel Minimum-Edit-Distance Algorithm: DocuToads," arXiv:1608.06459, Aug. 2016.

[12] W. Fan, Y. Zhou, M. Zhang, Y. Weng, Y. Hu, T. Zheng, B. Xu, C. Li, J. Yang, H. Li, and Y. Song, "Can LLMs Time Travel? Enhancing Temporal Consistency in Legal Agentic Search through Reinforcement Learning," arXiv:2605.25920, May 2026.

[13] A. Blair-Stanek, N. Holzenberger, and B. Van Durme, "BLT: Can Large Language Models Handle Basic Legal Text?" arXiv:2311.09693, Nov. 2023 (rev. Oct. 2024).

[14] COLIEE Organizing Committee, "Competition on Legal Information Extraction/Entailment (COLIEE), Task 4: Statute Law Entailment," ongoing competition series, JURIX/ICAIL-affiliated workshops.

[15] C. Xiao, X. Hu, Z. Liu, C. Tu, and M. Sun, "Lawformer: A Pre-trained Language Model for Chinese Legal Long Documents," *AI Open*, vol. 2, pp. 79–84, 2021.

[16] G. Koomullil, "Proof-Carrying Certificates for LLM Pipelines: A Trust-Boundary Architecture," arXiv:2605.16407, May 2026.

[17] G. Castiglione, S. Ebrahimi, and N. Khakpour, "VeriSBOM: Secure and Verifiable SBOM Sharing Via Zero-Knowledge Proofs," arXiv:2602.13682, Feb. 2026.

[18] European Union, "Regulation (EU) 2024/1689 (Artificial Intelligence Act), Article 44: Certificates," 2024.

---

*Limitations of this review: consolidates sources verified in two prior adversarial-review passes rather than a fresh search session; three items ([3], [4]) carry unverified author/date details flagged inline and require direct confirmation before use in a submission bibliography. As with the prior reviews, this is a single, non-exhaustive search effort, not a PRISMA-registered systematic review. Given LegalSearch-R1 [12] and the de Martim line [8, 9] are both active, very recent (2025–26) research directions, a literature-monitoring check immediately before submission is recommended.*
