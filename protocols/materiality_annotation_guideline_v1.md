# Materiality annotation guideline v1.0.0-draft

**Status:** operational draft for annotation preparation; not legally frozen or independently approved.

## What to label

Assign one amendment-level label to the legal significance of the evidenced wording change. Do not label the outcome of one user's scenario. Record every supported dimension separately. Temporal applicability and compliance consequence are separate decisions. The current task unit is the amendment-controlled fragment—not necessarily the complete historical provision. If context or evidence is insufficient, do not guess: flag the case for adjudication or exclusion and give the reason.

Use only the repository's canonical labels: **High, Medium, Low, None**.

| Label | Definition and inclusion | Exclusions / examples |
| --- | --- | --- |
| **High** | Changes a substantive right, duty, prohibition, legal scope/eligibility, liability, penalty, controlling exception, or major compliance requirement. Use when the amendment materially changes who is governed, what is required/forbidden, or the legal exposure. | Do not assign solely because wording is long or a particular scenario's answer changes. Punctuation-only or renumbering with unchanged legal effect is not High. |
| **Medium** | Changes an operative procedure, filing/reporting method, deadline, threshold, evidentiary requirement, or implementation condition while preserving the basic allocation of rights and duties. A changed number of days is ordinarily at least Medium; rate High only when evidence shows a fundamental substantive effect. | A purely clarifying phrase with no demonstrated operative effect is not Medium. Do not collapse the scenario consequence into this label. |
| **Low** | Makes a narrow legally relevant clarification, terminology update, cross-reference repair, or limited administrative refinement with minor expected compliance impact. | If the change demonstrably changes scope, duty, liability, a threshold, or a deadline with practical effect, use Medium or High. |
| **None** | Changes presentation only—such as spelling, punctuation, layout, or non-operative editorial wording—with evidence that legal meaning and compliance operation are preserved. | Any supported legal, procedural, scope, threshold, deadline, or liability effect rules out None. |

## Dimensions

Record all applicable dimensions from the current draft registry: obligation, right, prohibition, scope, definition, threshold, time, liability, procedure, exemption. This ten-dimension list remains a technical draft pending the Phase 0 research decision; do not invent or silently add categories.

## Evidence and difficult cases

Each annotator works independently and records label, dimensions, concise rationale, confidence (0–1), guideline version, and exact source-anchored evidence quote(s). Cite the amendment instruction and, where available, an independently downloaded consolidated-text corroboration. For an insertion, the before fragment is empty by operation; cite the insertion instruction rather than inventing pre-existing words. For omission/repeal, cite both the deleted wording and operative deletion cue. An amendment fragment is not a full section; request context or mark unresolved when the fragment alone cannot support a defensible rating.

When several dimensions change, choose the level supported by the most consequential evidenced legal effect, and list all supported dimensions. A legal consequence in one scenario does not automatically raise amendment materiality. A change from 10 days to 15 days is ordinarily Medium because it changes an operative deadline; it may be High only with evidence of a fundamental effect on rights, duties, or liability.

## Independent annotation and adjudication

Two annotators must submit separately before seeing each other's labels. Preserve immutable individual submissions. Compute exact agreement and Cohen's kappa over complete pairs only; report the denominator, class distributions, and the full confusion matrix. If expected agreement is 1 or there are no complete pairs, report kappa as undefined with its reason, not as zero. An independent adjudicator records a canonical label, dimensions, evidence quote, rationale, identity, and guideline version for every pair, including agreements. Never auto-adjudicate from majority vote or an LLM.

Only a complete set of 50 cases with two valid independent annotations per case and explicit evidence-backed adjudication may be written as materiality_gold_v1. A taxonomy revision increments its version and requires reannotation of affected items. Until independent annotation and adjudication exist, all outputs remain an open review round; no agreement, gold label, model metric, or validated-classifier claim may be reported.
