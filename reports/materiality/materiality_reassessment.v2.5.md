# Materiality Re-extraction Review — materiality-disagreement-audit-v2.5

This report re-extracts source clauses with generalised-amendment-extractor-v2.2 and reassesses 50 frozen silver cases. The v1 report and silver dataset remain unchanged. Machine outputs are not legal findings or gold labels.

- Confirmed extraction/alignment defects: **14**
- Review-required compound or unresolved cases: **5**
- Re-extracted aligned cases: **31**
- Cases requiring revalidation against the consolidated principal-Act snapshot: **2**
- v1 disagreements: **19/50**
- v2 comparable cases (both rules emitted labels): **20**
- v2 agreement among comparable cases: **20/20**
- v2 Rule A emitted labels for 42/50; Rule B proposed 22/50, with 2 held for cross-source review and 28 null-label abstentions.
- Predictions changed from v1: Rule A **15/50**; Rule B **31/50**. Labels held for cross-source review are not score-eligible.
- Remaining paired Low-versus-Medium disagreements: **0**; abstentions are not counted as agreement.

Rule B v1 assigned Medium solely from token similarity below 0.65 in all original disagreements. That ratio is not a legal-effect measure; v2 abstains with REVIEW_REQUIRED when low similarity is the only signal. Insertions correctly have an empty before fragment, but this makes a SequenceMatcher ratio of zero structurally uninformative.

## 1. mat_7cb4c31122dad86e30aa4021 — Arbitration And Conciliation Act 1996 / section:25

