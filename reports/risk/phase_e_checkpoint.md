# Phase E checkpoint — scenarios, consequences and conditional risk

Date: 2026-10-12. Engineering results only; **legal/research gate UNVERIFIED**.

## State verified

- `data/risk/compliance_scenarios.v1.json` keeps its 13 structured abstention scaffolds and 2 conditional Section 19 demonstrations, unchanged.
- No new substantive scenario was authored. None of the 13 scaffolds has a supportable full set of:
  - scenario facts and reference date;
  - an applicable version;
  - an obligation with an expected outcome;
  - source evidence.

  Writing those from machine outputs would manufacture legal gold.
- The deterministic engine (`risk/engine.py`) was reviewed:
  - It selects exactly one dated rule.
  - It requires obligation and temporal evidence whose quote and hash verify.
  - It returns `null` risk (never "None") when an obligation model, applicability, a fact or evidence is missing.
  - It has no drift input.

## Changes

New tests in `tests/unit/test_risk.py`:
- **No obligation model:** a provision without one returns `INSUFFICIENT_EVIDENCE` with null level and flag, escalates, and records the reason.
- **Out of scope:** an out-of-scope organization type returns `NOT_APPLICABLE` with a scope trace.
- **Full trace:** a supported output names the version, rule, obligation, evidence roles (no source text, hashes present), trace, urgency and uncertainty, with `escalation_required` and `legal_validation: UNVERIFIED`.
- **Section 19 demonstrations:** both remain `ASSUMED_FOR_DEMONSTRATION`. `graph-consumer-v1` on graph v4 returns `UNRESOLVED` for IT Act s.19 on 2009-10-26 and 2009-10-27. They therefore rest on stipulated applicability, not graph-supported law, and must stay labelled conditional.

Coverage that already existed:
- deadline false positives/negatives;
- inclusive boundary;
- pending vs breached;
- future facts;
- unknown, conflicting and unavailable versions (reference date not covered);
- wrong jurisdiction;
- materiality independence;
- drift rejection;
- tampered or mismatched evidence;
- missing temporal evidence;
- polarity;
- reproducibility;
- schema parity;
- registry fingerprint refusal.

## Not done

- The risk engine does not consume graph v4: rule applicability stays registry-stipulated. Feeding graph status into risk would need a new risk schema version and an expert-reviewed applicability decision.
- No legal-risk accuracy is reported; there are no independently adjudicated outcomes.

## Gates

- Engineering: risk unit and integration suites pass (26 tests).
- Legal/research: **UNVERIFIED**.
