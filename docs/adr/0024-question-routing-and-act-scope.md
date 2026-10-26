# ADR 0024: Question routing before retrieval, the Act-scope citation gate and latest records

Status: **accepted 2026-10-26**. Contract: `rag-answer-v6` (`schemas/rag/rag_answer.v6.schema.json`). Evaluation: `configs/routing_eval/questions.v1.json`, `reports/routing_eval/routing_eval.v1.json`.

## Failures reproduced (commit 96b0638, offline, extractive)

| Question | Before |
|---|---|
| what is the sir act? | Answered from the Repealing and Amending Act 2001 |
| What are the latest changes in India Code? | "India Code" treated as an Act not in the corpus |
| What has appeared recently in the e-Gazette? | Answered from the Code of Civil Procedure |
| What changed recently in Indian law? | Answered from the Copyright Act |
| Compare the Aadhaar Act and the IT Act on data protection. | Logged as an ambiguity; answered from the IT Act only |
| What did the Jan Vishwas Act change in the Motor Vehicles Act? | Logged as an ambiguity; Motor Vehicles Act cover page |
| What is the punishment for theft? | Answered from the IT Act |
| What is the capital of France? | Answered from the Companies Act |
| What changed in the Aadhaar Act by the Information Technology (Amendment) Act 2008? | Amending Act not recognised; no relation error |
| What does the Money Laundering Act say? | "Not in the local corpus" (the PMLA is indexed) |
| What does the Motor Vehicles Act generally cover? | Answered from section 115 |

## Root causes

1. **Any unresolved question fell through to an unrestricted search.** When no single principal Act was resolved, `answer()` passed `restrict=None`, so the top-scoring chunk from any Act (and a live India Code search) became the answer. A wrong or missing Act therefore always produced a confident answer from another Act.
2. **Act names were detected only in Title Case** (`ACT_PHRASE` needed capital letters), so "sir act" was not seen as a name at all.
3. **Several named Acts and one ambiguous name were the same state.** Two different Acts in one question were recorded as an "ambiguity" and the principal was left empty (cause 1 then applied).
4. **An amending Act was recognised only by its own catalogue base name** ("IT Act 2008"), not by the principal's other names ("Information Technology (Amendment) Act 2008").
5. **Source names and "latest" questions had no route.** "India Code" matched the Act-name pattern; recent-change questions had no path to the monitoring ledger.
6. **No check after generation** that cited documents belong to the Act the question named.
7. **General questions about an Act used topic search on words such as "generally" and "cover".**

## Decision

- **question-route-v1** (`rag/routing.py`) decides, before any retrieval, one of nine routes. Each route has a response type, a reason code and the entry ids it may use:
  - `act_identified`, `amendment_mismatch`, `act_comparison`, `act_ambiguous`, `several_acts`, `act_not_found`, `latest_records`, `general_no_act`, `outside_domain`.
- **Order of the decision:**
  1. A name shared by several corpus Acts asks the user to choose. A stated year decides it; nothing else does.
  2. An Act-like name (any letter case) that no corpus name or alias covers is reported as not found.
  3. Two or more named Acts are compared only when the question asks for a comparison; otherwise the user chooses one.
  4. One identified Act, or an amending Act, is answered.
  5. With no Act named: latest/recent plus a source or law word goes to monitoring; another legal question gets Act choices; anything else gets scope guidance.
- **question-frame-v2:**
  - Act names are found in any letter case, read back from "Act/Code/Sanhita/Adhiniyam" to a question word.
  - Several named Acts are kept (`other_acts`), and a shared name gives `act_choices`.
  - An amending Act matches through the names of the Acts it is recorded as amending.
  - New aliases: `pmla` and `money laundering act`.
- **Retrieval is restricted on every answering route** to the identified Act. No route reaches the unrestricted search or the live section search for its answer.
- **Citation gate** (`_enforce_act_scope`): after generation, every cited or listed document must be in the route's `allowed_entry_ids`, which are the Act, its recorded amending instruments and a named amending Act whose relation is recorded. A violation withdraws the answer, giving an evidence-limited response with reason `CITATION_OUTSIDE_ALLOWED_ACTS`. It fails closed; it does not repair the answer.
- **Diagnostic trace** (`routing`):
  - interpreted Acts and their ids, the route, the reason code and the permitted ids;
  - `rejected_candidates`: the Acts an unrestricted search would have used. These are reported, never used.
- **Not found:**
  - The answer says what was checked (the name, short forms, close spelling) and that this does not mean no such Act exists.
  - It links to India Code and e-Gazette searches.
  - Close matches are offered only when the same words appear in a longer corpus title or the spelling similarity is at least 0.85.
  - With live lookup on, India Code titles containing the name are listed as found and not ingested. They are never summarised.
- **Latest records** read `notifications()` from the monitoring ledger and never fetch, so the 24-hour rule is untouched.
  - Records are filtered to the source the question names.
  - Each record is classified as: Act amendment (verified, from the review state only); commencement notification (title test from ADR 0013); unverified machine candidate; or other notice.
  - Each source's last successful check and any STALE / FAILED state are stated.
- **Overview of a known Act:** the Act's long title ("An Act to …") and the chapter headings of its arrangement of sections, each cited, with no score. An Act-only change question keeps the section chooser (ADR 0021).
- **The user can correct the Act:**
  - `POST /api/rag/query` accepts `act` (a corpus entry id); the reason code then becomes `USER_SELECTED_ACT`.
  - The UI shows "Interpreted as" with "Not this Act?", Act-choice buttons and a latest-records list.

## Evaluation (routing-eval-v1)

Twenty-seven questions with expected routes and expected Act ids, taken from the catalog and not from answers. The metrics are reported separately:

- Act-resolution accuracy;
- cross-Act contamination (count);
- citation validity;
- helpful abstention;
- answer coverage.

They are engineering measures of routing and source identity, not legal accuracy. The set was written with the fix and tunes it; it is a regression set, not a held-out benchmark.

## Limits

- Act names that do not end in Act/Code/Sanhita/Adhiniyam (e.g. "Rules", "Regulations", "Ordinance") are not detected as names.
- Close-match thresholds and the legal-word list are hand-set.
- The overview depends on the PDF text layer; spacing errors in headings are shown as extracted.
- The unrestricted live India Code section search no longer contributes to answers. Live lookup now only reports titles for Acts not in the corpus.

## Rejected

- **Asking the model to pick the Act or to "be careful":** the Act is decided before the model sees any text.
- **Answering a general question from the best-matching Act:** the user chooses the Act.
- **Scoring drift between two different Acts:** they are not versions.
