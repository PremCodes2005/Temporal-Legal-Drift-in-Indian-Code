# Materiality Disagreement Review — Version 2.1

> Superseded by v2.2, which corrects how less-specific versus conflicting provision paths are compared and reports paired-rule coverage.

This report re-extracts source clauses with extractor v2 and reassesses the original 19 cases. The v1 report and silver dataset remain unchanged. Machine outputs are not legal findings or gold labels.

- Confirmed extraction/alignment defects: **5**
- Review-required compound or unresolved cases: **4**
- Re-extracted aligned cases: **10**
- v1 disagreements: **19/19**
- v2 comparable cases (both rules emitted labels): **0**
- v2 agreement: not calculable (no comparable cases)

Rule B v1 assigned Medium solely from token similarity below 0.65 in all original disagreements. That ratio is not a legal-effect measure; v2 abstains with REVIEW_REQUIRED when low similarity is the only signal. Insertions correctly have an empty before fragment, but this makes a SequenceMatcher ratio of zero structurally uninformative.

## 1. mat_fdb2b87808bcb525a732632e — Companies Act 2013 / section:46

- Source: `src_0cbccfdb70e8e9f057dbb00e` page 2, line 16 (SHA-256 `f0f1ff814a6f4fff582e3e542f3de46f0d25a06de39e5cd11aee187fd32e6f24`).
- v1 operation/fragments: `SUBSTITUTE`; before (43 chars): “issued under the common seal of the company”; after (178 chars): “issued under the common seal, if any, of the company or signed by two directors or by a director and the Company Secretary, wherever the company has appointed a Company Secretary”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.4103); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:46`; defects: none identified.
- v2 fragments: before (43 chars): “issued under the common seal of the company”; after (178 chars): “issued under the common seal, if any, of the company or signed by two directors or by a director and the Company Secretary, wherever the company has appointed a Company Secretary”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 2. mat_390c72d9d6d3e4ca87e8b0d2 — Arbitration And Conciliation Act 1996 / section:31

- Source: `src_0ad4e9c72da39b6e2ffcbafb` page 8, line 5 (SHA-256 `e6a3f49cadc97f08298b708f63c07f9452a420e43de4a7c08c1186da77e186f6`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (5 chars): “costs”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `INSERT`, target `section:31A`; defects: wording_changed_on_reextraction, target_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (2353 chars): “31A. (1) In relation to any arbitration proceeding or a proceeding under any of the provisions of this Act pertaining to the arbitration, the Court or arbitral tribunal, notwithstanding anything contained in the Code of Civil Proc …”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 3. mat_99dd581f7b342e821361f4fa — Specific Relief Act 1963 / section:41

- Source: `src_c402849814141b3fe1696d92` page 4, line 19 (SHA-256 `c5d552a1a07a54eaf2b6b18f2a03fa3761454de4d9ff0ffd00519a0e903299c1`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (222 chars): “(ha) if it would impede or delay the progress or completion of any infrastructure project or interfere with the continued provision of relevant facility related thereto or services being the subject matter of such project.”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `UNKNOWN`, target `section:41`; defects: compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 4. mat_9c042001b4e5dc62cae919ba — Insolvency Bankruptcy Code 2016 / section:11

- Source: `src_53c55ae5c2470ca158488216` page 3, line 11 (SHA-256 `7f61e73bf67e3bd0b5db8a917c79a55118320a7f1fc90cc42379b6afe86158fc`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (47 chars): “or a pre-packaged insolvency resolution process”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `UNKNOWN`, target `section:11`; defects: compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 5. mat_0773a4d10672e49537242824 — Motor Vehicles Act 1988 / section:40

- Source: `src_95267bd1a6e6edd43848c03f` page 6, line 30 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (23 chars): “a registering authority”; after (38 chars): “any registering authority in the State”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.4444); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:40`; defects: none identified.
- v2 fragments: before (23 chars): “a registering authority”; after (38 chars): “any registering authority in the State”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 6. mat_9563a4579cd8c87fb2ebf8dd — Motor Vehicles Act 1988 / section:74

- Source: `src_95267bd1a6e6edd43848c03f` page 13, line 16 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (23 chars): “(vii) self-help groups.”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `UNKNOWN`, target `section:74`; defects: target_path_detail_mismatch, compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 7. mat_0e781f2b5e6feb33660fe843 — Motor Vehicles Act 1988 / section:94

