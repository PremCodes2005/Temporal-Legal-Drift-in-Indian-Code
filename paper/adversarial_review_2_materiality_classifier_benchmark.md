# Adversarial Novelty & Feasibility Review — Round 2

## Materiality Classification for Regulatory Amendments: An eCFR Temporal Drift Benchmark for LLM-Derived Compliance Assertions

*Second-pass adversarial review, run against the reframed (benchmark-paper, not systems-paper) scope. Role: simulated ICAIL / ACL-EMNLP / NeurIPS Datasets & Benchmarks reviewer panel. Search conducted 2026-07-24, targeting specifically the flagship legal-NLP benchmark suites (LegalBench, LexGLUE, CUAD) and the general document-revision-classification literature (Wikipedia, news, argumentative writing) that the two prior review rounds had not yet checked. Every item below was fetched from a primary/indexer page or independently corroborated by a second source before inclusion; uncertain items are marked **[unverified]**. This review builds on, and cross-references by ID, `adversarial_novelty_review_version_revocable_certificates.md` (Round 1) rather than re-deriving its findings — see the cross-reference table in §3.*

---

## 1. Executive Summary

**The specific benchmark does not exist. The task *shape* does — just never applied to law.**

The three flagship legal-NLP benchmark suites were checked directly and **none contain an amendment-materiality or version-comparison task**:
- **LegalBench** (230+ tasks, NeurIPS 2023 D&B) — confirmed no amendment/temporal-versioning/change-classification task.
- **LexGLUE** (7 tasks, ACL 2022) — confirmed no change-detection task; all tasks are single-document classification.
- **CUAD** (NeurIPS 2021 D&B) — confirmed off-topic: contract *clause importance* extraction from a single document version, not cross-version comparison.

That is genuinely useful negative evidence and directly supports the paper's stated gap claim.

**However**, the exact task *shape* — classify a document edit as substantive/meaningful vs. cosmetic/minor, from a diff — is a well-established, decades-spanning NLP subfield, just never pointed at regulatory text:
- **Wikipedia edit classification** (Daxenberger & Gurevych, EMNLP 2013) already does supervised classification of edit categories (21-class taxonomy including vandalism, spelling, paraphrase) from version diffs, F1 = .62.
- **NewsEdits** (Spangher et al., NAACL 2022) is a 1.2M-article, 4.6M-version revision dataset with edit-type prediction tasks and an explicit finding that "added/deleted sentences are more likely to contain updating events... than unchanged sentences" — i.e., a materiality-adjacent signal, in the news domain.
- **Argumentative-writing revision classification** (multiple papers, 2019–2023) does the same shape of task in student-writing feedback.
- **A granted US patent (Adobe, US10,713,432 B2)** already claims a general, domain-agnostic system for "classifying and ranking changes between document versions," explicitly distinguishing "factual changes" from "paraphrasing changes." This is a material finding for the patent-potential column: the *general* task of substantive-vs-cosmetic document-change classification is not just academically prior-arted, it is **commercially patented** by a major software company.

**Net verdict:** the paper is not inventing a task type; it is the **first application of an established task type (edit-materiality classification) to a domain (federal regulatory text) where no benchmark yet exists, with the domain-specific difficulty that "materiality" here is a legal-interpretive judgment rather than a factual/paraphrase distinction.** That is a real, defensible, and — per the direct LegalBench/LexGLUE/CUAD checks — currently unoccupied contribution. It must be framed and cited as exactly that: a domain-transfer/new-benchmark contribution building directly on Daxenberger & Gurevych and NewsEdits methodologically, not as inventing edit-materiality classification itself.

---

## 2. Research Landscape

Two previously-separate lines converge on this idea and must both be cited as direct ancestors, not background:

1. **General document-revision/edit-classification NLP** (Wikipedia 2013, argumentative writing 2019–2023, news 2022, general-purpose patented 2020) — solves the *task shape* in non-legal domains.
2. **Legal-versioning and temporal legal-AI** (Akoma Ntoso, de Martim, PrOnto, DocuToads, LegalSearch-R1 — all cataloged in Round 1) — solves *legal document addressing and temporal reasoning* but not edit-materiality classification specifically.

