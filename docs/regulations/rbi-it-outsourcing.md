# RBI IT outsourcing directions

## Status: the 2023 Master Direction is repealed for NBFCs, so cite the 2025 Directions

- **Current:** Reserve Bank of India (Non-Banking Financial Companies – Managing Risks in Outsourcing) Directions, 2025, **Chapter IV (IT outsourcing)**. RBI/DOR/2025-26/363, DOR.ORG.REC.No.282/21-04-158/2025-26, dated **28 Nov 2025**, in force immediately. Existing IT outsourcing agreements had to comply at renewal or by 10 Apr 2026, whichever was earlier. https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12941
- **Repealed for NBFCs:** Master Direction on Outsourcing of Information Technology Services, RBI/2023-24/102, 10 Apr 2023 (effective 1 Oct 2023). https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12486. Para 100 of the 2025 Directions repeals it (circular DOR.RRC.REC.302/33-01-010/2025-26, 28 Nov 2025).
- **Applicability:** Chapter IV applies to Middle Layer and above (para 3(2)), and only to material IT outsourcing (para 5(1)).
- Banks have a parallel "Commercial Banks – Managing Risks in Outsourcing" Direction. That text was not checked.

Why it matters to FinShield: a lender that buys FinShield, or runs on AWS, is outsourcing IT. These rules apply to the lender's relationship with **us** as a vendor, and to the lender's cloud provider.

Checked against rbi.org.in on 2026-11-20 by M8.

| Clause ID | Plain summary | Why it matters to a digital lender | FinShield control / position | Source | Verified |
|---|---|---|---|---|---|
| Para 9; para 17 | Outsourcing does not reduce the NBFC's obligations. The Board and senior management keep ultimate responsibility and control. | The lender cannot hand breach accountability to a vendor. | FinShield keeps the human decision (Approve/Release) with the lender | id=12941 | yes |
| Paras 71–72 | Do due diligence on IT service providers before engaging them. | Buyers will diligence FinShield itself. | Architecture, evidence design and this compliance map serve as the diligence pack | id=12941 | yes |
| Para 61 | Service providers report cyber incidents to the NBFC **without undue delay**, so the NBFC can report to RBI **within six hours of detection by the service provider**. | The 6-hour clock can start at the vendor's detection, not the lender's. | RBI timer from `detected_at` (FinShield's own detection) | id=12941 | yes |
| Para 74(ii); para 81 | The NBFC and RBI need access to the provider's data, books, records, logs, alerts and premises. Access must be unrestricted and effective. | Logs must be available to the lender and RBI on demand. | Evidence export from the lender's own AWS account, nothing held only by the vendor | id=12941 | yes |
| Para 74(i); para 76; para 77 | Audit rights over the provider, regular audits, pooled audits allowed. | Audit-ready evidence. | Hash-chained evidence with Verify | id=12941 | yes |
| Para 74(vi) | Store data only in India, where existing regulations require it. | Conditional localisation. Combined with Digital Lending para 14(4), lending data must stay in India. | ap-south-1 only | id=12941 | yes |
| Para 69(iii) | The NBFC must immediately notify RBI of a security breach or leak of confidential customer information at the provider. | Another reporting trigger, with no fixed hours ("immediately"). | RBI incident draft | id=12941 | yes |
| Para 67 | Manage concentration risk across service providers. | Context for single-cloud dependence. | n/a | id=12941 | yes |
| Paras 96–97 | Cloud use: MFA for cloud applications (97(viii)(d)), integration of cloud provider logs into the NBFC's SOC (97(xi)), cloud exit plan (97(xvi)). | Direct match to FinShield's CloudTrail-into-detection design. | CloudTrail → EventBridge → detection | id=12941 | yes |
| Paras 84–88 | Exit strategy. No erasing, purging or altering data during the transition (para 87). | Evidence must survive a vendor change. | Evidence stays in the lender's S3 Object Lock bucket | id=12941 | yes |
