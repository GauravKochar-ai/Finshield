# RBI IT governance and cyber security directions for NBFCs

## Status: the 2023 Master Direction is repealed for NBFCs, so cite the 2026 Directions

- **Current:** Reserve Bank of India (Non-Banking Financial Companies – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026. RBI/DoS/2026-27/461, DoS.CO.CSITEG.55/31.01.015/2026-27, dated **31 July 2026**, in force immediately (para 2). https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13592
- **Repealed for NBFCs:** Master Direction – Information Technology Governance, Risk, Controls and Assurance Practices, RBI/2023-24/107, 7 Nov 2023 (effective 1 Apr 2024). https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12562. Para 155 of the 2026 Directions repeals the earlier IT framework and IT governance instructions for NBFCs (circular DoS.CO.PPG.66/11.01.005/2026-27, 31 Jul 2026).
- **Applicability is tiered:** Chapter III covers Base Layer below ₹500 cr and CICs. Chapter IV covers Base Layer at or above ₹500 cr. Chapter V covers Middle Layer and above (excluding CICs). HFCs report incidents to NHB, not RBI.
- Banks, AIFIs and CICs have their own parallel 2026 Directions. Those texts were not checked.

Checked against rbi.org.in on 2026-11-20 by M8. Para numbers below are from the 2026 NBFC Directions, Chapter V unless noted.

| Clause ID | Plain summary | Why it matters to a digital lender | FinShield control | Source | Verified |
|---|---|---|---|---|---|
| Para 141 (Ch. V); para 28 (Ch. IV) | Report cyber incidents to RBI **within six hours of detection** on the DAKSH platform, and proactively notify CERT-In. | This is the RBI 6-hour clock on the Overview. | RBI 6 h readiness timer from `detected_at`; `RBI_INCIDENT` draft | id=13592 | yes |
| Paras 139–146 (Ch. V) | Incident response and management, with "forensic analysis, if necessary" (para 140). | The lender needs a documented incident playbook and the facts to analyse. | Step Functions incident workflow; evidence chain | id=13592 | yes |
| Para 84 (Ch. V); para 25 (Ch. IV) | Keep a Cyber Crisis Management Plan covering detection, response, recovery and containment. | FinShield's playbook is an operational part of the CCMP. | Detect → contain → approve → release workflow | id=13592 | yes |
| Paras 109–111 | Keep audit trails, and monitor audit trails and system logs regularly to detect, understand or recover from unauthorised activity. Audit trails serve as forensic evidence (para 110). | Continuous monitoring of who touched KYC. | CloudTrail data events, detection, hash-chained evidence | id=13592 | yes |
| Para 82(4) | The CISO's office manages and monitors the Security Operations Centre. | FinShield gives the SOC a detection and response layer for KYC data. | Overview, alerts, SNS email | id=13592 | yes |
| Paras 113–114 | Grant access only on valid business need. Supervise elevated entitlements closely, log their activity and review it periodically. | Emergency or admin roles are the main insider-risk path. | Signal S3 (emergency role without approval), approvals (E2), self-approval ignored (E3) | id=13592 | yes |
| Para 115 | Based on risk assessment, use two-factor or multi-factor authentication for privileged users of critical systems and for critical activities. | MFA is required for privileged users, scoped to critical systems and risk assessment. It is not universal. | Signal S5 (MFA fatigue), Config rule `mfa-enabled-for-iam-console-access` | id=13592 | yes |
| Paras 70–73, 77, 81–82 | Board-level IT Strategy Committee, Information Security Committee and a CISO with an independent reporting line. | Gives the buyer: the CISO / Security Head approves containment. | `SecurityHead` approval step | id=13592 | yes |

## Do not claim

- **DLP:** no data-leak-prevention requirement appears in either the 2023 MD or the 2026 Directions.
- **Log retention period:** neither text sets one. Use CERT-In Direction (iv) (180 days) and DPDP Rules r.6(1)(e) / r.8(3) (1 year) instead.
- **A 6-hour rule in the 2023 IT Governance MD:** it had none. Para 27(d) only said to notify "as per regulatory requirements".
- **"PAM":** the texts do not use the term. Say "supervision of privileged access".
