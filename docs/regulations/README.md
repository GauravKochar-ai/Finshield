# Regulation summaries (for the `finshield-dev-rules` bucket)

One file per regulation. Each row has: clause ID, plain summary, why it matters to a digital lender, FinShield control, official source link and verified yes/verify. Only rows marked **yes** may be used in AI prompts, report drafts, the web app or the deck.

| File | Regulation | Status |
|---|---|---|
| [dpdp-act-2023-and-rules-2025.md](dpdp-act-2023-and-rules-2025.md) | DPDP Act 2023 + DPDP Rules 2025 (phasing dates) | Verified on meity.gov.in |
| [rbi-digital-lending.md](rbi-digital-lending.md) | RBI Digital Lending (2025 Directions, now NBFC Credit Facilities Directions 2025, Ch. III) | Verified on rbi.org.in (1 row "verify") |
| [rbi-it-governance-cyber-nbfc.md](rbi-it-governance-cyber-nbfc.md) | RBI IT governance and cyber security directions for NBFCs (2023 MD, now NBFC Cybersecurity Directions 2026) | Verified on rbi.org.in |
| [rbi-it-outsourcing.md](rbi-it-outsourcing.md) | RBI IT outsourcing directions (2023 MD, now NBFC Managing Risks in Outsourcing Directions 2025, Ch. IV) | Verified on rbi.org.in |
| [cert-in-directions-2022.md](cert-in-directions-2022.md) | CERT-In Directions, 28 April 2022 | Verified on cert-in.org.in |

Upload (Ajay): `aws s3 sync docs/regulations/ s3://finshield-dev-rules/ --exclude "README.md" --region ap-south-1`

## Notes for Keshav (M1/M5): changes needed outside docs/

1. **Wrong CERT-In citation in fixtures.** `contract/fixtures/ai_explanation.json`, `alert.json` and `api_alert_detail.json` cite `CERT-In Directions 2022, "Para (i)"` for the 6-hour rule. Direction (i) is NTP clock sync. The 6-hour rule is **Direction (ii)**.
2. **RBI Digital Lending Directions 2025 are repealed.** RBI moved them on 28 Nov 2025 into the *RBI (NBFC – Credit Facilities) Directions, 2025*, Chapter III, with new para numbers (old 12 → new 13, and so on). Prompts must cite the new instrument.
3. **RBI 6 h is not in the Digital Lending text.** It comes from the *RBI (NBFCs – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026* (31 Jul 2026), para 141 (Middle Layer and above) / para 28 (Base Layer ≥ ₹500 cr): "within six hours of detection on DAKSH platform".
4. **Deadline numbers in `contract/config.json` are correct (6, 6, 72).** The labels could be more precise:
   - CERT-In: legal trigger is "noticing such incidents or being brought to notice", not detection.
   - DPB: legal trigger is "becoming aware" (Rule 7(2)(b)). Rule 7 is in force only from about 13 May 2027. The 72 h report is the *detailed* one; an initial notice to the Board and to Data Principals is due "without delay".
   - Suggested labels: "RBI incident report: 6 h from detection (readiness timer)", "CERT-In report: 6 h from noticing (readiness timer)", "DPB detailed report: 72 h from becoming aware (readiness timer)".
5. **Both 2023 RBI IT Master Directions are repealed for NBFCs.** IT Governance (7 Nov 2023) → NBFC Cybersecurity Directions 2026. IT Outsourcing (10 Apr 2023) → NBFC Managing Risks in Outsourcing Directions 2025, Ch. IV. Do not cite DLP or a log-retention period from RBI; neither text has one.
6. **Penalty amounts are maximums.** "Up to ₹250 crore" (security safeguards) and "up to ₹200 crore" (breach notice), from the Schedule to the DPDP Act.
