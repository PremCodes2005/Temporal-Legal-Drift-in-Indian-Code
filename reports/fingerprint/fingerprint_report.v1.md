# Legal Change Fingerprint: cross-corpus results (2026-10-13)

Method: `docs/methodology/legal_change_fingerprint.v1.md` (ADR 0015). Engineering results only; legal validation is **UNVERIFIED**.

## Held-out run: every strongly corroborated graph-v4 transition (86), one templated question each

| Component | Result |
| --- | --- |
| Wording drift | 83 determined; 3 abstain (the amended words cannot be located exactly once in the clause) |
| Rule drift | 53 determined; 30 provisional lower bounds (operative wording changed but no supported field captured it); 3 abstain |
| Rule fields changed | {'modality': 23, 'deadline': 8, 'exception': 12, 'actor': 25, 'action': 22, 'scope': 1, 'monetary_threshold': 9, 'penalty': 3} |
| Clean zero (non-operative edits) | 8 |
| Invariant violations (span offsets, rule-score sums, values on abstention) | 0 |

**Manual spot check:** 6 random modality changes reviewed 2026-10-13: 4 correct; 'as may be decided' (Competition s.51) fixed as a delegation, not a permission; a relative clause 'circumstances in which ... may be terminated' (IBC s.240) remains a known limitation.

## Acceptance tests (`tests/unit/test_fingerprint.py`, 21 tests)

**Real corpus**, across five Acts and both insertions and substitutions:
- SRA s.11 (discretion becomes duty);
- CPC s.32 (500 → 5,000);
- DM s.31 (annually → every two years);
- Arbitration s.8 and s.23 (an added proviso, an inserted sub-section);
- MV s.181 (penalty);
- Banking Regulation s.45ZC (an unclassified change, so a lower bound).

**Synthetic (marked as such):**
- identical text;
- a spelling-only change;
- a 10 → 15-day deadline with filing on day 5 (unchanged) and day 12 (changed); the controlled set is 3/6 = 50%;
- a large non-operative rewording;
- incomplete before text;
- OCR corruption;
- an unreliable source.

**Also covered:**
- a model timeout and invalid model proposals;
- a wrong provision and a wrong Act;
- a wrong date (applicability: the before-amendment wording);
- missing facts;
- conflicting signals (wording 5.4% against rule 25/100);
- reproducibility of every value from the response;
- citations pointing to the scored text;
- mode invariance.

## Limitations

- **Rule fields are heuristic extractors:**
  - counts (for example a number of nominees) and who-may-sign changes are not a field, which gives the 30 lower bounds;
  - the actor and action fields are approximate;
  - relative clauses such as "in which … may be terminated" can read as permissions.
- **Before clause:** it is today's text with this amendment reverted. Later amendments remain on both sides, and this is labelled.
- **Outcome drift:** it evaluates only deadline, threshold, added or removed exception, penalty, modality and the registry rules. Other fields report "not evaluated".
