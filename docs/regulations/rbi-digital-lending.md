# RBI Digital Lending (2025 Directions → Credit Facilities Directions, Chapter III)

## Status: the standalone directions are repealed, so cite the new home

- **Repealed:** Reserve Bank of India (Digital Lending) Directions, 2025, RBI/2025-26/36, DOR.STR.REC.19/21.07.001/2025-26, dated 8 May 2025. It is listed as item 43 on RBI's withdrawn circulars page: https://www.rbi.org.in/scripts/NotificationUserWithdrawnCircular.aspx. Old text: https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=12848
- **Current home for NBFCs (incl. HFCs):** Reserve Bank of India (Non-Banking Financial Companies – Credit Facilities) Directions, 2025, **Chapter III "Digital Lending"**. RBI/DOR/2025-26/347, DOR.CRE.REC.No.266/07-01-008/2025-26, dated 28 Nov 2025, updated as on 15 Jul 2026. https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12957. Para 112 repeals the earlier instructions.
- **Commercial banks:** Reserve Bank of India (Commercial Banks – Credit Facilities) Directions, 2025, Chapter III, RBI/DOR/2025-26/154, 28 Nov 2025. https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13156. It uses the same para numbers (6, 12–16); the wording beyond the headings has not been checked.

In the deck and prompts, cite **"RBI NBFC Credit Facilities Directions 2025, Ch. III (Digital Lending), para X"**. Use the old numbering only when describing history.

Checked against rbi.org.in on 2026-11-20 by M8. Quotes are from the NBFC Direction (id=12957). All rows verified.

| Clause ID (NBFC Dir.) | Old 2025 para | Plain summary | Why it matters to a digital lender | FinShield control | Source | Verified |
|---|---|---|---|---|---|---|
| Para 6(2), 6(3), 6(4) | 5(ii)–(iv) | Do enhanced due diligence on a Lending Service Provider before signing, including its technical capability, data privacy policies and storage systems, and keep monitoring it. | LSP staff and apps touch borrower KYC. The lender has to vet and watch them. | Partner LSP users are in the detection baseline, with signal S7 (unassigned customers) | id=12957 | yes |
| Para 6(7) | 5(vii) | The lender "shall remain fully responsible and liable for all acts and omissions of the LSP". | A leak by an LSP agent is the lender's problem. | Detection covers LSP principals like internal staff | id=12957 | yes |
| Para 10(1)–(2) | — | Disburse loans only into the borrower's own bank account, never to a third-party or LSP account, except narrow listed cases (statutory mandate, co-lending, specific end use). Repayment goes directly to the NBFC's account with no pass-through or pool account. | Money diverted to a changed bank account is both fraud and a breach of this rule (SC-08). | Signal S10 (abnormal disbursement to a recently changed account) | id=12957 | yes |
| Para 12(1)–(4) | 11(i)–(iv) | The lender and any LSP facing borrowers must name nodal grievance redressal officers, publish them on the website, the DLA and the KFS, and allow escalation to the RBI Ombudsman after 30 days. | Breach-affected borrowers will complain. Someone must own the response. | Customer notice draft includes the grievance contact field | id=12957 | yes |
| Para 13(1) | 12(i) | Data collected by the lender's or LSP's app must be need-based, with the borrower's **prior and explicit consent**, and with an audit trail. No access to files and media, contacts, call logs or telephony. Camera, microphone and location only once, for onboarding/KYC. | Every KYC data point needs consent with an audit trail. | Consent ledger (purpose per customer), evidence chain | id=12957 | yes |
| Para 13(2) | 12(ii) | The borrower can revoke consent and ask for their data to be deleted or forgotten. | Withdrawn consent must stop further use. | Consent ledger tracks withdrawn consents; Privacy screen "withdrawn consents accessed" | id=12957 | yes |
| Para 13(3) | 12(iii) | Disclose the purpose of consent at each stage of interface. | Purpose limitation: KYC for a loan is not for marketing (SC-07). | Signal S9 (purpose mismatch) | id=12957 | yes |
| Para 14(1) | 13(i) | LSPs may store only basic minimal data (name, address, contact). The lender is responsible for data privacy and security. | LSPs should not be holding KYC files. If they access them, it is a red flag. | Signal S1/S7 on LSP principals | id=12957 | yes |
| Para 14(2) | 13(ii) | Publish a data-storage policy covering retention, destruction and "standards for handling security breach". | The breach-handling standard has to exist on paper. FinShield's playbook is the operational version. | Step Functions incident playbook | id=12957 | yes |
| Para 14(3) | 13(iii) | Do not store or collect biometric data unless statute allows it. | Limits what the KYC store may contain. | Aadhaar last-4 only (Aadhaar vault assumption) | id=12957 | yes |
| Para 14(4) | 13(iv) | Store all data **only on servers in India**. If it is processed abroad, delete it there and bring it back within 24 hours. | Data residency. Cloud region choice matters. | Everything runs in ap-south-1 (Mumbai) | id=12957 | yes |
| Para 15(1)–(2) | 14(i)–(ii) | Lender and LSPs must publish a comprehensive privacy policy naming third parties allowed to collect data. | Public commitments the lender must live up to. | Not a FinShield control | id=12957 | yes |
| Para 16 | 15(i) | Comply with RBI's and other agencies' technology and cybersecurity standards. | Links digital lending to the RBI cyber directions (see `rbi-it-governance-cyber-nbfc.md`). | Detection, containment, evidence | id=12957 | yes |

## Note: no breach reporting in this chapter

The digital lending text has **no incident-reporting clause**. Do not cite it for the RBI 6-hour deadline. That comes from the NBFC cybersecurity Direction, para 141 / para 28 (see `rbi-it-governance-cyber-nbfc.md`).

## Old dates (history)

The 2025 Directions came into force immediately on 8 May 2025, except para 6 (multi-lender LSP, 1 Nov 2025) and para 17 (DLA reporting on CIMS, 15 Jun 2025). They replaced the Guidelines on Digital Lending of 2 Sep 2022 and the DLG circular of 8 Jun 2023.
