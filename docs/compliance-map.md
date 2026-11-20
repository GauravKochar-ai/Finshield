# FinShield compliance map

**DPDP-aligned readiness and controls.** This map shows which FinShield control supports each obligation. It is not a claim of compliance or certification. The consent component is a **consent ledger**.

Clause details, verbatim checks and source links are in [`docs/regulations/`](regulations/). "Verified" means M8 checked the clause number and meaning against the official text on rbi.org.in, meity.gov.in or cert-in.org.in on 2026-11-20. Rows marked **verify** must not appear in the deck or AI prompts.

Screens follow the M6 spec: Overview, Alert detail, Reports, Privacy, Compliance map, Accuracy, Rules, Approvals.

## Indian regulations

| ID | Regulation | Clause | Obligation | FinShield control | Evidence produced | Screen | Verified |
|---|---|---|---|---|---|---|---|
| IN-01 | DPDP Act 2023 | s.8(5) | Reasonable security safeguards to prevent a personal data breach | Detection (S1–S11), automated containment, sealed evidence | Alert with signals and points, containment entries, evidence chain | Alert detail | yes |
| IN-02 | DPDP Rules 2025 | r.6(1)(a) | Encryption, masking or tokenisation of personal data | Aadhaar last-4 and fake PAN only; masking plus Bedrock Guardrail before AI | Masked AI input, Guardrail intervention count | Privacy | yes |
| IN-03 | DPDP Rules 2025 | r.6(1)(b) | Access control over computer resources | Containment (revoke sessions, deactivate keys, bucket deny), approvals for emergency roles (S3) | Containment evidence entries, IAM/bucket policy changes | Alert detail | yes |
| IN-04 | DPDP Rules 2025 | r.6(1)(c) | Visibility of access through logs, monitoring and review | CloudTrail data events on the KYC bucket into EventBridge; detection | Unified events, alert timeline | Alert detail (Timeline) | yes |
| IN-05 | DPDP Rules 2025 | r.6(1)(e); r.8(3) | Keep logs for at least one year | Raw-events bucket with 1-year lifecycle; evidence bucket in Object Lock compliance mode for 1 year | Object Lock retention on evidence objects | Alert detail (Evidence) | yes |
| IN-06 | DPDP Act 2023 / Rules 2025 | s.8(6); r.7(1) | Inform affected Data Principals without delay | Customer notice draft | `CUSTOMER_NOTICE` report | Reports | yes |
| IN-07 | DPDP Act 2023 / Rules 2025 | s.8(6); r.7(2)(a) | Inform the Data Protection Board without delay | DPB notice draft | `DPB_NOTICE` report | Reports | yes |
| IN-08 | DPDP Rules 2025 | r.7(2)(b) | Detailed report to the Board within 72 h of becoming aware | DPB 72 h readiness timer from `detected_at`; evidence chain supplies facts, cause and mitigation | Deadline on alert, DPB draft, evidence export | Overview (deadlines), Reports | yes |
| IN-09 | DPDP Act 2023 | s.6(1); s.4(1) | Consent is purpose-specific; processing only for a lawful purpose | Consent ledger + signal S9 (purpose mismatch), SC-07 | Alert with S9 facts (customers, purpose) | Privacy, Alert detail | yes |
| IN-10 | RBI NBFC Credit Facilities Dir. 2025, Ch. III | para 13(1) | Need-based data collection with prior explicit consent and an audit trail | Consent ledger; evidence chain | Consent records, evidence entries | Privacy | yes |
| IN-11 | RBI NBFC Credit Facilities Dir. 2025, Ch. III | para 13(2) | Borrower can revoke consent and ask for deletion | Consent ledger tracks withdrawn consents; flags access after withdrawal | Privacy counter "withdrawn consents accessed" | Privacy | yes |
| IN-12 | RBI NBFC Credit Facilities Dir. 2025, Ch. III | para 6(7) | Lender stays fully liable for its LSP's acts | LSP users scored like staff; S7 unassigned customer access (SC-04) | Alerts on partner principals | Alert detail | yes |
| IN-13 | RBI NBFC Credit Facilities Dir. 2025, Ch. III | para 14(4) | Data stored only on servers in India | Whole stack in ap-south-1 | Stack region, bucket locations | Architecture | yes |
| IN-14 | RBI NBFC Credit Facilities Dir. 2025, Ch. III | para 14(3) | No biometric data stored | Aadhaar last-4 only; `kyc_label` flags a full Aadhaar visible in an image | Privacy event "unmasked Aadhaar file" | Privacy | yes |
| IN-15 | RBI NBFC Cybersecurity Dir. 2026 | para 141 (Middle Layer+); para 28 (Base Layer ≥ ₹500 cr) | Report cyber incidents to RBI (DAKSH) within 6 hours of detection | RBI 6 h readiness timer; RBI incident report draft | Deadline on alert, `RBI_INCIDENT` report | Overview, Reports | yes |
| IN-16 | CERT-In Directions 2022 | Direction (ii) + Annexure I (iii), (xi), (xii), (xviii) | Report incidents to CERT-In within 6 hours of noticing | CERT-In 6 h readiness timer; CERT-In form draft | Deadline on alert, `CERTIN_FORM` report | Overview, Reports | yes |
| IN-17 | CERT-In Directions 2022 | Direction (iv) | Keep ICT logs for a rolling 180 days within India | CloudTrail + raw-events bucket in ap-south-1, 1-year lifecycle | Log objects in ap-south-1 | Compliance map | yes |
| IN-18 | CERT-In Directions 2022 | Direction (i) | Sync clocks to NIC/NPL NTP or traceable servers | Not claimed: NTP configuration is the lender's infrastructure setting. FinShield records ISO timestamps (+05:30) on every event and evidence entry. | Timestamps in evidence | Alert detail (Evidence) | yes (clause); control NOT_APPLICABLE |
| IN-19 | AWS Config managed rules | n/a | Sensitive bucket must not be public | Config rule `s3-bucket-public-read-prohibited` → S11 (SC-09) | Config result, alert | Overview (Config tiles) | n/a (AWS control, not a clause) |
| IN-20 | RBI NBFC Cybersecurity Dir. 2026 | paras 109–111 | Monitor audit trails and system logs to detect unauthorised activity; audit trails as forensic evidence | CloudTrail data events, detection, hash-chained evidence | Alert timeline, evidence chain | Alert detail | yes |
| IN-21 | RBI NBFC Cybersecurity Dir. 2026 | paras 113–115 | Supervise and log privileged access; MFA for privileged users of critical systems (risk-based) | S3 emergency role without approval, S5 MFA fatigue, Config MFA rule | Alert signals, Config result | Alert detail, Overview | yes |
| IN-22 | RBI NBFC Cybersecurity Dir. 2026 | paras 139–146; para 84 | Incident response and Cyber Crisis Management Plan (detect, respond, contain, recover) | Step Functions incident workflow, containment, release | Workflow execution, containment evidence | Alert detail | yes |
| IN-23 | RBI NBFC Outsourcing Dir. 2025, Ch. IV | para 61 | Service provider reports incidents without undue delay so the NBFC can report to RBI within 6 h of the provider's detection | RBI 6 h timer from FinShield detection | Alert deadlines | Overview | yes |
| IN-24 | RBI NBFC Outsourcing Dir. 2025, Ch. IV | para 74(ii); para 81; para 87 | Unrestricted access to provider data and logs; no data erased during exit | Evidence stays in the lender's own Object Lock bucket; export | Evidence export | Alert detail (Evidence) | yes |
| IN-25 | RBI NBFC Outsourcing Dir. 2025, Ch. IV | para 97(xi) | Integrate cloud provider logs into the NBFC's SOC | CloudTrail → EventBridge → detection | Unified events | Alert detail (Timeline) | yes |

## Deadline wording (confirmed with notes)

The configured wording is "RBI 6 h, CERT-In 6 h, Data Protection Board detailed report 72 h, from detection, as configured readiness timers". Checked against the texts:

| Body | Hours | Official trigger | Matches "from detection"? |
|---|---|---|---|
| RBI | 6 | "within six hours of detection" (NBFC Cybersecurity Dir. 2026, para 141 / 28) | Yes |
| CERT-In | 6 | "within 6 hours of noticing such incidents or being brought to notice" (Direction (ii)) | Close. Detection is one way of noticing; incidents reported by others also start the clock. |
| DPB | 72 | "within seventy-two hours of becoming aware" (DPDP Rules r.7(2)(b)); in force about 13 May 2027 | Close. `detected_at` is a conservative proxy. Initial notices to the Board and Data Principals are due "without delay". |

The hour values in `contract/config.json` (6, 6, 72) are correct. No change to the numbers is needed. Only the explanatory text should change (see the notes for Keshav in [`docs/regulations/README.md`](regulations/README.md)).

## SOC 2 and ISO 27001-aligned controls

Owned by Roopak. To be added to this file and to `simulator/seed/compliance_controls.json`.