- Source: `src_95267bd1a6e6edd43848c03f` page 14, line 27 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (34 chars): “or licence issued under any scheme”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:94`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (34 chars): “or licence issued under any scheme”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 8. mat_d7c70e6e86904b596cdb7209 — Aadhaar Act 2016 / section:39

- Source: `src_c81daaf704eb5583145bd290` page 7, line 20 (SHA-256 `738fba8fee6addb3cdef31082b0e0f22b8b456abdc41592815b06f20884140f1`).
- v1 operation/fragments: `SUBSTITUTE`; before (11 chars): “three years”; after (9 chars): “ten years”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.5000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:39`; defects: none identified.
- v2 fragments: before (11 chars): “three years”; after (9 chars): “ten years”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 9. mat_590ac03da167238d7d338824 — Prevention Of Corruption Act 1988 / section:15

- Source: `src_294c0d2fedc5374a906e0e92` page 5, line 26 (SHA-256 `a4b24b643ade5061282fd1a0cb0a232ee8059de17b81673493c7e2497bf9c1bc`).
- v1 operation/fragments: `SUBSTITUTE`; before (24 chars): “clause (c) or clause (d)”; after (10 chars): “clause (a)”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.2857); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:15`; defects: none identified.
- v2 fragments: before (24 chars): “clause (c) or clause (d)”; after (10 chars): “clause (a)”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 10. mat_f110320fba1c8f219054c648 — Motor Vehicles Act 1988 / section:173

- Source: `src_95267bd1a6e6edd43848c03f` page 32, line 26 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (12 chars): “ten thousand”; after (8 chars): “one lakh”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:173`; defects: none identified.
- v2 fragments: before (12 chars): “ten thousand”; after (8 chars): “one lakh”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 11. mat_95f88055beb515b1226fe96d — Wild Life Protection Act 1972 / section:50

- Source: `src_0530e08f12edbc47c3ca7a48` page 12, line 2 (SHA-256 `fc62e6c7da4fde06944184fcb659402bb213c26b505375ce9783f22cdd879b2f`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (18 chars): “derivative thereof”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `UNKNOWN`, target `section:50`; defects: v1_after_text_was_anchor_not_inserted_operand, compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 12. mat_123a9e691b0291bf0eb5fec8 — Motor Vehicles Act 1988 / section:182

- Source: `src_95267bd1a6e6edd43848c03f` page 33, line 6 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (39 chars): “which may extend to five hundred rupees”; after (19 chars): “ten thousand rupees”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.2000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `UNKNOWN`, target `section:182`; defects: compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 13. mat_83cb8f64c8cf9597131f36e5 — Motor Vehicles Act 1988 / section:92

- Source: `src_95267bd1a6e6edd43848c03f` page 14, line 10 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (65 chars): “stage carriage or contract carriage, in respect of which a permit”; after (58 chars): “transport vehicle, in respect of which a permit or licence”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.5714); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:92`; defects: none identified.
- v2 fragments: before (65 chars): “stage carriage or contract carriage, in respect of which a permit”; after (58 chars): “transport vehicle, in respect of which a permit or licence”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 14. mat_688beef91bf9956c6f7b8319 — Insolvency Bankruptcy Code 2016 / section:31

- Source: `src_618aa45bac01b76de19ff611` page 3, line 12 (SHA-256 `f9902cdebb447c9af9eb724f4b71d01b335f5035ee19c6ddb6b3aeb20352b126`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (230 chars): “including the Central Government, any State Government or any local authority to whom a debt in respect of the payment of dues arising under any law for the time being in force, such as authorities to whom statutory dues are owed,”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `INSERT`, target `section:31`; defects: none identified.
- v2 fragments: before (0 chars): “”; after (230 chars): “including the Central Government, any State Government or any local authority to whom a debt in respect of the payment of dues arising under any law for the time being in force, such as authorities to whom statutory dues are owed,”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 15. mat_db938a0f0eb92bab6fb078cc — Aadhaar Act 2016 / section:38

- Source: `src_c81daaf704eb5583145bd290` page 7, line 18 (SHA-256 `738fba8fee6addb3cdef31082b0e0f22b8b456abdc41592815b06f20884140f1`).
- v1 operation/fragments: `SUBSTITUTE`; before (11 chars): “three years”; after (9 chars): “ten years”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.5000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:38`; defects: none identified.
- v2 fragments: before (11 chars): “three years”; after (9 chars): “ten years”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 16. mat_08031e98498c98fa32a2e951 — Insolvency Bankruptcy Code 2016 / section:21

