# Commencement-notification policy (`commencement-policy-v1`)

Implementation: `src/temporal_legal_drift/monitoring/commencement.py`. Tests: `tests/unit/test_commencement.py`.

## Discovery (conservative)

An e-Gazette listing row is downloaded as `COMMENCEMENT_NOTIFICATION_CANDIDATE` only when its subject has both:
- a precise commencement phrase ("appoint(s/ment of) the date/day", "come(s)/coming into force", "commencement of"); and
- a named enactment ("Act", "Code", "Sanhita", "Adhiniyam").

On the 18 real subjects listed on 2026-10-12, it selected exactly the MSMED commencement notification.

## Three separate facts

| Fact | Source | Status |
| --- | --- | --- |
| `publication` | Gazette listing date | `unreviewed`; recorded uncertainty "publication is not commencement" |
| `commencement` / `partial_commencement` | Each "the <date> as the date on which <provisions> shall come into force" clause in the **English, quarantine-cleaned** text | `unreviewed`. Records the verbatim provisions span, Act, Act number, enabling provision, notification number and page/clause locator. |
| `applicability` | — | Never produced here: always `NOT_DETERMINED` |

- **Storage:** `TemporalFact` records in `data/monitoring/commencement/<official_id>.<sha12>.json` (write-once), with `legal_effect_claimed: false` and `review_required_before: [legal_effect, applicability, graph_update]`.
- **Resolver:** the applicability resolver uses only `approved` facts. A test shows that unreviewed commencement facts produce `unresolved_escalate` / `no_approved_temporal_evidence`.

## Conservative extraction

- **"Whole Act" versus partial:** "the said Act" counts as a whole-Act commencement. Anything narrower is `partial_commencement`.
- **Unparsed wording:** commencement wording that does not match exactly is `UNRESOLVED` and keeps its verbatim text. No date is guessed.
- **Hindi:** Hindi-only text yields nothing, because it is quarantined first.
- **Conflicts:** when another notification gives a different date for the same Act number and provisions, `conflicts` records it. It is never resolved by recency.

## Not implemented

- **Recording a review decision:** no mechanism records a qualified reviewer's approval of commencement facts. `commencement_pending_review` in `/api/sources/health` counts them.
- **Other notice types:** amendments to commencement notifications, and notifications that commence provisions "for a State" or under conditions, are only `UNRESOLVED` or text-level.
