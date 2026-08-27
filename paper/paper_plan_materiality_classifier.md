# Paper Plan (Reframed)

## Materiality Classification of Regulatory Amendments: A Benchmark for Detecting Legally Consequential Change

*Reframed per the adversarial review (`adversarial_novelty_review_version_revocable_certificates.md`, §8–9) and further hardened per the round-2 review (`adversarial_review_2_materiality_classifier_benchmark.md`, §10–11). Systems apparatus (certificates, revocation protocol) demoted to motivating example in the Introduction only. Core contribution: a classifier + benchmark for the one cell both reviews found genuinely unoccupied — deciding whether a regulatory-text edit changed compliance-relevant meaning — explicitly positioned as a **domain-transfer contribution**, not a new task type (see §1a).*

---

## 1. One-Sentence Contribution Claim

> "We introduce the first benchmark and evaluation of **materiality classification for regulatory amendments** — distinguishing legally consequential changes from cosmetic ones — grounded in real eCFR amendment history, with inter-annotator agreement reported as a primary result rather than assumed, and show that syntactic edit-distance, general-purpose revision classifiers, and off-the-shelf legal-entailment baselines all systematically fail on the cases that matter most: small edits with large legal effect."

This is deliberately narrower than the "first ___ that ___ while ___" template — per the review's own caution against overclaiming, the sentence names exactly the two things the corpus doesn't have (a materiality-labeled benchmark; an IAA-honest evaluation) and doesn't claim the certificate/revocation apparatus at all.

### 1a. What is and isn't being claimed (round-2 correction)

The round-2 review found the *task shape* — classify a document edit as substantive vs. cosmetic from a diff — already solved three times in other domains: Wikipedia (Daxenberger & Gurevych, EMNLP 2013), news (NewsEdits, Spangher et al., NAACL 2022), and student argumentative writing (Litman-lineage, 2019–2023) — plus claimed generically in a granted Adobe patent (US10,713,432 B2, "Classifying and Ranking Changes Between Document Versions," distinguishing "factual" from "paraphrasing" changes). **Do not claim to invent edit-materiality classification.** Claim instead: *the first application of this established task type to regulatory/legal text, where the ground truth is a contested legal-interpretive judgment rather than a checkable fact-change* — and cite Daxenberger & Gurevych and NewsEdits as direct methodological ancestors in the opening paragraph of Related Work, not as background found later. This is now the paper's load-bearing novelty sentence; get it right or a reviewer will supply it less charitably.

The positive complement to this correction: three flagship legal-NLP benchmarks were checked directly and confirmed to lack this task — LegalBench (full 230+ task list reviewed), LexGLUE (7 tasks, documented scope), CUAD (documented 41-clause scope). State this explicitly ("we checked the obvious places first") rather than asserting absence from a vacuum.

---

## 2. Task Formalization

**Input:** a pair (clause_v1, clause_v2) — the text of a single regulatory provision before and after an amendment event — plus optional context (parent section, cross-references, effective-date metadata).

**Output:** NOT a binary label, and NOT discrete-only. Per Reviewer 2 (round 1) and Reviewer 3/NeurIPS D&B (round 2) — both independently objected to a hard discrete label losing information a downstream risk-based decision would want — report **both** a 3-way discrete label **and** a continuous materiality confidence score per item, and let downstream users/experiments choose which to consume:
- `cosmetic` — renumbering, formatting, punctuation, typo fixes, reference updates, non-substantive restructuring
- `substantive` — new obligations, changed thresholds, removed requirements, modified exceptions, altered penalties
- `contested` — a fourth, explicit category (see §4) for cases where trained legal annotators themselves disagree after discussion — **do not force-adjudicate these away**; report classifier performance separately on `contested` vs. high-agreement cases. This directly operationalizes the review's instruction to report materiality-is-contested honestly instead of presenting labels as clean ground truth.

