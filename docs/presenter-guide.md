# FinShield AI: presenter guide (what is live, how to demo it, how to explain it)

Frozen build: `main` at 7a93878, stack `finshield-dev` in ap-south-1. `scripts/live_check.py` passed 31 of 31 at 17:45 IST
on 20 Nov 2026. All data is synthetic and marked SAMPLE.

## 1. Links and logins

| App | Link | Sign in as | Use it for |
| --- | --- | --- | --- |
| Admin console | https://djr2m04eyaclp.cloudfront.net | `securityhead@finshield.example` | Alerts, approve, release, evidence, reports, compliance |
| Simulator | https://d1rrgk7c2l6zwn.cloudfront.net | `admin@finshield.example` | Run the 5 demo scenarios, reset, GuardDuty sample |

Other console logins: `analyst@`, `compliancehead@`, `auditor@finshield.example`. The demo password is in `scripts/seed.sh`.

## 2. Before the demo (T-10 min)

1. Two browser windows: A = Simulator as admin, B = Admin console as securityhead.
2. Simulator: **Reset environment** once. Do not reset again after SC-01 has run.
3. Admin console as admin: open **Detection accuracy** and check the last run shows 11/11 and 0 false alerts. Do not re-run it live (it replays every scenario and floods the Overview).
4. Have the deck open and the backup video paused at 0:00.
5. Never click live: Run accuracy, GuardDuty sample, Reset (after SC-01).

## 3. Six-minute flow (live build)

| Time | Step | Do | Say |
| --- | --- | --- | --- |
| 0:00 | Problem | B: Overview (posture score, compliance and privacy tiles) | One insider KYC leak starts three clocks: RBI 6 h, CERT-In 6 h, Data Protection Board detailed report 72 h. Most lenders find out days later. |
| 0:30 | Attack | A: **Run** on SC-01. B: the CRITICAL alert appears in about 5 s | An ops admin assumes the emergency role at 23:40 from a new device in a second city, pulls 212 KYC files and uploads them outside. One alert, score 96, deadlines already counting. |
| 1:30 | Investigate | B: open the alert. Score bar by signal, timeline, AI card | 212 downloads vs a usual 2 = 106x (40), emergency role without approval (20), external upload (15), new device and second city (11), off-hours (10) = 96. **Code computed every number; Bedrock only wrote the words**, and its text is rejected if it adds a number. |
| 2:30 | Respond | B: Containment panel (4 actions), wait for AWAITING_APPROVAL, **Approve** → LOCKED, then **Release** → RELEASED | Containment ran in seconds, before the AI finished: revoke sessions, bucket deny, DNS block, keys (not applicable to a role). It runs in DRY_RUN here and records the exact IAM and S3 call it would make. A human approves the lock-down; Release undoes everything. |
| 3:30 | Evidence | B: Audit evidence → **Verify** (green), **Tamper demo** (red at one entry, needs admin), Reports → CERT-In draft | Every step is hash-chained and exported to S3 Object Lock for a year. Edit one entry in a copy and the chain breaks exactly there. The 4 regulator and customer drafts are written by Bedrock from the computed facts. |
| 4:15 | Breadth | B: Detection accuracy | 11 scenarios plus 7 normal days: 11 of 11 correct, 0 false alerts. SC-07 consent mismatch caught; SC-03 auditor under a ticket stays quiet. |
| 5:00 | Architecture | Deck: architecture slide; B: Compliance | Serverless on AWS in Mumbai; data and the AI model stay in India. DPDP-aligned readiness and controls; SOC 2-aligned and ISO 27001-aligned controls. |
| 5:45 | Close | Deck: business case | For NBFCs, digital lenders and their lending service partners. |

Fallbacks: alert not visible by 1:15 → backup video from the Attack step. AI card shows FALLBACK → "Bedrock was slow, so the template from the same facts is shown; decisions are unaffected." Anything else → backup video from that step.

## 4. How it works (one paragraph per layer)

