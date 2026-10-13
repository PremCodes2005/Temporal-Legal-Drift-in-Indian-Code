# RAG assistant audit: baseline before integration (2026-10-13)

Case set: `configs/rag_audit/cases.v1.json` (24 cases, 15 strata). Expectations come from graph v4, the silver materiality set and the risk registry, never from the assistant's answers. Run: offline and extractive (`rag.audit.offline_extractive`), so it is reproducible. Raw results: `reports/rag_audit/baseline.v1.json`. These are engineering counts, not legal accuracy.

**Summary:** 12/24 support errors, 2 pairing errors, 5 cases citing a different Act, and all four determinations absent in every case.

## Root causes (traced in code)

| Code | Root cause | Evidence |
| --- | --- | --- |
| RC1 | Pair selection uses `configs/versioning/instrument_relations.v1.json`, which has a single relation (IT 2008 → IT 2000). The 86 strongly corroborated graph-v4 transitions (18 Acts) are consulted only after retrieval has already chosen a pair. | 11 of 12 supported-transition queries returned `NOT_A_COMPARISON`. |
| RC2 | Retrieval does not resolve the Act named in the question, and the lone relation fires whenever IT chunks appear anywhere in the top 40. | The Companies s.46 and wrong-Act queries were paired with IT Act documents; the Factories query was answered from an IBC amendment. |
| RC3 | No provision-level selection: the top chunk wins regardless of the named section. | The MV s.173 query cited the CGST Act; the Companies s.105 query cited the Trade Marks Act. |
| RC4 | No scenario input and no determinations: materiality, answer change and risk were never computed in the query flow. The case orchestrator (`orchestration/pipeline.py`) already joins graph → materiality → risk but is not used. | All 24 cases had `determinations` absent; scenario cases behaved identically to plain ones. |
| RC5 | Generation reads the retrieved chunks, not the evidence the comparison selected. | LLM sample (qwen3:4b, 24 s): the 'Before' panel showed the IT Amendment Act's garbled OCR schedule, while the comparison used the footnote reconstruction; the differences included unsupported details. |

## Per case

| Case | Stratum | Expected support | Actual | Pair / citations | Root cause |
| --- | --- | --- | --- | --- | --- |
| arb-s7-specific | supported_transition_insert_dated_silver | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| arb-s7-generic | mode_invariance | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| arb-s23-counterclaim | insert_answer_change_conditional | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| mv-s173-deposit | numeric_substitution_silver_undated | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | citation_outside_expected_act:central-goods-services-tax-act-2017 | RC1, RC2, RC3 |
| cpc-s32-fine | numeric_substitution_no_silver | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| mv-s181-penalty | numeric_substitution_no_silver | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| sra-s11-discretion | modal_substitution_no_silver | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| patents-s60-period | period_substitution_no_silver | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| brega-s45zc-nominees | numeric_substitution_silver | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| companies-s46-compare | comparison_silver | GRAPH_TRANSITION_FRAGMENTS | UNALIGNED_EXCERPTS | pair_entry_outside_expected:it-act-2000-consolidated; pair_entry_outside_expected:it-amendment-act-2008; citation_outside_expected_act:it-amendment-act-2008; citation_outside_expected_act:it-act-2000-consolidated | RC1, RC2 (IT relation fired) |
| rti-s13-term | substitution_no_silver | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |
| it-s19-specific | footnote_reconstruction | CONSOLIDATED_FOOTNOTE_RECONSTRUCTION | CONSOLIDATED_FOOTNOTE_RECONSTRUCTION | ok | RC4, RC5 |
| it-s19-generic | footnote_reconstruction_generic | CONSOLIDATED_FOOTNOTE_RECONSTRUCTION | CONSOLIDATED_FOOTNOTE_RECONSTRUCTION | ok | RC4, RC5 |
| it-s19-risk-match | scenario_risk_rule_match | CONSOLIDATED_FOOTNOTE_RECONSTRUCTION | CONSOLIDATED_FOOTNOTE_RECONSTRUCTION | ok | RC4 (scenario ignored) |
| it-s19-risk-mismatch | scenario_risk_rule_mismatch | CONSOLIDATED_FOOTNOTE_RECONSTRUCTION | CONSOLIDATED_FOOTNOTE_RECONSTRUCTION | ok | RC4 (scenario ignored) |
| it-2008-privacy-ocr | poor_ocr_unaligned | UNALIGNED_OR_ABSTAIN | UNALIGNED_EXCERPTS | ok | correct abstention (unaligned); RC4 |
| wrong-act-companies-competition | wrong_act_rejection | UNALIGNED_OR_ABSTAIN | UNALIGNED_EXCERPTS | pair_entry_outside_expected:it-act-2000-consolidated; pair_entry_outside_expected:it-amendment-act-2008; citation_outside_expected_act:it-amendment-act-2008; citation_outside_expected_act:it-act-2000-consolidated | RC2 (IT relation fired) |
| companies-s105-weak | unsupported_transition_internal_checks_only | UNALIGNED_OR_ABSTAIN | NOT_A_COMPARISON | citation_outside_expected_act:trade-marks-act-1999 | RC2, RC3 (Trade Marks Act cited) |
| wildlife-s11-omission | omission_unsupported | UNALIGNED_OR_ABSTAIN | NOT_A_COMPARISON | ok | acceptable (no version claim); RC4 |
| factories-not-in-graph | act_without_amendment_source | UNALIGNED_OR_ABSTAIN | NOT_A_COMPARISON | citation_outside_expected_act:insolvency-and-bankruptcy-code-amendment-act-2020 | RC2 (answered from IBC amendment) |
| cpa-mediation-general | general_qa | NOT_A_COMPARISON | NOT_A_COMPARISON | ok | correct support; RC4 |
| thoa-punishment-general | general_qa | NOT_A_COMPARISON | NOT_A_COMPARISON | ok | correct support; RC4 |
| jan-vishwas-general | general_qa_amending_act | NOT_A_COMPARISON | NOT_A_COMPARISON | ok | correct support; RC4 |
| dm-s31-frequency | frequency_substitution_no_silver | GRAPH_TRANSITION_FRAGMENTS | NOT_A_COMPARISON | ok | RC1 |

## Missing inputs

- **Scenario facts** (reference date, organisation type, activity and rule-specific facts) cannot be supplied at all. They are needed for answer change and for risk.
- **Effective dates:** only the 2015 Arbitration transitions carry one (Act-wide basis). All other transitions are undated, so date-specific applicability is unresolved.
- **Materiality** silver rows exist for about 30 of the 86 strong transitions, and none exists for IT s.19.
