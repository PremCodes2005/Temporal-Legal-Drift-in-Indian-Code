# ADR 0014: Evidence-first answers with four independent determinations (rag-answer-v2)

Status: **accepted 2026-10-13**. Implementation: `rag/question.py`, `rag/versions.py`, `rag/determinations.py`, `rag/compose.py`, `rag/rag_pipeline.py`, `frontend/src/Determinations.jsx`. Contract: `schemas/rag/rag_answer.v2.schema.json`, `docs/api_contracts.md`. Audit: `reports/rag_audit/`.

## Context

The baseline audit (24 cases, 12 Acts) found 12 support errors, 2 pairing errors and 5 wrong-Act citations. Its root causes:
- **RC1:** pairing used a single curated relation.
- **RC2:** the Act named in the question was not resolved.
- **RC3:** no provision was selected.
- **RC4:** no scenario input and no determinations.
- **RC5:** generation was decoupled from the selected evidence.

## Decision

1. **Identity before similarity.** A question frame resolves the Act, section, amending Act or year, date and question type against the corpus names and the amending → principal relations in graph v4. Unknown Acts are out of scope, and a wrong amending Act is rejected, never paired.
2. **Version evidence, in order of support:**
   - a strongly corroborated graph-v4 transition, carrying the verbatim instruction (page, line, hash), the derived fragments and the corroborating consolidated text;
   - else the consolidated Act's own substitution footnote for that section. The footnote is tied to its numbered marker, "ibid." is resolved, and the amending Act number must appear in the amending Act's own text;
   - else an explicit reason: weak transition only, several candidates, the named amendment has no change here, or nothing recorded.
3. **Four independent determinations**, each in a state from DETERMINED, PROVISIONAL, CONDITIONAL, NEEDS_FACTS, INSUFFICIENT_EVIDENCE or OUT_OF_SCOPE, always with a plain reason:
   - **textual drift:** drift-metrics-v3, only on a supported pair; insertions are out of scope;
   - **materiality:** the versioned silver set, only on an exact match of source hash, provision, operation and wording; shown as provisional machine triage, never gold; never computed on the fly;
   - **answer change:** the slot the question asks about (amount, period, frequency, delegation, modal force) compared across the supported versions. "What changed" questions get NEEDS_FACTS. Dates against an Act-wide commencement make the result CONDITIONAL. Rule-based comparison of both versions applies when a registry rule exists;
   - **risk:** the existing RiskService and registry only, with no drift or materiality input. Stipulated applicability makes it CONDITIONAL, and unknown risk is never shown as none.
4. **Grounded composition:** comparisons are written deterministically from the selected evidence (no model). General questions may use the model, which cites every excerpt it was given, with a labelled extractive fallback.
5. **Compatibility:** `rag-answer-v2` (`schema_version` 2.0.0) keeps every v1 field. Version questions carry `comparison-record-v2`; general questions keep `comparison-record-v1`.

## Consequences

- **Coverage:** supported comparisons now exist for the 86 corroborated transitions (18 Acts) and for footnote-documented substitutions. Everything else abstains with a specific, actionable reason.
- **Risk** is available only where the registry has rules (currently the IT Act s.19 demonstrations).
- **Not covered:** paraphrased Act names beyond the alias list, multi-section questions (only the first section is used), and commencement-specific applicability.