**Downstream framing (Introduction only, not a contribution claim):** motivate with one paragraph noting that such a classifier is the missing trigger condition for any certificate-lifecycle system (cite VeriSBOM/OCSP as prior art for the *architecture* that would consume this classifier's output — explicitly not claimed here).

---

## 3. Dataset Construction — eCFR Temporal-Drift Benchmark

1. **Source:** eCFR REST API (`ecfr.gov/developers/documentation/api/v1`) — point-in-time and timeline/diff endpoints, full history back to 2017 (raw XML to 2002).
2. **Title selection:** pick 2–3 CFR titles with (a) high amendment frequency and (b) domain diversity, to pre-empt Reviewer 1's "US-only, single-domain" objection — e.g., a financial title, an environmental title, and a tax/IRS title (natural pairing with prior work B4 on IRC §121). Report amendment-frequency stats per title as a dataset-description table.
3. **Extraction:** pull clause-level version pairs at each amendment event via the timeline API; keep the raw diff plus surrounding section context.
4. **Target size:** aim for ≥800–1,200 labeled clause-pairs total across titles — large enough to avoid Reviewer 2's "resource paper, not a D&B paper" objection, small enough for expert (not crowd) annotation to be feasible.
5. **Held-out split:** stratify by title/domain so at least one full title is held out entirely for an out-of-domain generalization test (mirrors the ablation Reviewer 1 will expect).
6. **Secondary jurisdiction (optional, strengthens generalization claim):** EUR-Lex CELEX consolidated-version data or legislation.gov.uk's versioned API as a second-language/second-system out-of-domain test, flagged as future work if time-constrained.

---

## 4. Annotation Protocol (the make-or-break section)

Given both the Legal and ML reviewers flagged ground-truth reliability as the paper's central risk:

- **Annotators:** ≥2 independent annotators with legal training (law students or practicing lawyers), plus a third adjudicator for disagreements — do not use single-annotator or crowd-sourced labels for the gold set.
- **Guideline design:** write explicit materiality criteria *before* annotation (new obligation / changed threshold / removed requirement / modified exception / altered penalty = substantive; renumbering / formatting / punctuation / typo / reference-only update = cosmetic), pilot on ~50 pairs, revise guidelines, then annotate the full set.
- **Metric — report first, prominently:** Cohen's kappa (2 annotators) or Fleiss' kappa (3+) on the pilot and full set, **before** any model results. If kappa is low (plausible, given DocuToads' own note that "systems identify substantive changes that human coders missed" and general legal-materiality contestation), that is itself a reportable finding, not a flaw to hide — it directly substantiates the paper's framing that this is a genuinely hard, contested judgment, which is the argument for why a naive baseline (edit distance) cannot solve it.
- **`contested` label rule:** any pair where the two initial annotators disagree AND the adjudicator does not find the disagreement resolvable by the written guideline (i.e., a genuine boundary case) is labeled `contested` rather than force-resolved to a majority vote. Report the size of this category as a headline dataset statistic.
- **Ethics/limitations note:** state plainly that "materiality" is a legal-interpretive judgment, not an objective fact, and that the benchmark's gold labels reflect the annotation team's specific guideline, not a claim of legal authority — required for ICAIL/JURIX submission norms and pre-empts Reviewer 1's likely framing objection.

---

## 5. Baselines (all six are non-negotiable per the two-round reviewer simulation)

| Baseline | Source | Role |
|---|---|---|
| Minimum-edit-distance amendment typing | DocuToads (Hermansson & Cross, 2016) — reimplement Levenshtein-based insert/delete/substitute/transposition typing as a feature set or standalone classifier | The classical syntactic floor; expected to fail specifically on small-edit-distance/high-materiality cases (e.g., "30 days"→"15 days") — this contrast is the paper's central empirical hook |
| **General-purpose revision classifier (new, round 2)** | Reimplementation/fine-tune of Daxenberger & Gurevych (EMNLP 2013) edit-category features, and/or a NewsEdits-style edit-action classifier (Addition/Deletion/Edit/Refactor), retrained on the eCFR training split | **The single most important baseline added post-review** — this is the paper's actual nearest neighbor; if this baseline does well, the paper's contribution shrinks to "retraining an existing method on a new domain," so this comparison must be run and reported honestly regardless of outcome |
| Zero-shot / few-shot LLM judge | Prompted GPT/Claude-class model, materiality taxonomy from §4 in the prompt, tested at ≥2 model tiers per Reviewer 2 (round 2) | The field's current default approach; test whether it does better than edit distance and whether it's calibrated (not just accurate) |
| Fine-tuned legal NLI / entailment model | COLIEE-style architecture (legal-BERT or similar, fine-tuned on statute entailment) adapted to predict "does v2 entail/contradict the compliance-relevant content of v1" | Tests whether general legal-entailment training transfers to materiality judgment, or whether the task needs amendment-specific supervision |
| **Fine-tuned long-document legal encoder (new, round 2)** | Lawformer (Xiao et al., *AI Open* 2021) is Chinese-only — use an English equivalent (Legal-BERT/Longformer-class model) fine-tuned on the benchmark | Explicitly requested by Reviewer 2 (round 2); represents the "specialized legal encoder" architecture class distinct from both prompted LLMs and generic edit-classifiers |
| Naive floor/ceiling pair | "always cosmetic" / "always substantive" | Trivial baselines to contextualize F1 numbers |

- **Also test temporal leakage** explicitly: for LLM-judge and fine-tuned baselines, check whether performance differs on amendments dated before vs. after the underlying model's pretraining cutoff — mirrors F1's (LegalSearch-R1) finding on "temporal bias tied to training cutoffs," and preempts an obvious reviewer question.
- **Check for existing official amendment-type metadata before finalizing baselines** (round 2, Reviewer 1 concern): confirm whether eCFR or a comparator source (EUR-Lex, legislation.gov.uk) already flags "technical correction" vs. substantive amendments in structured metadata. If such a signal exists, it becomes a mandatory strong baseline, not just prior art to cite.

---

## 6. Evaluation

- **Primary metrics:** per-class precision/recall/F1 (cosmetic / substantive / contested-as-its-own-class); macro-F1 as headline number.
- **Reliability metric (reported first, per §4):** inter-annotator kappa on gold labels.
- **Statistical testing:** paired bootstrap or McNemar's test between the proposed classifier and each baseline on the same held-out pairs.
- **Highest-stakes error class:** false negatives — substantive changes misclassified as cosmetic (a missed compliance-relevant change is the costly direction of error). Report this rate separately and prominently, not buried in a confusion matrix.
- **Ablations:** (a) raw diff text vs. structured/Akoma-Ntoso-style amendment markup as input representation; (b) clause-only vs. full-section context; (c) cross-title/domain transfer (train on financial, test on environmental, etc.); (d) performance on `contested` subset vs. high-agreement subset — expect and report a performance drop on `contested`, and argue this is *expected and correct behavior*, not a failure, since even human experts split on these.
- **Error analysis:** qualitative review of false negatives with example amendments, categorized by why they were missed (e.g., threshold buried in a subordinate clause, negation flip, cross-reference chain).

---

## 7. Related Work Mapping (reframed per both adversarial reviews)

| Section | Papers | Framing |
|---|---|---|
| **General-purpose document-revision classification (new, round 2 — lead with this)** | Daxenberger & Gurevych (Wikipedia, EMNLP 2013), NewsEdits (Spangher et al., NAACL 2022), argumentative-writing revision classification (Litman-lineage, 2019–2023), Adobe patent US10,713,432 B2 | **Cite first, prominently, as this paper's direct methodological ancestry** — the task type is theirs; the domain transfer to contested legal-interpretive text is this paper's contribution. Naming these explicitly pre-empts the single most damaging reviewer discovery |
| Legal NLP benchmark landscape (new, round 2) | LegalBench (Guha et al., NeurIPS 2023), LexGLUE (Chalkidis et al., ACL 2022), CUAD (Hendrycks et al., NeurIPS 2021) | Cited as **the specific places checked and confirmed absent** — state "we reviewed LegalBench's full task list and LexGLUE's/CUAD's documented scope; none contain an amendment-materiality or cross-version-comparison task" rather than a vague absence claim |
| Legal document versioning/addressing | de Martim (SAT-Graph RAG; LRMoo), Akoma Ntoso | Cited as **infrastructure this work assumes/could sit on top of**, explicitly not competed with |
| Certificate/revocation architectures | Koomullil, Avni et al. (PCO), VeriSBOM, X.509/OCSP | Cited **only in the Introduction's motivating paragraph**, as the downstream consumer of this classifier's output — not a related-work section claiming to extend them |
| Legal NLP / temporal reasoning | LegalSearch-R1, BLT, COLIEE Task 4 | **Direct related work** — closest problem-framing and methodology neighbors; explicitly differentiate: LegalSearch-R1 optimizes retrieval-time correctness, this work evaluates a standalone materiality-judgment task on historical pairs |
| Amendment/change detection | DocuToads | **Direct baseline**, not background — this is the paper's central empirical foil |
| Neuro-symbolic compliance verification | Hsia et al., ARc, NSVIF, IRC Prolog work | Background — establishes the broader compliance-verification context without claiming to extend it |
| Long-document legal encoders | Lawformer (Xiao et al., *AI Open* 2021) | Cited as the architecture class an English-equivalent fine-tuned baseline represents (§5) |

---

## 8. Section Outline

1. **Introduction** — motivate with the certificate-staleness scenario (one paragraph, citing Koomullil/VeriSBOM/OCSP as prior art the scenario assumes), then pivot immediately to: "the missing piece is deciding whether an amendment matters — that is this paper's contribution," and state the §1a positioning sentence explicitly (domain transfer of an established task type, not a new task).
2. **Related Work** — per §7 table, **leading with the general-purpose revision-classification cluster** (Daxenberger & Gurevych, NewsEdits), then the confirmed-absent benchmark landscape (LegalBench/LexGLUE/CUAD), then legal-versioning and certificate/revocation background.
3. **Task Definition** — 3-way + `contested` label scheme, reported alongside a continuous materiality score (§2).
4. **The eCFR Temporal-Drift Benchmark** — construction (§3), annotation protocol and IAA (§4) reported as a dataset-quality result, not an appendix footnote; include a **datasheet for datasets** (per NeurIPS D&B norms — motivation, composition, collection process, licensing [eCFR text is US public domain], maintenance plan for a benchmark built on a continuously-amended source).
5. **Baselines and Proposed Approach** — §5, now six baselines including the general-purpose revision classifier and the long-document legal encoder.
6. **Evaluation** — §6, IAA-first, then classifier comparison (including the general-purpose-classifier result, reported honestly even if it performs well), then ablations, then error analysis.
7. **Discussion** — honest treatment of the `contested` category; what this implies for any downstream automated-revocation system (tie back to Introduction's motivating scenario without overclaiming to have built one).
8. **Limitations** — single/limited jurisdiction, annotator-guideline-dependent gold labels, temporal leakage risk, materiality-is-contested-in-law-itself as an epistemic limitation, not just a modeling one, **and an explicit disclosure that a general-purpose patent (Adobe, US10,713,432 B2) already exists for domain-agnostic document-change classification** — state plainly that this work's contribution is domain-specific and framed academically, not as a patent claim.
9. **Conclusion.**
10. **Reproducibility appendix** — eCFR extraction pipeline code release, annotation guideline document, dataset maintenance/versioning plan given the source regulation keeps amending after publication.

---

## 9. Venue Recommendation

Given the reframe, re-rank the four target venues:

- **NLLP (Natural Legal Language Processing) workshop, ACL/EMNLP-affiliated** — best fit: legal-NLP audience, benchmark-paper norms, has published directly adjacent amendment/argumentation work.
- **JURIX or ICAIL** — still strong fits (matches de Martim, COLIEE, GDPR-formalization audience) and legitimizes the legal-materiality framing; expect Reviewer-1-style scrutiny on annotation methodology, which §4 is designed to survive.
- **NeurIPS Datasets & Benchmarks track** — viable if the dataset is scaled and documented to D&B norms (datasheet, licensing, maintenance plan) — the review flagged this as "could stand on this alone."
- *De-prioritize* ASE/AIware/systems venues — no longer a good fit now that the systems apparatus is out of scope.

---

## 10. What Changed From the Prior Scope (for your own tracking)

| Was | Now |
|---|---|
| Certificate schema — headline contribution | Cited as motivating context only, not claimed |
| Revocation protocol — headline contribution | Cited as motivating context only, not claimed |
| Binary substantive/cosmetic label | 3-way + explicit `contested` category |
| IAA as an implementation detail | IAA as a first-class, first-reported result |
| Baselines: implied, unspecified | DocuToads + LLM-judge + COLIEE-style NLI + floor/ceiling, all mandatory |
| Target venue: ASE/AIware/ICAIL (systems-leaning) | NLLP/JURIX/ICAIL/NeurIPS D&B (legal-NLP/benchmark-leaning) |
| **(round 2) Novelty claim: "materiality classification" unqualified** | **Explicitly a domain-transfer contribution — task type is prior art (Daxenberger & Gurevych 2013, NewsEdits 2022), regulatory-text application is not** |
| **(round 2) Baselines: 4, no general-purpose revision classifier** | **6 baselines: adds a retrained general-purpose revision classifier (the paper's real nearest neighbor) and a fine-tuned long-document legal encoder** |
| **(round 2) No benchmark-landscape check** | **LegalBench (full task list), LexGLUE, CUAD directly checked and confirmed absent — cited as evidence, not asserted from a vacuum** |
| **(round 2) No IP disclosure** | **Explicit Limitations-section disclosure of the Adobe general-purpose patent (US10,713,432 B2)** |
| **(round 2) Discrete label only** | **Discrete 3-way label reported alongside a continuous materiality confidence score** |
| **(round 2) No dataset documentation plan** | **Datasheet for datasets + code release + maintenance/versioning plan, required for NeurIPS D&B and good practice regardless of venue** |