- Source: `src_2f4b081203dd22bf8f6a9f7a` page 3, line 28 (SHA-256 `bd4f44a1437260977604e7ca9d1ec4bf2afa43edaeb5177e50b92676bfaeb0cf`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (30 chars): “convertible into equity shares”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `INSERT`, target `section:21`; defects: v1_after_text_was_anchor_not_inserted_operand, wording_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (56 chars): “or completion of such transactions as may be prescribed,”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 17. mat_ca8210674f56599734ad7a8e — Banking Regulation Act 1949 / section:45ZC

- Source: `src_726705f7fc61363b6e330510` page 4, line 38 (SHA-256 `e88810e9ddf46ad9103623120dca107dd31b0f21bfd37456d5a57267375fa534`).
- v1 operation/fragments: `SUBSTITUTE`; before (10 chars): “one person”; after (53 chars): “one or more persons not exceeding four, successively,”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.2000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REEXTRACTED_ALIGNED**; new operation `SUBSTITUTE`, target `section:45ZC`; defects: none identified.
- v2 fragments: before (10 chars): “one person”; after (53 chars): “one or more persons not exceeding four, successively,”.
- v2 rules: A **Low** (PROVISIONAL_RULE_OUTPUT); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 18. mat_da9a0c78b92e51330bd0b0f1 — Competition Act 2002 / section:6

- Source: `src_53d4d0a959b38eab14c04abe` page 6, line 46 (SHA-256 `0012b8c0a5617e6697e1e6067dea0ec09ad56c177e2276daa28bf62edd3ab069`).
- v1 operation/fragments: `INSERT`; before (0 chars): “”; after (10 chars): “open offer”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.0000); v1 tie-break **Medium** (provisional).
- v2 extraction status: **CONFIRMED_EXTRACTION_DEFECT**; new operation `INSERT`, target `section:6A`; defects: wording_changed_on_reextraction, target_changed_on_reextraction.
- v2 fragments: before (0 chars): “”; after (1223 chars): “6A. Nothing contained in sub-section (2A) of section 6 and section 43A shall prevent the implementation of an open offer or an acquisition of shares or securities 15 of 1992. 15 of 1992. Insertion of a new section 6A. Open offers, …”.
- v2 rules: A **High** (PROVISIONAL_RULE_OUTPUT); B **High** (PROVISIONAL_RULE_OUTPUT).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## 19. mat_b52f18d09b58658c1547c5fa — Motor Vehicles Act 1988 / section:197

- Source: `src_95267bd1a6e6edd43848c03f` page 39, line 17 (SHA-256 `38624ae08543c7fd41fe470f18273817d2566e1581f0100de033b030f61b74a5`).
- v1 operation/fragments: `SUBSTITUTE`; before (39 chars): “which may extend to five hundred rupees”; after (23 chars): “of five thousand rupees”.
- v1 rule labels: A **Low**, B **Medium** (similarity 0.3636); v1 tie-break **Medium** (provisional).
- v2 extraction status: **REVIEW_REQUIRED**; new operation `UNKNOWN`, target `section:197`; defects: compound_operation_requires_event_split_or_adjudication.
- v2 fragments: before (0 chars): “”; after (0 chars): “”.
- v2 rules: A **ABSTAIN** (REVIEW_REQUIRED); B **ABSTAIN** (REVIEW_REQUIRED).
- Neither v1 nor v2 label is asserted legally correct; source evidence establishes textual provenance only.

## Limits and next step

This audit corrects identified extraction mechanics and rule behavior, but it does not certify the resulting text as the legally applicable provision. Before replacing the 50-case dataset, regenerate a complete versioned Phase 2/3 graph and materiality round, then independently inspect consolidated-source alignment. Legal validity remains unverified without qualified review.
