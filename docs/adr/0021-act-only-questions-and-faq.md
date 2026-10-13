# ADR 0021: Act-only questions, amendment matching, recent questions and the FAQ

Status: **accepted 2026-10-13**. Report: `reports/analysis_workspace/report.v4.md`.

## Context

- **Act-only questions:** a question naming only an Act ("What changed in the Motor Vehicles Act?") stopped at `SECTION_NOT_IDENTIFIED`.
- **FAQ:** 11 of 12 FAQ questions returned no evidence.
- **Wrong amendment:** a footnote substitution was scored for a question naming a different amendment. "Section 99 … after the 2025 amendment" scored Act 6 of 2026.
- **FAQ prefill bug:** clicking an FAQ card showed the previous answer's question, because `AssistantWorkspace`'s result effect ran after the starter effect on mount.

## Decision

- **version-evidence-v2:**
  - **Footnote matching:** a footnote is used only when its amending Act is the amendment the question names. It matches when the years are equal, or when the amending Act's own text carries the footnote's Act number (the IT (Amendment) Act, 2008 is Act 10 of 2009). Otherwise the answer says which Act made the change (`FOOTNOTE_FROM_OTHER_AMENDMENT`) and nothing is scored.
  - **`VersionSelector.discover`:** an Act-only question lists the Act's sections with a recorded change (graph transitions or reconstructable footnotes), plus sections whose text matches the question's topic.
  - **Same gates:** each listed section runs the same `select()` and the fingerprint's text gate as a typed section, so its status is honest. The statuses are: supported, several changes, not corroborated, text unreliable, other amendment, or no recorded change.
  - **Ranking:** topic match first (heading words count double), then evidence strength, then newest amendment. Eight are shown, with counts.
- **answer-composition-v3:** the Act-level answer says how many sections can be compared and gives examples. It never scores the whole Act and never implies a complete amendment history.
- **Section choice:** `POST /api/rag/query` accepts `section` (validated). The question is kept as asked, `selection` records the Act and section, and both are part of the analysis ID.
- **Frontend:**
  - **Section chooser:** a "Compare" or "See why" button per section, with its status, the reason it is listed, the amendment, and a source PDF link.
  - **FAQ:** clicking an FAQ card asks its question once ("Ask this question"), and the previous answer is cleared. `#assistant?q=` links also ask once and are replaced in history, so Back never re-asks.
  - **Recent questions:** the last five successful questions are kept in this browser's `localStorage` (question, mode and Act only; no facts), with "Clear history".
  - **Suggested follow-ups:** built from the last answer's Act and sections, and labelled as suggestions.
  - **Try asking:** verified starters.
- **FAQ content:** `frontend/src/faq.json` holds 10 questions about Acts in the corpus (6 Act-only, 4 section-specific), without "recent" claims. Every question and starter is run against the backend by `tests/unit/test_act_discovery.py`.

## Not changed

Evidence gates, OCR handling, provenance, temporal applicability and the scoring methods. No recommendation model was added.
