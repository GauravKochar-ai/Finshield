# FinShield AI: 6-minute demo script

Owner: M8 (Arvind). Status: DRAFT. Times not yet rehearsed against the live app.

Screen and button names follow `.kiro/specs/m6-frontend` and `contract/openapi.yaml`. The web app is not built yet, so every label marked **[confirm label]** must be checked with M6 once the screen exists. Numbers come from the SC-01 fixture (`contract/fixtures/api_alert_detail.json`).

## Before you start (T-10 min)

1. `make scenario` is not used live. Run a clean reset: Simulator → **Reset** [confirm label] (clears Alerts and Counters for scenario users).
2. Sign in on two browser tabs: Tab A as `Admin` (Simulator, Tamper demo), Tab B as `SecurityHead` (Approve, Release).
3. Run **Accuracy → Run all** once in advance so the 11/11 result is cached. Do not re-run it live.
4. Open in background tabs: the IAM console on `finshield-dev-demo-ops-admin` and the S3 bucket policy of `finshield-dev-kyc-docs`.
5. Check SSM `/finshield/dev/containment_mode`. The story says LIVE for sessions, keys and bucket deny and DRY_RUN for DNS block.
6. Have the backup video open, paused at 0:00, on the second screen.

Never click during the demo: **Accuracy → Run all** (it replays all scenarios and floods Overview), **GuardDuty sample**, **Reset** after SC-01 has run.

## Script

| Time | Step | Click | Say |
|---|---|---|---|
| 0:00 | **Problem** (30 s) | Tab A, **Overview**. Point at posture score, compliance tiles, privacy tiles. | "A digital lender holds KYC for every borrower. One insider leak starts three clocks: RBI 6 hours, CERT-In 6 hours, and a detailed report to the Data Protection Board in 72 hours. Today most lenders find out days later. This is FinShield's view of one lender's AWS account: posture score, compliance status and privacy risks." |
| 0:30 | **Attack** (60 s) | **Simulator** → **SC-01** [confirm label]. Go back to **Overview** and wait for the red CRITICAL row (under 60 s). Point at the three deadline countdowns. | "An ops admin assumes the KYC emergency role at 23:40 from a new device in a second city, pulls 212 KYC files and uploads them to an outside file share. We replay it onto the real EventBridge bus... there: CRITICAL, score 96, under a minute. The RBI, CERT-In and Board countdowns started from the moment we detected it." |
| 1:30 | **Investigate** (60 s) | Click the alert row → **Alert detail**. Hover each score-bar segment. Scroll to **Timeline**, then the **AI card** with clause citations. | "The score is broken down by signal: 106 times normal download volume for 40 points, emergency role with no approval for 20, external upload 3 minutes later for 15, new device and 1,180 km between cities for 11, off-hours for 10. That's 96. The timeline shows the events behind it. The AI card explains it in plain words and cites the clauses. **Code computed every number; AI only wrote the words.**" |
| 2:30 | **Respond** (60 s) | On Alert detail, **Containment** panel: four ticks with timestamps. Switch briefly to the IAM tab (inline deny) or bucket policy (`FinShieldDeny…`). Tab B: **Approve** → reason "Confirmed insider exfiltration" → status **LOCKED**. Then **Release** → status **RELEASED**. | "Containment ran before the AI finished: sessions revoked, access keys off, a deny on the KYC bucket, DNS block in dry run. Here it is in IAM, a real policy. A human still decides: as Security Head I approve, and the account is locked. Every action is reversible: Release removes each deny." |
| 3:30 | **Evidence** (45 s) | **Evidence** tab → **Verify** (green). Tab A: **Tamper demo** (red at the edited entry's seq). **Reports** tab → **CERT-In**. | "Every step was written to a hash-chained evidence log, sealed into S3 Object Lock. Verify: green. Now we edit one entry in a copy: the chain breaks at exactly that entry. And here's the CERT-In draft, ready for a human to review and file inside the 6 hours." |
| 4:15 | **Breadth** (45 s) | **Accuracy** panel (cached run): 11/11, 0 false alerts. Click **SC-07** row, then **SC-03** row. | "One scenario isn't a product. We have 11 scenarios plus 7 normal days: 11 out of 11 correct, zero false alerts. SC-07: a marketing user reads KYC of 40 customers who only consented to loan processing, caught by the consent ledger. SC-03: an auditor pulls 90 files under an approved 100-file ticket and stays quiet. Quiet when it should be quiet matters as much as loud." |
| 5:00 | **Architecture and compliance** (45 s) | **Architecture** page (or `docs/architecture.png` on the slide). Then **Compliance map** screen. | "All serverless on AWS in Mumbai, ap-south-1, so data stays in India. CloudTrail, Config and GuardDuty feed EventBridge; Lambda scores; Step Functions responds; Bedrock with a Guardrail writes the words; evidence goes to S3 Object Lock. Built spec-first in Kiro. Each control maps to an obligation, as DPDP-aligned readiness and controls, not a certification." |
| 5:45 | **Close** (15 s) | Last slide. | "FinShield is for NBFCs, digital lenders and their lending service partners. It costs about [Ajay: cost per million events] per million events to run. Thank you." |

## Fallbacks

| If | Then |
|---|---|
| CloudTrail is slow (real mode) | Do not use the real-mode run in the main demo. Keep it as an optional second demo after Q&A starts. |
| Bedrock is down or slow (> 8 s) | The AI card shows **FALLBACK**. Say: "Bedrock is unavailable, so the AI card shows the template text. Every number and the response are unaffected, because code makes the decisions." Continue. |
| SC-01 alert has not appeared by 1:15 | Play the backup video from the Attack step. |
| Anything else fails | Play the backup video from the same step, then return to live at the next step if the app recovers. |

## Rehearsal log

| Date | Run by | Clean reset | Total time | Failed steps |
|---|---|---|---|---|
| not yet rehearsed | | | | |