- **Sources:** the simulator (or CloudTrail, GuardDuty, AWS Config) sends events to the EventBridge bus `finshield-dev-bus`.
- **Detect:** `normalizer` turns every source into one event format and drops duplicates; `detection` keeps 15-minute and daily counters, compares them with each user's normal pattern, scores 11 warning signs and 3 exceptions from `contract/config.json`, and keeps one open alert per user per hour.
- **Respond:** an Alert Raised event starts Step Functions. It writes evidence, sets the three deadlines, runs containment and the Bedrock explanation in parallel, drafts 4 reports, emails the Security Head, waits 30 minutes for approval and escalates to the Compliance Head.
- **Record:** every step is appended to a SHA-256 hash chain in DynamoDB that no role can edit, and exported to S3 Object Lock.
- **Serve:** three static Next.js apps on CloudFront; API Gateway with a Cognito JWT authorizer; five role groups.

Full design: `docs/hld.md`. Services: CloudFront, S3, Cognito, API Gateway, EventBridge, Lambda (23), Step Functions, DynamoDB (13 tables), Bedrock (Mistral Large 3) and Guardrails, CloudTrail, AWS Config, GuardDuty, IAM, SNS, SSM Parameter Store, Secrets Manager, KMS, CloudWatch, Route 53 Resolver DNS Firewall (optional).

## 4b. The 5 demo scenarios (all raise an alert you can open in the admin console)

| ID | Risk | Story | Expected | Signs |
| --- | --- | --- | --- | --- |
| SC-01 | KYC exfiltration (mandatory demo) | Ops admin, 23:40, emergency role from a new device and second city, 212 KYC files, external upload | CRITICAL 96 | S1 40, S3 20, S4 15, S5 11, S6 10 |
| SC-06 | Compromised privileged credentials | Cloud admin: 6 MFA pushes, login 1,400 km away, emergency role, StopLogging | CRITICAL 100 | S5, S3, S8 (instant 100) |
| SC-07 | Consent and purpose violation | Marketing user reads KYC of 40 customers who consented only to loan processing | HIGH 70 | S9 30, S7 40 |
| SC-08 | Abnormal transaction | Bank account changed from a new device, then Rs 4.8 lakh disbursed to it at 01:40 | HIGH 65 | S10 50, S6 10, S5 5 |
| SC-09 | Cloud misconfiguration | KYC bucket made public; AWS Config marks it non-compliant | MEDIUM 45 | S11 45 |

## 5. Likely judge questions

| Question | Answer |
| --- | --- |
| How do you stop the AI hallucinating? | It never decides. Code computes the score, severity and counts. Bedrock gets masked facts, writes text, and the output is rejected if a number or clause is not in the facts; a template from the same facts replaces it. |
| Does customer data leave India? | No. Everything runs in ap-south-1, including the Bedrock model (Mistral Large 3 runs in-region). No names, Aadhaar or PAN are sent to the model, and a Guardrail filters input and output. |
| Is containment real? | Each action is a Lambda that calls IAM or S3. The demo runs in DRY_RUN and records the exact call; LIVE is one SSM switch and only ever touches the demo principals. Release reverses it. |
| Can someone change the evidence? | No role has update or delete on the Evidence table. Each entry hashes the previous one, so any edit breaks the chain at that entry; exports are in S3 Object Lock for a year. |
| False positives? | Measured: 0 alerts on 7 normal days; approved jobs and tickets cap the score (SC-02, SC-03). |
| Are you DPDP compliant? | We say DPDP-aligned readiness and controls. Compliance is the lender's obligation; FinShield produces the evidence and timers. No HIPAA claim (US health data, not relevant). |

## 6. Known limits (say them before judges find them)

- Containment runs in DRY_RUN in this demo. Deactivate keys is not applicable to the SC-01 role principal.
- The simulator shows 5 demo scenarios. The Accuracy panel still replays all 11 scenarios plus 7 normal days.
- The FinLend Ops staff app is dropped from this build (code kept on branches `feat/user-web` and `wip/feat-002-staff-api`).
- Real mode through CloudTrail works but adds minutes of delivery delay, so it is not in the main demo.
