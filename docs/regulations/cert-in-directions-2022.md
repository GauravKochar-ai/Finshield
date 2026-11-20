# CERT-In Directions under Section 70B(6) of the IT Act, 2000 (28 April 2022)

Instrument: Directions No. 20(3)/2022-CERT-In, dated 28.04.2022.
Official text: https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf
FAQ (May 2022): https://www.cert-in.org.in/PDF/FAQs_on_CyberSecurityDirections_May2022.pdf
Extension notice (27.06.2022): https://www.cert-in.org.in/PDF/CERT-In_directions_extension_MSMEs_and_validation_27.06.2022.pdf
Index page: https://www.cert-in.org.in/Directions70B.jsp

Checked against the official PDFs on 2026-11-20 by M8. The text numbers its directions (i) to (vi) in lowercase roman numerals. Cite them as "Direction (ii)", never "Para (i)".

| Clause ID | Plain summary | Why it matters to a digital lender | FinShield control | Source | Verified |
|---|---|---|---|---|---|
| Direction (i) | Sync all ICT system clocks to NIC or NPL NTP servers, or to servers traceable to them. | Evidence timestamps must line up with CERT-In's and RBI's, or the incident timeline can be challenged. | Every event and evidence entry carries an ISO timestamp with +05:30 offset; AWS time sync (Amazon Time Sync Service) [time-source traceability to NPL/NIC not yet confirmed] | Directions p.2 | yes |
| Direction (ii) | Report cyber incidents listed in Annexure I to CERT-In **within 6 hours of noticing them or being told about them**. Report by email (incident@cert-in.org.in), phone (1800-11-4949) or fax (1800-11-6969). | A KYC leak is a reportable incident. The 6-hour clock is the tightest one a lender faces. | CERT-In readiness timer from `detected_at`, CERT-In draft report (`CERTIN_FORM`) | Directions p.2 | yes |
| FAQ Q 30 | The 6-hour report may contain what is known at the time. More details can follow "within reasonable time". | The team can file a first report quickly and then add the full analysis later. | CERT-In draft is a first report built from the alert and evidence | FAQ p.10 | yes |
| FAQ Q 13 | The entity that notices the incident must report it. The obligation cannot be transferred or indemnified away. | A lender cannot leave reporting to its lending service provider or cloud vendor by contract. | Report drafts are generated for the regulated entity | FAQ | yes |
| Direction (iii) + Annexure II | Designate a Point of Contact for CERT-In and send their details in the Annexure II format to info@cert-in.org.in. | Someone has to own the 6-hour report. | Not a FinShield control (organisational). Report drafts name the PoC as a field to fill. | Directions p.3, p.7 | yes |
| Direction (iv) | Enable logs on all ICT systems and keep them securely for a **rolling 180 days within India**. Provide them to CERT-In with any incident report or when ordered. | Without the logs, the lender cannot show what happened. They must stay in India. | CloudTrail plus raw-events bucket in ap-south-1 with a 1-year lifecycle (more than 180 days), and the evidence chain | Directions p.3 | yes |
| Direction (v) | Data centres, VPS, cloud and VPN providers must register subscriber details and keep them for 5 years. | Usually not the lender itself. It applies to the lender's cloud and VPN vendors. | Not applicable | Directions p.3 | yes |
| Direction (vi) + Annexure III | Virtual asset service providers must keep KYC and transaction records for 5 years. | Not applicable to a lender unless it also deals in virtual assets. | Not applicable | Directions p.4, p.8 | yes |
| Annexure I (iii) | "Unauthorised access of IT systems/data" is a reportable incident. | Covers SC-01, SC-04 and SC-07. | Detection signals S1, S3, S7, S9 | Directions p.5 | yes |
| Annexure I (xi), (xii) | "Data Breach" and "Data Leak" are reportable incidents. | Covers the KYC exfiltration story. | Detection signal S4 (external upload), CERT-In draft | Directions p.5 | yes |
| Annexure I (xviii) | "Attacks or malicious/ suspicious activities affecting Cloud computing systems/servers/software/applications" are reportable. | Covers SC-06 (StopLogging) and SC-09 (bucket made public). | Signals S8, S11, GuardDuty and Config feeds | Directions p.5 | yes |
| Closing para; FAQ Q 44 | The directions take effect 60 days after issue (28 June 2022, derived, the text gives no calendar date). For MSMEs, and for items (v)(a) and (v)(f), the date moved to 25 Sept 2022. | Fully in force. No transition period remains. | n/a | Directions p.4; extension notice p.2 | yes |
| Closing para; FAQ Q 23 | Not complying can lead to action under Section 70B(7) of the IT Act. | This is the penalty for reporting late. | n/a | Directions p.4 | yes |

## Deadline wording

The config label "CERT-In 6 h, from detection, as configured readiness timer" is close but not exact. The legal trigger is **"noticing such incidents or being brought to notice"**. It also covers incidents someone else reports to the lender, not only ones FinShield detects. Suggested display text:

> CERT-In: 6 h from noticing (Direction (ii)). Readiness timer starts at FinShield detection.

The 6 hours itself is fixed by the directions. It must not be shown as configurable.

## Corrections for other modules

- `contract/fixtures/ai_explanation.json`, `alert.json` and `api_alert_detail.json` cite `"CERT-In Directions 2022", "Para (i)"` for the 6-hour rule. The correct citation is **Direction (ii)**. Owner M1/M5 (Keshav).
