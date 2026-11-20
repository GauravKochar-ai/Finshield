# Digital Personal Data Protection Act, 2023 and DPDP Rules, 2025

Wording rule: FinShield offers **DPDP-aligned readiness and controls**. Never say "DPDP compliant". The consent component is a **consent ledger**, never a "Consent Manager" (a registered role under s.2(g), s.6(9) and Rule 4).

Official texts (meity.gov.in, Gazette copies):
- [A] Act, Gazette No. 25, 11 Aug 2023: https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf
- [R] Rules, G.S.R. 846(E), 13 Nov 2025 (English text from p.24): https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf
- [C] Act commencement notification, G.S.R. 843(E), 13 Nov 2025: https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf

Checked against the official PDFs on 2026-11-20 by M8.

## Phasing (Rule 1; G.S.R. 843(E))

| Commences | What | Date |
|---|---|---|
| On publication | Rules 1, 2, 17–21 (Board). Act s.1(2), s.2, ss.18–26, 35, 38–43, s.44(1),(3). | 13 Nov 2025 |
| One year later | Rule 4 (Consent Manager registration, a regulated role, not our consent ledger). Act s.6(9), s.27(1)(d). | about 13 Nov 2026 |
| Eighteen months later | Rules 3, 5–16, 22, 23 (notice, **security safeguards r.6, breach intimation r.7, retention r.8**, contact r.9, SDF r.13). Act ss.3–17 including **all of s.8**, ss.28–34 (penalties). | about 13 May 2027 |

The Gazette is dated 13 Nov 2025 but was uploaded on 14 Nov 2025, so give the derived dates as "about". **As of Nov 2026 the core obligations (s.8, Rules 6–7, penalties) are not yet in force.** That is why FinShield shows readiness timers, not legal deadlines.

## Clauses

| Clause ID | Plain summary | Why it matters to a digital lender | FinShield control | Source | Verified |
|---|---|---|---|---|---|
| Act s.2(u) | Defines a "personal data breach": any unauthorised processing, or accidental disclosure, acquisition, sharing, use, alteration, destruction or loss of access, that compromises confidentiality, integrity or availability. | An insider bulk-downloading KYC files and uploading them outside is a breach under this definition. | Detection signals S1, S4, S7, S9 | [A] | yes |
| Act s.4(1) | Personal data may be processed only for a lawful purpose, with consent or for a legitimate use. | Every KYC read needs a lawful basis. | Consent ledger, S9 purpose mismatch | [A] | yes |
| Act s.5(1) | A notice must accompany or come before every consent request. Rule 3 sets its content. | Loan app onboarding must give notice before collecting KYC. | Not a FinShield control (product/legal) | [A] | yes |
| Act s.6(1) | Consent must be free, specific, informed, unconditional and unambiguous, for a specified purpose, and limited to the data needed for it. | KYC given for loan processing cannot be reused for marketing (SC-07). | Consent ledger + signal S9 (purpose mismatch) | [A] | yes |
| Act s.7 | Lists the legitimate uses that allow processing without consent, clauses (a) to (i). | Some processing (for example legal obligations) does not need consent. Detection must not flag it. | Exceptions E1/E2 (scheduled jobs, approved tickets) | [A] | yes |
| Act s.8(5) | A Data Fiduciary must protect personal data it holds or that a processor handles for it, through reasonable security safeguards to prevent a breach. | This is the core duty. The maximum penalty is ₹250 crore (Schedule Sl. 1). | Detection, automated containment, evidence chain | [A] | yes |
| Act s.8(6) | On a breach, inform the Board and each affected Data Principal, in the form and manner prescribed (Rule 7). | Notification to the Board and to borrowers. The maximum penalty is ₹200 crore (Schedule Sl. 2). | DPB notice draft + customer notice draft, readiness timers | [A] | yes |
| Act s.8(7), 8(8) | Erase personal data when consent is withdrawn or the purpose is no longer served, unless a law requires retention. Processors must erase too. | KYC of closed or rejected applicants cannot be kept indefinitely without a legal reason. | Not covered yet (roadmap) | [A] | yes |
| Act s.8(9); Rule 9 | Publish the business contact of a DPO (if applicable) or another person who can answer, prominently on the website or app. | Borrowers need a named contact after a breach. | Customer notice draft includes the contact field | [A], [R] | yes |
| Act s.10(2); Rule 13 | A Significant Data Fiduciary must appoint a DPO based in India, an independent data auditor, and do a DPIA and audit every 12 months. | Large lenders may be notified as SDFs. | Evidence chain and compliance map support the audit | [A], [R] | yes |
| Act s.33(1) + Schedule | Maximum penalties ("may extend to"): Sl.1 security safeguards ₹250 cr; Sl.2 breach notice ₹200 cr; Sl.3 children ₹200 cr; Sl.4 SDF ₹150 cr; Sl.7 any other ₹50 cr. | Shows the size of the risk. These are caps, not fixed fines. | n/a (deck: "up to ₹250 crore") | [A] | yes |
| Rule 6(1)(a)–(g) | Minimum safeguards: (a) encryption, obfuscation, masking or tokens; (b) access control; (c) visibility through logs, monitoring and review; (d) continuity such as backups; (e) keep logs for 1 year; (f) security clauses in processor contracts; (g) technical and organisational measures. | This is the checklist an auditor will use. | (a) Aadhaar last-4 and fake PAN only, masking before Bedrock; (b) containment + approvals; (c) CloudTrail + detection; (e) raw-events 1-year lifecycle | [R] | yes |
| Rule 7(1) | On becoming aware of a breach, inform each affected Data Principal without delay. State the nature, extent and timing; likely consequences; mitigation; steps they can take; a contact. | Borrowers must hear quickly and in plain language. | `CUSTOMER_NOTICE` draft | [R] | yes |
| Rule 7(2)(a) | Inform the Board without delay. State the nature, extent, timing, location and likely impact. | An initial notice comes before the 72 h report. | `DPB_NOTICE` draft | [R] | yes |
| Rule 7(2)(b) | Within **72 hours of becoming aware** (or longer if the Board allows in writing), send the Board: (i) updated details; (ii) facts, circumstances and reasons; (iii) mitigation; (iv) findings on who caused it; (v) remedial measures; (vi) report on notices to Data Principals. | This is the 72-hour deadline on the Overview. | DPB 72 h readiness timer; evidence chain supplies (ii)–(iv) | [R] | yes |
| Rule 8(3) + Seventh Schedule | Keep personal data, traffic data and processing logs for at least 1 year from processing, then erase unless a law requires more. | Detection logs and evidence must survive at least a year. | Evidence bucket Object Lock 1 year; raw-events 1-year lifecycle | [R] | yes (Seventh Schedule purposes not read in detail) |
| Rule 4 + First Schedule Part A; Act s.2(g), s.6(9) | Consent Managers must register with the Board. | We must not call the consent ledger a "Consent Manager". | Wording rule | [R], [A] | yes |

## Deadline wording

The config label "Data Protection Board detailed report 72 h, from detection" needs two fixes:

1. Rule 7(2)(b) says **"within seventy-two hours of becoming aware"**, not "detection". Starting the timer at `detected_at` is a conservative internal proxy. The text should say so.
2. The 72 h report is the *detailed* one. An initial Board notice (r.7(2)(a)) and notices to Data Principals (r.7(1)) are due **"without delay"**, with no fixed hours.

Suggested display text:

> DPB detailed report: 72 h from becoming aware (Rule 7(2)(b), in force about May 2027). Readiness timer starts at FinShield detection.
