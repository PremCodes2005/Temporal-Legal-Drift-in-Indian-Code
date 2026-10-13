# ADR 0016: Stored analyses, explicit limits and minimum facts (rag-answer-v4)

Status: **accepted 2026-10-13**. Method changes: `docs/methodology/legal_change_fingerprint.v1.1.md`. Report: `reports/analysis_workspace/report.v1.md`.

## Context

The v0.13.0 audit of the assistant at `127.0.0.1:8765` found these problems:

- **Navigation lost the result.** "Drift explanation" and "Score calculation" were separate navigation pages. They re-read browser state, so after navigation or a refresh they showed "Evidence unavailable / NO PAGE ANCHOR" instead of the answer's own clauses.
- **One page held everything.** It showed seven cards, and six of them said "needs facts" or "not enough evidence". Missing legal evidence and missing user facts looked the same.
- **There was no way to supply facts.** The only form asked for every registry fact (11 for IT s.19).
- **IT s.19 rule drift was spurious.** It scored 5/100 from an "actor" change. The heuristic took the words of the qualifier "Certificate issued by such Certifying Authority" as the provision's actor, so the field and its alignment were unsupported.
- **Materiality was not assessed without a silver row.** It was "not assessed" whenever no frozen silver row matched, even when the aligned evidence was adequate.

## Decision

- **Stable analysis ID.**
  - `analysis_id = "an_" + sha256(identity)[:24]`.
  - The identity covers:
    - the contract version;
    - the method versions (determinations, fingerprint, composition, metrics);
    - the query, the mode and the applied scenario;
    - the recorded generation method;
    - the index identity and graph hash;
    - the active release manifest hash.
- **Write-once storage.**
  - The response is stored at `data/runtime/analyses/<id>.json` (gitignored runtime output) and served by `GET /api/analyses/<id>`. An invalid ID returns 400; an unknown one returns 404.
  - Every view and every shared link `#analysis/<id>/<view>` reads that record. The browser never recomputes a value.
- **Explicit limits.** Every determination and fingerprint component carries `limit {kind, reason, action}`, where `kind` is one of:
  - `evidence`: the legal text is missing or unreliable; the action is verify_source;
  - `facts`: the user's situation is unknown; the action is add_facts;
  - `method`: the change is outside what the method can score; the action is queue_review;
  - `not_applicable`.

  Facts are never requested to fill an evidence gap.
- **Minimum facts.**
  - `scenario_request` lists only the facts needed by components whose limit is `facts`, deduplicated, with what each one unlocks.
  - Core facts are those needed for applicability or outcome. Facts needed only for risk sit in a collapsed optional group.
  - Registry comparisons ask only for the facts on which the two versions' rules differ (`_decisive_comparison`), and state that the shared conditions are assumed to be met.
  - Facts written in the question ("after 18 months", "Rs 3,000", a date) are applied and attributed to the question. Facts from the form override them.
- **Machine triage of materiality.**
  - With no frozen silver match, materiality is triaged on the fly from the aligned evidence, using rule-cue-transition-v1 and operation-delta-v1. When the two rules disagree, both labels are shown.
  - The state is PROVISIONAL with `source: ON_THE_FLY_MACHINE_TRIAGE`.
  - A frozen silver match is labelled `FROZEN_SILVER_SET`.
  - Neither is gold, and unreliable text blocks triage.
- **Rule drift v1.1.**
  - An actor must be a recognised legal-actor head noun in the subject's head noun phrase, before any qualifier ("issued by", "under", "of", …).
  - An action is extracted only for an accepted actor.
  - An unclassified change is "Not scored" (INSUFFICIENT_EVIDENCE, method limit), never 0/100.
  - When rule drift is unscored, outcome drift cannot read "Unchanged".
- **Five views of one analysis:** Answer, Compare & Evidence, Scores & Method, Scenario & Impact, and Sources & Review.
  - They form an ARIA tablist with arrow, Home and End keys.
  - The active view is in the URL; a pasted link or back/forward re-opens it from the stored record.
- **Version history.** The v2 and v3 schemas, `rule_drift.v1.json` and audit cases v1/v2 are kept. Contract `rag-answer-v4`, `determinations-v3`, `legal-change-fingerprint-v1.1` and `rule-drift-v1.1` are new versions.

## Rejected

- **Recomputing scores in the browser for the explanation pages:** two code paths could disagree, and the explanation could then differ from the answer.
- **Asking every registry fact:** it buries the one or two facts that decide the answer.
- **Labelling machine triage "Determined" to fill the UI:** this is silver-like evidence, not reviewed legal materiality.
- **Re-asking the backend on every tab change:** the result could change between views if the index or release changed.