- Source: `src_0ad4e9c72da39b6e2ffcbafb` page 6, line 18 (SHA-256 `e6a3f49cadc97f08298b708f63c07f9452a420e43de4a7c08c1186da77e186f6`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (125 chars): “and shall have the discretion to treat the right of the respondent to file such statement of defence as having been forfeited”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:25`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (125 chars): “and shall have the discretion to treat the right of the respondent to file such statement of defence as having been forfeited”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 2. mat_e27898c6847505312aa05fec — Arbitration And Conciliation Act 1996 / section:14

- Source: `src_0ad4e9c72da39b6e2ffcbafb` page 5, line 15 (SHA-256 `e6a3f49cadc97f08298b708f63c07f9452a420e43de4a7c08c1186da77e186f6`).
- v1 operation/fragments: `SUBSTITUTE`; before (47 chars): “The mandate of an arbitrator shall terminate if”; after (98 chars): “The mandate of an arbitrator shall terminate and he shall be substituted by another arbitrator, if”.
- v1 rule labels: A **Low**, B **Low** (similarity 0.6667); v1 tie-break **Low** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `UNKNOWN`, target `section:14`; defects: compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 3. mat_1037bf61be63655a13f6f7af — Arbitration And Conciliation Act 1996 / section:7

- Source: `src_0ad4e9c72da39b6e2ffcbafb` page 2, line 22 (SHA-256 `e6a3f49cadc97f08298b708f63c07f9452a420e43de4a7c08c1186da77e186f6`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (48 chars): “including communication through electronic means”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:7`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (48 chars): “including communication through electronic means”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 4. mat_5058fcf9b63e3c8345f6d7c8 — Companies Act 2013 / section:14

- Source: `src_73ff6b08cbbe209ab709e642` page 3, line 2 (SHA-256 `6c7e9d557747412f22e15e8dbd4242d8bf8a0d869771bfeccdf50163e94f670e`).
- v1 operation/fragments: `SUBSTITUTE`; before (508 chars): “Provided further that any alteration having the effect of conversion of a public company into a private company shall not be valid unless it is approved by an order of the Central Government on an application made in such form and …”; after (18 chars): “Central Government”.
- v1 rule labels: A **High**, B **High** (similarity 0.0460); v1 tie-break **High** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `None`, target `None`; defects: reextracted_source_clause_not_uniquely_matched.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 5. mat_06d03c5ce4d0d00dc77ebdaa — Arbitration And Conciliation Act 1996 / section:23

- Source: `src_0ad4e9c72da39b6e2ffcbafb` page 6, line 6 (SHA-256 `e6a3f49cadc97f08298b708f63c07f9452a420e43de4a7c08c1186da77e186f6`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (238 chars): “(2A) The respondent, in support of his case, may also submit a counterclaim or plead a set-off, which shall be adjudicated upon by the arbitral tribunal, if such counterclaim or set-off falls within the scope of the arbitration ag …”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:23`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (238 chars): “(2A) The respondent, in support of his case, may also submit a counterclaim or plead a set-off, which shall be adjudicated upon by the arbitral tribunal, if such counterclaim or set-off falls within the scope of the arbitration ag …”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 6. mat_fdb2b87808bcb525a732632e — Companies Act 2013 / section:46

- Source: `src_0cbccfdb70e8e9f057dbb00e` page 2, line 16 (SHA-256 `f0f1ff814a6f4fff582e3e542f3de46f0d25a06de39e5cd11aee187fd32e6f24`).
- v1 operation/fragments: `SUBSTITUTE`; before (43 chars): “issued under the common seal of the company”; after (178 chars): “issued under the common seal, if any, of the company or signed by two directors or by a director and the Company Secretary, wherever the company has appointed a Company Secretary”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.4103); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:46`; defects: none identified.
- v2 fragments: before (43 chars): “issued under the common seal of the company”; after (178 chars): “issued under the common seal, if any, of the company or signed by two directors or by a director and the Company Secretary, wherever the company has appointed a Company Secretary”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 7. mat_390c72d9d6d3e4ca87e8b0d2 — Arbitration And Conciliation Act 1996 / section:31

- Source: `src_0ad4e9c72da39b6e2ffcbafb` page 8, line 5 (SHA-256 `e6a3f49cadc97f08298b708f63c07f9452a420e43de4a7c08c1186da77e186f6`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (5 chars): “costs”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `INSERT`, target `section:31A`; defects: wording_changed_on_reextraction, target_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (2239 chars): “31A. (1) In relation to any arbitration proceeding or a proceeding under any of the provisions of this Act pertaining to the arbitration, the Court or arbitral tribunal, notwithstanding anything contained in the Code of Civil Proc …”.
- v2 rules: A **High** (REVIEW_REQUIRED_CROSS_SOURCE_MISMATCH); B **High** (REVIEW_REQUIRED_CROSS_SOURCE_MISMATCH).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 8. mat_9e349bb1642e64225e9503a1 — Companies Act 2013 / section:2

- Source: `src_73ff6b08cbbe209ab709e642` page 2, line 5 (SHA-256 `6c7e9d557747412f22e15e8dbd4242d8bf8a0d869771bfeccdf50163e94f670e`).
- v1 operation/fragments: `SUBSTITUTE`; before (714 chars): “Provided that where a company or body corporate, which is a holding company or a subsidiary or associate company of a company incorporated outside India and is required to follow a different financial year for consolidation of its …”; after (18 chars): “Provided also that”.
- v1 rule labels: A **High**, B **High** (similarity 0.0331); v1 tie-break **High** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `SUBSTITUTE`, target `section:2`; defects: wording_changed_on_reextraction.
- v2 fragments: before (21 chars): “Provided further that”; after (18 chars): “Provided also that”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 9. mat_a1406890a695e5217ea3311d — Arbitration And Conciliation Act 1996 / section:24

- Source: `src_0ad4e9c72da39b6e2ffcbafb` page 6, line 11 (SHA-256 `e6a3f49cadc97f08298b708f63c07f9452a420e43de4a7c08c1186da77e186f6`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (342 chars): “Provided further that the arbitral tribunal shall, as far as possible, hold oral hearings for the presentation of evidence or for oral argument on day-to-day basis, and not grant any adjournments unless sufficient cause is made ou …”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:24`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (342 chars): “Provided further that the arbitral tribunal shall, as far as possible, hold oral hearings for the presentation of evidence or for oral argument on day-to-day basis, and not grant any adjournments unless sufficient cause is made ou …”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 10. mat_f6b73bb3602ae415caa163a1 — Prevention Of Corruption Act 1988 / section:23

- Source: `src_294c0d2fedc5374a906e0e92` page 7, line 25 (SHA-256 `a4b24b643ade5061282fd1a0cb0a232ee8059de17b81673493c7e2497bf9c1bc`).
- v1 operation/fragments: `SUBSTITUTE`; before (18 chars): “section 13 (1) (c)”; after (10 chars): “clause (a)”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `SUBSTITUTE`, target `section:23`; defects: wording_changed_on_reextraction.
- v2 fragments: before (10 chars): “clause (c)”; after (10 chars): “clause (a)”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 11. mat_99dd581f7b342e821361f4fa — Specific Relief Act 1963 / section:41

- Source: `src_c402849814141b3fe1696d92` page 4, line 19 (SHA-256 `c5d552a1a07a54eaf2b6b18f2a03fa3761454de4d9ff0ffd00519a0e903299c1`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (222 chars): “(ha) if it would impede or delay the progress or completion of any infrastructure project or interfere with the continued provision of relevant facility related thereto or services being the subject matter of such project.”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `UNKNOWN`, target `section:41`; defects: compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 12. mat_1d047b61abe3fdec714bf1fc — Motor Vehicles Act 1988 / section:165

- Source: `src_95267bd1a6e6edd43848c03f` page 31, line 38 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (28 chars): “section 140 and section 163A”; after (11 chars): “section 164”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.2500); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:165`; defects: none identified.
- v2 fragments: before (28 chars): “section 140 and section 163A”; after (11 chars): “section 164”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 13. mat_8712bef392cb1761c552d536 — Disaster Management Act 2005 / section:79

- Source: `src_a234a3f5c6ac749e32f6f075` page 14, line 30 (SHA-256 `494f2c1d79272efd9b4a1460c6ed75c719b792271aea3b8ce2ba692da0ab04dd`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (602 chars): “(1A) Notwithstanding anything contained in sub-section (1), if any difficulty arises in giving effect to the provisions of this Act as amended by the Disaster Management (Amendment) Act, 2025, the Central Government may, by order …”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:79`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (602 chars): “(1A) Notwithstanding anything contained in sub-section (1), if any difficulty arises in giving effect to the provisions of this Act as amended by the Disaster Management (Amendment) Act, 2025, the Central Government may, by order …”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 14. mat_5bb9130dc72b18a8dd0463a5 — Motor Vehicles Act 1988 / section:15

- Source: `src_95267bd1a6e6edd43848c03f` page 4, line 27 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (21 chars): “more than thirty days”; after (92 chars): “one year after the driving licence has ceased to be effective, the licensing authority shall”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `UNKNOWN`, target `section:15`; defects: target_path_detail_mismatch, compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 15. mat_9c042001b4e5dc62cae919ba — Insolvency Bankruptcy Code 2016 / section:11

- Source: `src_53c55ae5c2470ca158488216` page 3, line 11 (SHA-256 `7f61e73bf67e3bd0b5db8a917c79a55118320a7f1fc90cc42379b6afe86158fc`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (47 chars): “or a pre-packaged insolvency resolution process”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:11`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (47 chars): “or a pre-packaged insolvency resolution process”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 16. mat_0773a4d10672e49537242824 — Motor Vehicles Act 1988 / section:40

- Source: `src_95267bd1a6e6edd43848c03f` page 6, line 30 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (23 chars): “a registering authority”; after (38 chars): “any registering authority in the State”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.4444); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:40`; defects: none identified.
- v2 fragments: before (23 chars): “a registering authority”; after (38 chars): “any registering authority in the State”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 17. mat_d1acc86ed566f3a993e1c036 — Motor Vehicles Act 1988 / section:206

- Source: `src_95267bd1a6e6edd43848c03f` page 42, line 2 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (644 chars): “(4) A police officer or other person authorised in this behalf by the State Government shall, if he has reason to believe that the driver of a motor vehicle has committed an offence under any of sections 183, 184, 185, 189, 190, 1 …”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:206`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (644 chars): “(4) A police officer or other person authorised in this behalf by the State Government shall, if he has reason to believe that the driver of a motor vehicle has committed an offence under any of sections 183, 184, 185, 189, 190, 1 …”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 18. mat_859f1a5bc4b6b3208d6a6994 — Disaster Management Act 2005 / section:11

- Source: `src_a234a3f5c6ac749e32f6f075` page 7, line 22 (SHA-256 `494f2c1d79272efd9b4a1460c6ed75c719b792271aea3b8ce2ba692da0ab04dd`).
- v1 operation/fragments: `SUBSTITUTE`; before (262 chars): “(2) The National Authority shall coordinate, in consultation with the Central Government and the State Governments and other stakeholders in the field of disaster management, for preparation and approval of the National Plan havin …”; after (129 chars): “(4) The National Authority shall review the National Plan once in every three years and update at least once in every five years.”.
- v1 rule labels: A **High**, B **High** (similarity 0.2258); v1 tie-break **High** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `SUBSTITUTE`, target `section:11`; defects: wording_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 19. mat_9563a4579cd8c87fb2ebf8dd — Motor Vehicles Act 1988 / section:74

- Source: `src_95267bd1a6e6edd43848c03f` page 13, line 16 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (23 chars): “(vii) self-help groups.”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `INSERT`, target `section:74`; defects: target_path_detail_mismatch.
- v2 fragments: before (0 chars): “”; after (23 chars): “(vii) self-help groups.”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 20. mat_61bdc9abc22419bc811f4af8 — Wild Life Protection Act 1972 / section:62

- Source: `src_0530e08f12edbc47c3ca7a48` page 13, line 2 (SHA-256 `fc62e6c7da4fde06944184fcb659402bb213c26b505375ce9783f22cdd879b2f`).
- v1 operation/fragments: `SUBSTITUTE`; before (67 chars): “other than those specified in Schedule I and Part II of Schedule II”; after (107 chars): “deemed not to be included in Schedule II for such area and for such period as specified in the notification”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.1212); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `SUBSTITUTE`, target `section:62`; defects: wording_changed_on_reextraction.
- v2 fragments: before (42 chars): “deemed to have been included in Schedule V”; after (107 chars): “deemed not to be included in Schedule II for such area and for such period as specified in the notification”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 21. mat_0e781f2b5e6feb33660fe843 — Motor Vehicles Act 1988 / section:94

- Source: `src_95267bd1a6e6edd43848c03f` page 14, line 27 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (34 chars): “or licence issued under any scheme”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:94`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (34 chars): “or licence issued under any scheme”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 22. mat_d7c70e6e86904b596cdb7209 — Aadhaar Act 2016 / section:39

- Source: `src_c81daaf704eb5583145bd290` page 7, line 20 (SHA-256 `738fba8fee6addb3cdef31082b0e0f22b8b456abdc41592815b06f20884140f1`).
- v1 operation/fragments: `SUBSTITUTE`; before (11 chars): “three years”; after (9 chars): “ten years”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.5000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:39`; defects: none identified.
- v2 fragments: before (11 chars): “three years”; after (9 chars): “ten years”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 23. mat_3a027c7f4cc70391e6c0a97c — Motor Vehicles Act 1988 / section:59

- Source: `src_95267bd1a6e6edd43848c03f` page 9, line 22 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (254 chars): “(4) The Central Government may, having regard to the public safety, convenience, protection of the environment and the objects of this Act, make rules prescribing the manner of recycling of motor vehicles and parts thereof which h …”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:59`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (254 chars): “(4) The Central Government may, having regard to the public safety, convenience, protection of the environment and the objects of this Act, make rules prescribing the manner of recycling of motor vehicles and parts thereof which h …”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 24. mat_590ac03da167238d7d338824 — Prevention Of Corruption Act 1988 / section:15

- Source: `src_294c0d2fedc5374a906e0e92` page 5, line 26 (SHA-256 `a4b24b643ade5061282fd1a0cb0a232ee8059de17b81673493c7e2497bf9c1bc`).
- v1 operation/fragments: `SUBSTITUTE`; before (24 chars): “clause (c) or clause (d)”; after (10 chars): “clause (a)”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.2857); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:15`; defects: none identified.
- v2 fragments: before (24 chars): “clause (c) or clause (d)”; after (10 chars): “clause (a)”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 25. mat_fcb1a39752da9c08f09a3504 — Motor Vehicles Act 1988 / section:96

- Source: `src_95267bd1a6e6edd43848c03f` page 14, line 29 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (197 chars): “(xxxiia) framing of schemes under sub-section (3) of section 67; (xxxiib) the promotion of effective competition, passenger convenience and safety, competitive fares and prevention of overcrowding;”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:96`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (197 chars): “(xxxiia) framing of schemes under sub-section (3) of section 67; (xxxiib) the promotion of effective competition, passenger convenience and safety, competitive fares and prevention of overcrowding;”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 26. mat_f110320fba1c8f219054c648 — Motor Vehicles Act 1988 / section:173

- Source: `src_95267bd1a6e6edd43848c03f` page 32, line 26 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (12 chars): “ten thousand”; after (8 chars): “one lakh”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:173`; defects: none identified.
- v2 fragments: before (12 chars): “ten thousand”; after (8 chars): “one lakh”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 27. mat_0e12529c90eed9079b2ebc59 — Insolvency Bankruptcy Code 2016 / section:12

- Source: `src_618aa45bac01b76de19ff611` page 2, line 7 (SHA-256 `f9902cdebb447c9af9eb724f4b71d01b335f5035ee19c6ddb6b3aeb20352b126`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (733 chars): “Provided further that the corporate insolvency resolution process shall mandatorily be completed within a period of three hundred and thirty days from the insolvency commencement date, including any extension of the period of corp …”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:12`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (733 chars): “Provided further that the corporate insolvency resolution process shall mandatorily be completed within a period of three hundred and thirty days from the insolvency commencement date, including any extension of the period of corp …”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 28. mat_3729e9c6bbccb8fa4bb132b1 — Prevention Of Corruption Act 1988 / section:16

- Source: `src_294c0d2fedc5374a906e0e92` page 5, line 28 (SHA-256 `a4b24b643ade5061282fd1a0cb0a232ee8059de17b81673493c7e2497bf9c1bc`).
- v1 operation/fragments: `SUBSTITUTE`; before (44 chars): “sub-section ( 2) of section 13 or section 14”; after (10 chars): “clause (b)”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `SUBSTITUTE`, target `section:16`; defects: wording_changed_on_reextraction.
- v2 fragments: before (10 chars): “clause (e)”; after (10 chars): “clause (b)”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 29. mat_95f88055beb515b1226fe96d — Wild Life Protection Act 1972 / section:50

- Source: `src_0530e08f12edbc47c3ca7a48` page 12, line 2 (SHA-256 `fc62e6c7da4fde06944184fcb659402bb213c26b505375ce9783f22cdd879b2f`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (18 chars): “derivative thereof”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `INSERT`, target `section:50`; defects: v1_after_text_was_anchor_not_inserted_operand, wording_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (21 chars): “or scheduled specimen”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 30. mat_123a9e691b0291bf0eb5fec8 — Motor Vehicles Act 1988 / section:182

- Source: `src_95267bd1a6e6edd43848c03f` page 33, line 6 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (39 chars): “which may extend to five hundred rupees”; after (19 chars): “ten thousand rupees”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.2000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `None`, target `None`; defects: reextracted_source_clause_not_uniquely_matched.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 31. mat_e20dcc1843f5295412f0547a — Companies Act 2013 / section:243

- Source: `src_73ff6b08cbbe209ab709e642` page 10, line 1 (SHA-256 `6c7e9d557747412f22e15e8dbd4242d8bf8a0d869771bfeccdf50163e94f670e`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (19 chars): “or sub-section (1A)”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:243`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (19 chars): “or sub-section (1A)”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 32. mat_3bf4e1de2910e0639568f12f — Banking Regulation Act 1949 / section:25

- Source: `src_726705f7fc61363b6e330510` page 3, line 38 (SHA-256 `e88810e9ddf46ad9103623120dca107dd31b0f21bfd37456d5a57267375fa534`).
- v1 operation/fragments: `SUBSTITUTE`; before (47 chars): “last Friday of every quarter or, if that Friday”; after (49 chars): “last day of the previous quarter, or, if that day”.
- v1 rule labels: A **High**, B **High** (similarity 0.6316); v1 tie-break **High** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `SUBSTITUTE`, target `section:25`; defects: target_path_detail_mismatch, wording_changed_on_reextraction.
- v2 fragments: before (55 chars): “last Friday of the previous quarter, or, if that Friday”; after (49 chars): “last day of the previous quarter, or, if that day”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 33. mat_398dac09f25a41f5fe085757 — Companies Act 2013 / section:164

- Source: `src_73ff6b08cbbe209ab709e642` page 7, line 43 (SHA-256 `6c7e9d557747412f22e15e8dbd4242d8bf8a0d869771bfeccdf50163e94f670e`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (78 chars): “(i) he has not complied with the provisions of sub-section (1) of section 165.”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:164`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (78 chars): “(i) he has not complied with the provisions of sub-section (1) of section 165.”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 34. mat_83cb8f64c8cf9597131f36e5 — Motor Vehicles Act 1988 / section:92

- Source: `src_95267bd1a6e6edd43848c03f` page 14, line 10 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (65 chars): “stage carriage or contract carriage, in respect of which a permit”; after (58 chars): “transport vehicle, in respect of which a permit or licence”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.5714); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:92`; defects: none identified.
- v2 fragments: before (65 chars): “stage carriage or contract carriage, in respect of which a permit”; after (58 chars): “transport vehicle, in respect of which a permit or licence”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 35. mat_688beef91bf9956c6f7b8319 — Insolvency Bankruptcy Code 2016 / section:31

- Source: `src_618aa45bac01b76de19ff611` page 3, line 12 (SHA-256 `f9902cdebb447c9af9eb724f4b71d01b335f5035ee19c6ddb6b3aeb20352b126`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (230 chars): “including the Central Government, any State Government or any local authority to whom a debt in respect of the payment of dues arising under any law for the time being in force, such as authorities to whom statutory dues are owed,”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:31`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (230 chars): “including the Central Government, any State Government or any local authority to whom a debt in respect of the payment of dues arising under any law for the time being in force, such as authorities to whom statutory dues are owed,”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 36. mat_db938a0f0eb92bab6fb078cc — Aadhaar Act 2016 / section:38

- Source: `src_c81daaf704eb5583145bd290` page 7, line 18 (SHA-256 `738fba8fee6addb3cdef31082b0e0f22b8b456abdc41592815b06f20884140f1`).
- v1 operation/fragments: `SUBSTITUTE`; before (11 chars): “three years”; after (9 chars): “ten years”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.5000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:38`; defects: none identified.
- v2 fragments: before (11 chars): “three years”; after (9 chars): “ten years”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 37. mat_08031e98498c98fa32a2e951 — Insolvency Bankruptcy Code 2016 / section:21

- Source: `src_2f4b081203dd22bf8f6a9f7a` page 3, line 28 (SHA-256 `bd4f44a1437260977604e7ca9d1ec4bf2afa43edaeb5177e50b92676bfaeb0cf`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (30 chars): “convertible into equity shares”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `INSERT`, target `section:21`; defects: v1_after_text_was_anchor_not_inserted_operand, wording_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (56 chars): “or completion of such transactions as may be prescribed,”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 38. mat_bc4acfabeb51f81d44d17bfc — Motor Vehicles Act 1988 / section:187

- Source: `src_95267bd1a6e6edd43848c03f` page 35, line 18 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (4 chars): “( c)”; after (22 chars): “of ten thousand rupees”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `SUBSTITUTE`, target `section:187`; defects: wording_changed_on_reextraction.
- v2 fragments: before (39 chars): “which may extend to one thousand rupees”; after (22 chars): “of ten thousand rupees”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 39. mat_70db190e17bf249b7b42387b — Motor Vehicles Act 1988 / section:137

- Source: `src_95267bd1a6e6edd43848c03f` page 18, line 23 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (201 chars): “(c) providing for limits of urban city by the State Governments under sub-section (1) of section 136A; and (d) providing for electronic monitoring and enforcement under sub-section (2) of section 136A.”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:137`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (201 chars): “(c) providing for limits of urban city by the State Governments under sub-section (1) of section 136A; and (d) providing for electronic monitoring and enforcement under sub-section (2) of section 136A.”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 40. mat_4c42b65249ca48221952c7f7 — Motor Vehicles Act 1988 / section:170

- Source: `src_95267bd1a6e6edd43848c03f` page 32, line 24 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (11 chars): “section 149”; after (11 chars): “section 150”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.5000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:170`; defects: none identified.
- v2 fragments: before (11 chars): “section 149”; after (11 chars): “section 150”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 41. mat_cc42b7cdc91c25c19b971c18 — Motor Vehicles Act 1988 / section:66

- Source: `src_95267bd1a6e6edd43848c03f` page 11, line 10 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (243 chars): “(q) to any transport vehicle having been issued a licence under a scheme, under sub-section (3) of section 67 or sub-section (1) of section 88A, or plying under such orders as may be issued by the Central Government or by the Stat …”.
- v1 rule labels: A **Medium**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:66`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (243 chars): “(q) to any transport vehicle having been issued a licence under a scheme, under sub-section (3) of section 67 or sub-section (1) of section 88A, or plying under such orders as may be issued by the Central Government or by the Stat …”.
- v2 rules: A **Medium** (PROVISIONAL_RULE_OUTPUT); B **Medium** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 42. mat_9251893450a9c8bd3d7a8590 — Companies Act 2013 / section:223

- Source: `src_0cbccfdb70e8e9f057dbb00e` page 4, line 21 (SHA-256 `f0f1ff814a6f4fff582e3e542f3de46f0d25a06de39e5cd11aee187fd32e6f24`).
- v1 operation/fragments: `SUBSTITUTE`; before (11 chars): “by the seal”; after (20 chars): “by the seal, if any,”.
- v1 rule labels: A **Low**, B **Low** (similarity 0.7500); v1 tie-break **Low** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:223`; defects: none identified.
- v2 fragments: before (11 chars): “by the seal”; after (20 chars): “by the seal, if any,”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 43. mat_e2b212ca6b91884eeccab0fd — Motor Vehicles Act 1988 / section:72

- Source: `src_95267bd1a6e6edd43848c03f` page 13, line 12 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (147 chars): “Provided that the Regional Transport Authority may waive any such condition for a stage carriage permit operating in a rural area, as it deems fit.”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:72`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (147 chars): “Provided that the Regional Transport Authority may waive any such condition for a stage carriage permit operating in a rural area, as it deems fit.”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 44. mat_f073384e10cbf86405d1be3d — Disaster Management Act 2005 / section:23

- Source: `src_a234a3f5c6ac749e32f6f075` page 8, line 46 (SHA-256 `494f2c1d79272efd9b4a1460c6ed75c719b792271aea3b8ce2ba692da0ab04dd`).
- v1 operation/fragments: `SUBSTITUTE`; before (315 chars): “(2) The State Authority shall coordinate the preparation of the State Plan having regard to the National Plan and guidelines laid down by the National Authority, and in consultation with local authorities, District Authorities, Ur …”; after (122 chars): “(5) The State Authority shall review the State Plan once in every three years and update atleast once in every five years.”.
- v1 rule labels: A **High**, B **High** (similarity 0.2571); v1 tie-break **High** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `SUBSTITUTE`, target `section:23`; defects: wording_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 45. mat_fe230e5ee9ce232f41dd593e — Aadhaar Act 2016 / section:3

- Source: `src_c81daaf704eb5583145bd290` page 2, line 34 (SHA-256 `738fba8fee6addb3cdef31082b0e0f22b8b456abdc41592815b06f20884140f1`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (307 chars): “(4) The Aadhaar number issued to an individual under sub-section (3) shall be a twelve-digit identification number and any alternative virtual identity as an alternative to the actual Aadhaar number of an individual that shall be …”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:3`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (307 chars): “(4) The Aadhaar number issued to an individual under sub-section (3) shall be a twelve-digit identification number and any alternative virtual identity as an alternative to the actual Aadhaar number of an individual that shall be …”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 46. mat_ca8210674f56599734ad7a8e — Banking Regulation Act 1949 / section:45ZC

- Source: `src_726705f7fc61363b6e330510` page 4, line 38 (SHA-256 `e88810e9ddf46ad9103623120dca107dd31b0f21bfd37456d5a57267375fa534`).
- v1 operation/fragments: `SUBSTITUTE`; before (10 chars): “one person”; after (53 chars): “one or more persons not exceeding four, successively,”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.2000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:45ZC`; defects: none identified.
- v2 fragments: before (10 chars): “one person”; after (53 chars): “one or more persons not exceeding four, successively,”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 47. mat_da9a0c78b92e51330bd0b0f1 — Competition Act 2002 / section:6

- Source: `src_53d4d0a959b38eab14c04abe` page 6, line 46 (SHA-256 `0012b8c0a5617e6697e1e6067dea0ec09ad56c177e2276daa28bf62edd3ab069`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (10 chars): “open offer”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `INSERT`, target `section:6A`; defects: wording_changed_on_reextraction, target_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (1095 chars): “6A. Nothing contained in sub-section (2A) of section 6 and section 43A shall prevent the implementation of an open offer or an acquisition of shares or securities convertible into other securities from various sellers, through a s …”.
- v2 rules: A **High** (REVIEW_REQUIRED_CROSS_SOURCE_MISMATCH); B **High** (REVIEW_REQUIRED_CROSS_SOURCE_MISMATCH).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 48. mat_b52f18d09b58658c1547c5fa — Motor Vehicles Act 1988 / section:197

- Source: `src_95267bd1a6e6edd43848c03f` page 39, line 17 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (39 chars): “which may extend to five hundred rupees”; after (23 chars): “of five thousand rupees”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.3636); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `None`, target `None`; defects: reextracted_source_clause_not_uniquely_matched.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 49. mat_cd3d33bc93222e0cafae2223 — Disaster Management Act 2005 / section:20

- Source: `src_a234a3f5c6ac749e32f6f075` page 8, line 30 (SHA-256 `494f2c1d79272efd9b4a1460c6ed75c719b792271aea3b8ce2ba692da0ab04dd`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (109 chars): “(c) the Director General of Police of the State shall be member of the State Executive Committee, ex officio.”.
- v1 rule labels: A **High**, B **High** (similarity 0.0000); v1 tie-break **High** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:20`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (109 chars): “(c) the Director General of Police of the State shall be member of the State Executive Committee, ex officio.”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 50. mat_ff373a92367a05c862b41846 — Prevention Of Corruption Act 1988 / section:17

- Source: `src_294c0d2fedc5374a906e0e92` page 5, line 35 (SHA-256 `a4b24b643ade5061282fd1a0cb0a232ee8059de17b81673493c7e2497bf9c1bc`).
- v1 operation/fragments: `SUBSTITUTE`; before (31 chars): “clause ( e) of sub-section ( 1)”; after (29 chars): “clause (b) of sub-section (1)”.
- v1 rule labels: A **Low**, B **Low** (similarity 0.8333); v1 tie-break **Low** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:17`; defects: none identified.
- v2 fragments: before (31 chars): “clause ( e) of sub-section ( 1)”; after (29 chars): “clause (b) of sub-section (1)”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## Limits and next step

This audit corrects identified extraction mechanics and rule behavior, but it does not certify the resulting text as the legally applicable provision. Before replacing the 50-case dataset, regenerate a complete versioned Phase 2/3 graph and materiality round, then independently inspect consolidated-source alignment. Legal validity remains unverified without qualified review.