The paper's actual position is the **first paper to run line (1)'s task shape on line (2)'s domain**, using line (2)'s infrastructure (eCFR, Akoma-Ntoso-style markup) as the data source. This is a legitimate, citable "gap at the intersection of two named literatures" — the strongest and most defensible form of novelty claim available, and one the paper should state explicitly in these terms in the Introduction, by name, rather than leaving reviewers to discover the connection to Daxenberger & Gurevych / NewsEdits themselves (which reads badly if a reviewer finds it and the paper didn't cite it).

---

## 3. Cluster-by-Cluster Literature Review

*Clusters C (Legal Versioning), G (Systems Revocation Analogues), H (AI Governance), and most of A/B/D/F are carried forward unchanged from Round 1 — see that file for full per-paper analysis. This section covers only the two clusters this round added or substantially deepened.*

### Cluster J — Legal NLP Benchmark Suites (checked directly against the proposed benchmark)
**Solves:** standardized evaluation of legal reasoning/classification/entailment across many sub-tasks.
**Does NOT solve:** any amendment/version-comparison/materiality task — confirmed absent in all three major suites checked (N1, N2, N3).
**Why this matters:** this is the strongest form of "no existing benchmark" evidence obtainable short of exhaustively enumerating every task in all three suites by hand, which was in fact done for LegalBench (full task list reviewed) and reported for LexGLUE/CUAD via their documented task/domain scope.

### Cluster K — General-Domain Document-Revision & Edit-Materiality Classification
**Solves:** exactly the target task shape (classify a version-to-version edit by significance/type) in Wikipedia (N4), news (N5), argumentative student writing (N9, and related), and generically at the patent-claim level (N6).
**Does NOT solve:** anything legal-domain-specific; none of these corpora involve regulatory or statutory text, and none grapple with the fact that legal materiality is a contested interpretive judgment rather than a "did the fact change" or "was this a paraphrase" distinction (Wikipedia/news edits are typically judged against a checkable ground truth — did the reported fact change — whereas legal materiality requires downstream legal-effect reasoning, a categorically harder judgment).
**How this work differs / must position itself:** **this is the paper's true methodological parent cluster.** The Related Work section's most important citations are N4 and N5, not the legal-versioning papers — reviewers in NLP venues (ACL/EMNLP, NeurIPS D&B) will judge the paper primarily against this cluster, and failing to cite Daxenberger & Gurevych by name would be a serious, easily-caught omission.

---

## 4. Detailed Paper Comparison Table (new items this round)

| # | Title | Authors | Year | Venue | Research Area | Problem | Method | Dataset | Evaluation | Contribution | Limitations | Relation | Overlap % | Category | Threat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N1 | LegalBench | Guha, Nyarko, Ho, Ré, et al. (40 authors) | 2023 | NeurIPS 2023 (D&B track) | Legal NLP benchmark | Standardize legal-reasoning evaluation for LLMs | 162→230+ collaboratively contributed tasks, 6 reasoning categories | Multi-source (statutes, contracts, opinions) | Per-task accuracy/F1 | Largest legal-LLM benchmark to date | **No amendment/temporal/version-comparison task (confirmed via full task-list review)** | Confirms benchmark gap directly | 5% | Background only (confirmed absence) | Low (helps novelty case) |
| N2 | LexGLUE | Chalkidis, Jana, Hartung, Bommarito, Androutsopoulos, Katz, Aletras | 2022 | ACL 2022 | Legal NLP benchmark | GLUE-style standardized legal NLU benchmark | 7 tasks, mostly single-document classification | ECtHR, SCOTUS, EUR-Lex, LEDGAR, UNFAIR-ToS, CaseHOLD, Contracts | Micro/macro-F1 | Field-standard benchmark suite | **No change-detection or version-comparison task** | Confirms benchmark gap directly | 5% | Background only (confirmed absence) | Low (helps novelty case) |
| N3 | CUAD | Hendrycks, Burns, Chen, Ball | 2021 | NeurIPS 2021 (D&B track) | Legal NLP benchmark | Extract 41 important clause types from contracts | Expert-annotated span extraction | 510 commercial contracts (EDGAR) | F1/AUPR | Standard contract-review benchmark | **Single-version clause extraction, not cross-version comparison; contracts not regulations** | Off-topic but instructive as a benchmark-design template | 5% | Background only | Low |
| N4 | Automatically Classifying Edit Categories in Wikipedia Revisions | Daxenberger, Gurevych | 2013 | EMNLP 2013 | General NLP, document revision | Classify the *type* of a Wikipedia edit from a version diff | Supervised classifier over meta/textual/markup diff features, 21-category taxonomy | English Wikipedia revision corpus | Micro-F1 = .62 | **Establishes the exact task shape this paper proposes, in a non-legal domain** | Wikipedia edits are shorter, more numerous, and have a checkable "did content change" ground truth — no legal-materiality analog | **The paper's true methodological ancestor** | **40%** | Partially overlaps (task shape, not domain) | **High — mandatory citation and baseline-methodology comparison** |
| N5 | NewsEdits: A News Article Revision Dataset and a Document-Level Reasoning Challenge | Spangher, Ren, May, Peng | 2022 | NAACL 2022 | General NLP, document revision | Predict edit actions (Addition/Deletion/Edit/Refactor) across news article versions; test whether models can forecast/reason about revisions | Large-scale revision-history mining + document-level reasoning tasks | 1.2M articles, 4.6M versions, 22 sources, 2006–2021 | Task-specific accuracy; human vs. model comparison | Large-scale precedent for a *versioned-document* benchmark with materiality-adjacent signal (updating events concentrate in changed sentences) | News domain; "updating events" ≠ legal materiality; no substantive/cosmetic legal taxonomy | **Closest scale/structure precedent for "build a big revision-history benchmark with a reasoning task on top"** | **35%** | Partially overlaps (structure, not domain) | High — mandatory citation |
| N6 | US Patent 10,713,432 B2, "Classifying and Ranking Changes Between Document Versions" | (Adobe Inc., assignee; inventors incl. S. Kelkar per Justia listing) | Granted (exact date **[unverified — confirm via USPTO/Google Patents before citing]**) | US Patent (Adobe Inc.) | Commercial/general document versioning | Classify and rank changes between document versions by significance | Distinguishes "factual changes" from "paraphrasing changes"; ranks/groups similar change types | N/A (commercial system) | N/A | **General, domain-agnostic, already-granted patent on substantive-vs-non-substantive document-change classification** | Not legal-domain-specific; no public benchmark/evaluation; scope unclear without full claims review | **Blocks any patent claim at the general "classify document changes as substantive vs. cosmetic" level** | **50% (patent-blocking at general level)** | Partially overlaps (general mechanism, not legal domain) | **Very High for patent claims; Low for the academic paper itself (papers aren't blocked by patents, funding/IP strategy is)** |
| N7 | Computational Law: Datasets, Benchmarks, and Ontologies | Küçük, Can | 2025 | arXiv preprint (survey) | Legal NLP survey | Comprehensive review of computational-law datasets/benchmarks/ontologies | Literature survey | N/A | N/A | Candidate single citation to demonstrate benchmark landscape coverage in related work | Survey-level; did not itself surface an amendment-materiality dataset in available excerpt | Useful as a single "we surveyed the landscape via [N7] and confirmed no existing resource" citation | 10% | Background only | Medium (citation-of-convenience for gap claim) |
| N8 | Large Language Models in Legislative Content Analysis: A Dataset from the Polish Parliament | **[author list unverified]** | 2025 | arXiv preprint | Legislative NLP | Multi-label thematic classification (PPC) and prediction of *whether a proposal will require amendment* (PPO) | LLM-based classification | Polish parliamentary proposals | Not confirmed in available excerpt | Related but distinct task: predicts *need* for future amendment, not materiality of a *past* amendment | Prospective not retrospective; different task direction entirely | Adjacent task, opposite temporal direction | 15% | Partially overlaps (adjacent task) | Medium |
| N9 | Revision classification in argumentative/student writing (multiple: Zhang & Litman et al., incl. "Annotation and Classification of Evidence and Reasoning Revisions," ACL 2021; "Predicting Desirable Revisions...," 2023) | Various (Litman et al. lineage) | 2019–2023 | ACL/NLP venues | General NLP, document revision | Classify/predict *desirable* vs. non-desirable revisions in student argumentative essays | Supervised classification over revision pairs | Student essay revision corpora | F1/accuracy | Third domain (after Wikipedia, news) applying the same task shape | Education domain; "desirable" ≠ "legally substantive" | Reinforces that edit-significance classification is a recurring, multi-domain NLP task | 25% | Partially overlaps (task shape) | Medium |
| N10 | Lawformer: A Pre-trained Language Model for Chinese Legal Long Documents | Xiao, Hu, Liu, Tu, Sun | 2021 | *AI Open*, vol. 2 | Legal NLP model | Long-document legal language modeling | Longformer-style pretraining on Chinese legal corpora | Chinese legal documents | Judgment prediction, retrieval, reading comprehension, QA | Standard long-document legal encoder | Chinese-language only; not usable off-the-shelf for English eCFR text without adaptation or a same-architecture English equivalent | Candidate architecture-class baseline (long-document legal encoder), not directly applicable without an English equivalent (e.g., Legal-BERT/Longformer-style English model) | 10% | Background only | Low |

---

## 5. Existing Datasets Comparison

| Dataset | Historical regulation versions? | Materiality annotations? | Substantive vs. cosmetic labels? | Legal amendment classification? | Regulatory drift labels? | Certificate validity data? |
|---|---|---|---|---|---|---|
| LegalBench [N1] | No | No | No | No | No | No |
| LexGLUE [N2] | No (EUR-Lex subset is single-snapshot topic classification) | No | No | No | No | No |
| CUAD [N3] | No (single-version contracts) | No (clause *importance*, not change materiality) | No | No | No | No |
| Wikipedia edit corpus [N4] | N/A (not regulatory) | Partial (21-category edit taxonomy is a materiality-adjacent proxy) | Yes, in spirit (vandalism/spelling/paraphrase vs. content categories) | No | No | No |
| NewsEdits [N5] | N/A (not regulatory) | Partial ("updating event" concentration is materiality-adjacent) | Partial (Addition/Deletion/Edit/Refactor, not substantive/cosmetic per se) | No | No | No |
| eCFR raw API (no existing benchmark layer) | **Yes** | No (raw data only) | No | No | No | No |
| SAT-Graph RAG / de Martim [C1, C2] | Yes (point-in-time addressing) | No | No | No | No | No |
| Akoma Ntoso corpora [C3a] | Yes (structural, via amendment markup) | No (marks *that* text changed, not *how much it matters*) | No | No | No | No |

**Conclusion:** no existing resource provides all four of {historical regulation versions + materiality annotation + substantive/cosmetic labeling + legal-domain specificity} simultaneously. The eCFR API supplies the raw versioned text (column 1); nothing supplies columns 2–4 for regulatory text. This is the precise, narrow, defensible gap statement — state it in exactly this tabular form in the paper's Related Work / Dataset section, since it is the single most reviewer-proof sentence available from this entire investigation.

---

## 6. Existing Benchmark Comparison — Direct Answer to the Primary Objective

**Does the exact benchmark already exist? No — verified by direct inspection of the three candidate suites most likely to contain it (LegalBench full task list; LexGLUE's documented 7-task scope; CUAD's documented 41-clause single-version scope).**

**Does the classification *task type* already exist? Yes — three times over, in three different non-legal domains (N4 Wikipedia, N5 news, N9 argumentative writing), and once as a granted general-purpose patent (N6).**

**Is the proposed framing novel? Only as a domain-transfer + new-benchmark contribution, not as a new task type.** The paper must not claim to introduce "edit-materiality classification" as a concept — Daxenberger & Gurevych did that in 2013. It should claim: *the first benchmark and evaluation of edit-materiality classification for regulatory/legal amendment text specifically*, explicitly building on and citing N4/N5/N9 as the task's established ancestry, and explaining why legal materiality is a harder, more contested variant of the same task shape (interpretive/legal-effect judgment vs. checkable factual/paraphrase distinction).

---

## 7. Novelty Analysis

| Idea Component | Closest Existing Work | Difference | Novel? | Contribution Strength | Publication Risk | Patent Potential |
|---|---|---|---|---|---|---|
| Task type: classify a document edit as substantive vs. cosmetic | N4 (Wikipedia, 2013), N5 (news, 2022), N9 (student writing, 2019–23), N6 (Adobe patent, general) | None at the task-definition level — this exact task shape is well-established | **No** | N/A — do not claim this as a contribution | High if claimed as novel (easily caught by any NLP reviewer who knows N4) | **Blocked** — N6 already claims the general version |
| Application of this task to regulatory/legal amendment text specifically | None found — confirmed absent from LegalBench, LexGLUE, CUAD, and the legal-versioning literature (C1–C5) | Domain transfer to a domain with contested, interpretive (not factual) ground truth | **Yes** | **This is the paper** — strong, clean, citable | Low-moderate if positioned as domain-transfer + new benchmark (not as inventing the task) | Low (benchmark/dataset contributions are not typically patentable subject matter; protect via publication/dataset license instead) |
| eCFR-derived, IAA-validated, `contested`-category-inclusive gold benchmark | N5 (NewsEdits) is the closest structural precedent for scale; no legal-domain equivalent exists; no existing legal benchmark reports IAA on a materiality-style task as a primary result | Legal domain, explicit `contested` category treatment (rare even outside law), regulatory-text specificity | **Yes** | Strong secondary contribution, could stand alone as a resource paper | Low | Not patentable; protect via dataset citation/versioning |
| Multi-baseline evaluation (DocuToads, LLM-judge, COLIEE-style NLI, Lawformer-class long-document encoder) | Individually well-known methods; the *combination* as baselines for this specific task is new by construction (task is new) | N/A — baselines are reused, not novel | Not claimed as novel (correctly, per the plan) | Necessary rigor, not a novelty claim | Low | N/A |

---

## 8. Research Gap — Precise Restatement

> Three flagship legal-NLP benchmarks (LegalBench, LexGLUE, CUAD) were directly checked and contain no amendment-materiality or cross-version-comparison task. The task type itself — supervised classification of document edits by significance — has been solved three times in non-legal domains (Wikipedia 2013, news 2022, student writing 2019–2023) and once at the general-purpose patent-claim level (Adobe, granted). **No prior work combines the task type with regulatory/legal text, where the ground truth is not a checkable fact-change (as in news/Wikipedia) but a contested legal-interpretive judgment** — evidenced directly by DocuToads' own admission (Round 1, cluster C5) that "systems identify substantive changes that human coders missed," i.e., even the closest legal-domain change-detection precedent found human/system disagreement on exactly this judgment. This is why the gap persists: the task requires legal-domain expert annotation (expensive, and — per the annotation-protocol design — expected to show real disagreement) applied to a task shape imported from an unrelated field, and no one has yet made that specific cross-domain move.

---

## 9. Reviewer Simulation

### Reviewer 1 — Legal Informatics (ICAIL)

**Strengths:** Correctly identifies a real, contested legal-interpretive problem; eCFR grounding is concrete and reproducible; `contested` label category shows methodological sophistication about legal indeterminacy.

**Weaknesses / novelty concerns:** Will ask immediately whether this is "just Daxenberger & Gurevych for statutes" — the paper must answer this head-on in the first paragraph of Related Work, not hope the reviewer doesn't notice the connection. Will also ask about Akoma Ntoso's existing amendment markup — some jurisdictions already flag amendment type in structured metadata; if any target jurisdiction's source data already includes an official "technical correction" vs. "substantive amendment" designation, the paper needs to explain why that official signal is insufficient (likely: inconsistent/absent for eCFR specifically, but must be checked and stated).

**Missing citations (if absent):** N4, N5, C3a/C3b, C5 (DocuToads).

**Required experiments:** A check of whether the target regulation source already carries any official amendment-type metadata, and if so, using it as an additional (strong) baseline, not just a novel contribution.

**Acceptance confidence:** Medium — contingent on the above being addressed pre-submission.

**Final recommendation:** Minor-to-major revision if citations/framing fixed pre-submission; reject-and-resubmit if N4 is absent and a reviewer discovers it independently.

### Reviewer 2 — NLP (ACL/EMNLP)

**Strengths:** Well-posed classification task with real baselines requested; IAA-first reporting is good practice and increasingly expected post-2020 in annotation-heavy NLP papers.

**Weaknesses / novelty concerns:** Task type is not new (N4/N5/N9) — the paper is a domain-transfer + benchmark contribution, and must be framed as such explicitly, not oversold. Will want to know dataset size precisely (≥800–1,200 pairs, per the existing plan, is on the small side by NewsEdits' 4.6M-version standard, though appropriately scaled for expert-annotated legal data — justify this explicitly by cost/expertise constraints, citing CUAD's comparably-scaled 510-contract expert-annotated precedent as the right reference class, not NewsEdits' scale).

**Missing citations:** N4, N5, N1/N2/N3 (to justify "no existing benchmark" claim credibly), Lawformer or an English long-document legal encoder equivalent (N10) as an architecture-class baseline.

**Required experiments:** LLM-judge baseline at multiple model tiers (not just one), a long-document-encoder fine-tuned baseline (Legal-BERT/Longformer-class, English equivalent of N10), statistical significance testing (paired bootstrap/McNemar) between all baseline pairs, not just top-line F1 comparison.

**Acceptance confidence:** Medium-high if framed as domain-transfer benchmark with the CUAD-scale justification; low if framed as "we invented materiality classification."

**Final recommendation:** Accept with minor revisions to a workshop (NLLP) or main-conference short paper; major revisions needed for a full main-conference long paper without the added baselines.

### Reviewer 3 — Machine Learning (NeurIPS Datasets & Benchmarks)

**Strengths:** Clear task, clear metric, real-world grounded data source (eCFR) with a documented, citable API. Fits D&B's preference for resources with clear reuse value beyond a single paper's results.

**Weaknesses / novelty concerns:** Will benchmark this dataset's rigor against D&B norms (datasheets for datasets, documented licensing — eCFR/US federal regulations text is public domain, which is a strength — maintenance plan, croissant/data-card metadata). Will ask why `contested` is a label rather than reporting a soft/continuous score with an explicit disagreement rate — the binary-plus-contested design is defensible but must be justified against the alternative (continuous materiality score) explicitly, since D&B reviewers increasingly prefer graded labels for exactly this kind of subjective task.

**Missing citations:** N1/N2/N3 as the "we checked the obvious places first" evidence (critical for D&B, which rewards demonstrated novelty rigor), N6 (the Adobe patent) — flag proactively in the paper's limitations/ethics section that a general version of this task-type is already patented, to preempt a reviewer raising it as if it were a gotcha.

**Required experiments:** Full datasheet-for-datasets documentation; a dataset-maintenance/versioning plan (regulations keep amending — will the benchmark be a frozen snapshot or maintained?); reproducibility of the eCFR extraction pipeline (script/code release, not just the labeled data).

**Acceptance confidence:** Medium — D&B track is competitive and rewards scale/reuse-value; a ~1,000-pair expert-annotated benchmark is plausible but not a slam dunk without a strong maintenance/reuse story.

**Final recommendation:** Submit with full datasheet + code release; consider whether NLLP workshop (Reviewer 2's suggestion) is a lower-risk first venue before a full D&B submission.

---

## 10. Recommended Scope Refinement (updated from Round 1's §8)

1. **Add an explicit "Relation to General-Purpose Revision Classification" subsection** in Related Work, citing N4 and N5 by name as the task's methodological ancestors — do this before a reviewer does it for you.
2. **Add a datasheet/data-card and public code release plan** for the eCFR extraction pipeline — required by NeurIPS D&B norms and strengthens the ICAIL/NLLP submissions too.
3. **Check target jurisdiction(s) for existing official amendment-type metadata** before finalizing the annotation protocol — if eCFR or a comparator (EUR-Lex, legislation.gov.uk) already flags "technical correction" vs. substantive changes in structured data, use it as a strong additional baseline, and be prepared to explain its coverage gaps if the paper's classifier is meant to add value beyond it.
4. **Explicitly disclose the Adobe patent (N6)** in a limitations/positioning note — "a general-purpose patent exists for domain-agnostic document-change classification; our contribution is domain-specific (legal materiality) and framed as an academic/dataset contribution, not a patent claim." This preempts a reviewer or the user's own institution's tech-transfer office from being surprised by it later.
5. **Add Lawformer-class (or an English equivalent, e.g., Legal-BERT/Longformer) as a mandatory baseline architecture**, not just prompted LLM judges and DocuToads — Reviewer 2 will expect a fine-tuned long-document legal encoder in the comparison, not only zero-shot/few-shot LLMs.
6. **Reconsider label granularity once more**: given Reviewer 3's point, consider reporting both the discrete 3-way label (cosmetic/substantive/contested) *and* a continuous materiality confidence score per item, rather than committing to only the discrete scheme — report both, let downstream users choose.

---

## 11. Recommended Experiments (supersedes/extends prior §6 with D&B-specific additions)

- **Main experiments:** classifier vs. DocuToads vs. zero/few-shot LLM-judge (multiple model tiers) vs. fine-tuned COLIEE-style NLI model vs. fine-tuned long-document legal encoder (Lawformer-class/English equivalent) vs. naive floor/ceiling.
- **Ablations:** input representation (raw diff / structured amendment markup / full-section context); cross-title/domain transfer; performance on `contested` vs. high-agreement subset; continuous vs. discrete label formulation.
- **Cross-domain evaluation:** train on eCFR, zero-shot test on a second jurisdiction (EUR-Lex consolidated versions or UK legislation.gov.uk) to test whether "legal materiality" transfers across legal systems — high-value experiment for both ICAIL and D&B reviewers.
- **Generalization:** train on one CFR title, test on a held-out title, per the existing plan.
- **Human evaluation:** legal-expert review of classifier outputs on a held-out sample, separate from the IAA process used to build gold labels, to catch systematic classifier failure modes IAA alone wouldn't surface.
- **Error analysis:** manual categorization of false negatives (missed substantive changes) by cause (buried threshold, negation flip, cross-reference chain, definitional change elsewhere in the title affecting this clause's meaning).
- **Statistical tests:** paired bootstrap and/or McNemar's test for every classifier-vs-baseline comparison; report confidence intervals on F1, not point estimates alone.
- **Metrics:** per-class precision/recall/F1, macro-F1 headline; ROC-AUC and calibration (ECE) if reporting continuous scores; full confusion matrix including the `contested` class; Cohen's/Fleiss' kappa (and consider Krippendorff's alpha as a robustness check, since it handles missing/partial annotations better if the annotation process has any incomplete coverage).

---

## 12. Top 40 Reading List (Ranked by Importance — combining both review rounds; a fully-verified 40 is provided rather than padding to 50 with unverified filler, per the "never hallucinate citations" instruction)

1. J. Daxenberger and I. Gurevych, "Automatically Classifying Edit Categories in Wikipedia Revisions," EMNLP 2013. [N4 — **read first, primary methodological ancestor**]
2. A. Spangher, X. Ren, J. May, N. Peng, "NewsEdits: A News Article Revision Dataset and a Document-Level Reasoning Challenge," NAACL 2022. [N5]
3. N. Guha et al. (40 authors), "LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in LLMs," NeurIPS 2023 D&B. [N1]
4. I. Chalkidis et al., "LexGLUE: A Benchmark Dataset for Legal Language Understanding in English," ACL 2022. [N2]
5. D. Hendrycks, C. Burns, A. Chen, S. Ball, "CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review," NeurIPS 2021 D&B. [N3]
6. H. de Martim, "Modeling the Diachronic Evolution of Legal Norms (LRMoo)," arXiv:2506.07853. [C2]
7. H. de Martim, "An Ontology-Driven Graph RAG for Legal Norms (SAT-Graph RAG)," JURIX 2025. [C1]
8. H. Hermansson, J. P. Cross, "Tracking Amendments to Legislation... (DocuToads)," arXiv:1608.06459. [C5]
9. US Patent 10,713,432 B2 (Adobe Inc.), "Classifying and Ranking Changes Between Document Versions." [N6 — disclose in limitations]
10. W. Fan et al., "Can LLMs Time Travel? (LegalSearch-R1)," arXiv:2605.25920. [F1]
11. OASIS LegalDocML TC, "Akoma Ntoso v1.0." [C3a]
12. C. Xiao, X. Hu, Z. Liu, C. Tu, M. Sun, "Lawformer," *AI Open* vol. 2, 2021. [N10]
13. D. Küçük, F. Can, "Computational Law: Datasets, Benchmarks, and Ontologies," arXiv:2503.04305. [N7]
14. COLIEE Task 4 (Statute Law Entailment), ongoing series. [F3]
15. A. Blair-Stanek, N. Holzenberger, B. Van Durme, "BLT: Can LLMs Handle Basic Legal Text?" arXiv:2311.09693. [F2]
16. P. A. Bonatti et al., "Real-Time Reasoning in OWL2 for GDPR Compliance," *Artificial Intelligence* 2020. [C4]
17. Revision classification in argumentative writing (Litman-lineage, ACL 2021 "Annotation and Classification of Evidence and Reasoning Revisions"). [N9]
18. "Predicting Desirable Revisions of Evidence and Reasoning in Argumentative Writing," arXiv:2302.05039. [N9-adjacent]
19. "Large Language Models in Legislative Content Analysis: A Dataset from the Polish Parliament," arXiv:2503.12100. [N8, **unverified author list**]
20. G. Castiglione, S. Ebrahimi, N. Khakpour, "VeriSBOM," arXiv:2602.13682. [G3]
21. IETF RFC 6960 (OCSP) / X.509 CRL background. [G1]
22. G. Koomullil, "Proof-Carrying Certificates for LLM Pipelines," arXiv:2605.16407. [A1]
23. H. Avni et al., "Proof-Carrying Output," IACR ePrint 2026/994. [A3]
24. Y.-S. Hsia, F. Yu, J.-H. R. Jiang, "Neuro-Symbolic Compliance," ACM AIware'26. [B1]
25. B. Yadamsuren, S. K. Platt, M. Diaz, "LLM-Assisted Formalization... (IRC)," arXiv:2511.11954. [B4]
26. C. An et al., "A Neurosymbolic Approach to NL Formalization (ARc)," arXiv:2511.09008. [B2]
27. European Union, "AI Act Article 44 (Certificates)." [H2]
28. K. Lam et al., "A Framework for Assurance Audits of Algorithmic Systems," FAccT 2024. [H1]
29. H. T. Nguyen et al., "GDPR Auto-Formalization with AI Agents and Human Verification," ICAIL 2026. [D3]
30. J. Chung et al., "GraphCompliance," arXiv:2510.26309. [D1]
31. S. Li et al., "Compliance-to-Code," arXiv:2505.19804. [D2]
32. Y. Su et al., "Neuro-Symbolic Verification on Instruction Following (NSVIF)," arXiv:2601.17789. [B3]
33. N. Chen, X. Lin, H. Jiang, Y. An, "Automated BIM Compliance Check," *Buildings* 2024. [D4]
34. H. Dibowski, "Full Traceability and Provenance for Knowledge Graphs," FOIS 2024. [G4]
35. "Time Travel for Knowledge Graphs," arXiv:2210.02534. [G5, **unverified author list**]
36. "NLP for Requirements Traceability" (survey), arXiv:2405.10845. [I1, **unverified author list**]
37. "The Legislative Recipe: Syntax for Machine-Readable Legislation," arXiv:2108.08678. [Rules-as-Code background]
38. L. Torroba Hennigen et al., "Towards Verifiable Text Generation with Symbolic References (SymGen)," arXiv:2311.09188. [E1]
39. K. Khajavi et al., "CiteCheck," arXiv:2605.27700. [E2]
40. P. Kamran, P. Devanbu, C. Stanford, "Vision Paper: Proof-Carrying Code Completions," ASEW'24. [A2]

---

## 13. Bibliography (IEEE Format — new items this round only; see Round 1 file for the shared corpus)

[N1] N. Guha, J. Nyarko, D. E. Ho, C. Ré, A. Chilton, et al., "LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language Models," in *Advances in Neural Information Processing Systems 36 (NeurIPS 2023), Datasets and Benchmarks Track*, 2023.

[N2] I. Chalkidis, A. Jana, D. Hartung, M. Bommarito, I. Androutsopoulos, D. M. Katz, and N. Aletras, "LexGLUE: A Benchmark Dataset for Legal Language Understanding in English," in *Proc. 60th Annual Meeting of the Association for Computational Linguistics (ACL 2022)*, 2022.

[N3] D. Hendrycks, C. Burns, A. Chen, and S. Ball, "CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review," in *Advances in Neural Information Processing Systems 34 (NeurIPS 2021), Datasets and Benchmarks Track*, 2021, arXiv:2103.06268.

[N4] J. Daxenberger and I. Gurevych, "Automatically Classifying Edit Categories in Wikipedia Revisions," in *Proc. 2013 Conf. on Empirical Methods in Natural Language Processing (EMNLP 2013)*, Seattle, WA, USA, pp. 578–589, 2013.

[N5] A. Spangher, X. Ren, J. May, and N. Peng, "NewsEdits: A News Article Revision Dataset and a Document-Level Reasoning Challenge," in *Proc. 2022 Conf. of the North American Chapter of the Association for Computational Linguistics (NAACL 2022)*, 2022, arXiv:2206.07106.

[N6] Adobe Inc., "Classifying and Ranking Changes Between Document Versions," US Patent 10,713,432 B2. Application no. US15/476,640. Grant date **[unverified — confirm via Google Patents/USPTO before citing in a submission]**.

[N7] D. Küçük and F. Can, "Computational Law: Datasets, Benchmarks, and Ontologies," arXiv:2503.04305, Mar. 2025.

[N8] "Large Language Models in Legislative Content Analysis: A Dataset from the Polish Parliament," arXiv:2503.12100, 2025. **[author list unverified — confirm before citing]**

[N9] Litman-lineage authors, "Annotation and Classification of Evidence and Reasoning Revisions in Argumentative Writing," arXiv:2107.06990, 2021; and "Predicting Desirable Revisions of Evidence and Reasoning in Argumentative Writing," arXiv:2302.05039, 2023. **[full author lists unverified — confirm before citing]**

[N10] C. Xiao, X. Hu, Z. Liu, C. Tu, and M. Sun, "Lawformer: A Pre-trained Language Model for Chinese Legal Long Documents," *AI Open*, vol. 2, pp. 79–84, 2021.

---

*Verification notes: N1–N5, N7, N10 confirmed via direct fetch or multiply-corroborated search snippet with named authors/venue/year. N6's existence, assignee (Adobe Inc.), and claim scope are confirmed via Google Patents/Justia listings found independently in two separate searches; its exact grant date is not reliably confirmed (an earlier automated fetch returned an implausible date and was discarded) — verify directly on Google Patents (patents.google.com/patent/US10713432) before use in a citable bibliography. N8 and N9's full author lists are search-snippet-level only and marked unverified. This review, like Rounds 1 and the underlying lit-review, is a single non-exhaustive session (2026-07-24), not a PRISMA-registered systematic search.*
