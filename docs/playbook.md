# FinShield AI — Build Playbook (Kiro + SAM + Team Prompts)

Nov 20, 2026 · @Keshav Sharma

## How to use this playbook

Every member builds against one shared contract (Section 2), so the modules plug together at the end without rework. Each member pastes their own Start prompt into Kiro, and pastes their Validate prompt at every checkpoint, whatever stage they are at.

**Rules for everyone**

1. The `contract/` folder and `.kiro/steering/` win over anything else. If your module needs a contract change, ask the integration lead (M1). Never change it silently.
2. Every Lambda must be testable alone with a fixture from `contract/fixtures/`. Every UI screen must run on mocks first (`NEXT_PUBLIC_USE_MOCKS=true`).
3. Commit to `main` in small pieces, at least every 45 minutes. Pull before every checkpoint.
4. Code does the numbers, AI does the words. No module lets Bedrock decide a score, a severity or a count.
5. The wording is "DPDP-aligned readiness and controls". Never "DPDP compliant", and never "Consent Manager".

**Modules and owners** (with fewer than 8 people, merge M1+M8, M3+M7 and M4+M5)

| ID | Module | Owns | Needs from | Gives to |
| --- | --- | --- | --- | --- |
| M1 | Integration lead, Kiro specs and steering | `.kiro/`, `contract/`, `Makefile`, checkpoint runs | Everyone | Everyone |
| M2 | Infrastructure (SAM) | `infra/template.yaml`, IAM, CloudTrail, Config, GuardDuty, Cognito, hosting, `scripts/` | M1 contract | Stack outputs, `.env` for all |
| M3 | Detection pipeline | normalizer, detection, baseline, exceptions, incident dedup | M2 tables and bus, M7 seed data | Alerts in DynamoDB plus `finshield.alert.raised` events |
| M4 | Response and evidence | Step Functions, containment, approvals, release, deadlines, evidence seal, SNS | M3 alerts, M5 AI Lambdas | Incident workflow, evidence chain |
| M5 | AI layer | Bedrock explain, reports, Guardrails, Knowledge Base, KYC image labelling, Ask FinShield chat | M8 regulation texts, M3 alert shape | AI JSON on each alert, 4 report drafts |
| M6 | Frontend (Next.js admin portal) | `web/` | Contract fixtures, then M7 API | Dashboard, demo buttons |
| M7 | Data, simulator, API and accuracy | seed data, 10 scenarios, simulator, test runner, API handlers | M2 tables, M3 scoring rules | Seeded DynamoDB, replayable scenarios, REST API |
| M8 | Compliance, pitch and demo | `docs/compliance-map.md`, regulation summaries, deck, demo script, business case, backup video | Everyone's screenshots | Deck, regulation texts for M5 |

**Build order and checkpoints** (T0 = when the Start prompts begin; M1 runs each checkpoint with the Integration check prompt in Section 5)

| Checkpoint | Time | Passes when |
| --- | --- | --- |
| CP1 Skeleton | T0 + 1h | `contract/` committed; `sam deploy` creates the bus, tables, buckets and a hello API; the web app runs on mocks; seed data loaded |
| CP2 First detection | T0 + 2h30 | `make scenario SC=SC-01` produces exactly one alert scoring 96, Critical, in under 60 s |
| CP3 Full incident | T0 + 4h | SC-01 runs Step Functions; containment works (LIVE or DRY\_RUN); evidence chain verifies; AI card filled; web app on the live API with Cognito sign-in |
| CP4 All scenarios | T0 + 5h15 | All 10 scenarios match their expected level on the Accuracy panel; 0 alerts on normal days; real-mode CloudTrail run works once |
| CP5 Freeze | T0 + 6h | No new features. Rehearse the demo twice, record the backup video, finish the deck |

Build order inside each module: the P0 items carry the mandatory demo; the P1 items carry the other scenarios and judging points; the P2 items are depth. Nothing is cut, but nobody starts P1 until their P0 passes CP2 or CP3.

## The integration contract

This section is what makes the parts plug together. M1 copies it into `contract/` and `.kiro/steering/contract.md` before anyone writes code.

### Repo layout

```
finshield/
  .kiro/steering/        product.md tech.md structure.md contract.md compliance.md
  .kiro/specs/           one folder per module (M1 generates)
  contract/
    config.json          scoring points, thresholds, deadlines (single source of truth)
    openapi.yaml         REST API
    schemas/             event, alert, ai_explanation, evidence_entry, report (JSON Schema)
    fixtures/            one example per schema + one per API response
  infra/template.yaml    SAM, the only template; samconfig.toml (stage=dev)
  backend/
    shared/python/finshield/   schema.py ddb.py config.py evidence.py events.py bedrock.py (Lambda layer)
    functions/<name>/app.py    one folder per Lambda, handler = app.handler
    statemachines/incident.asl.json
    tests/                      pytest, one file per function
  simulator/seed/  simulator/scenarios/SC-01.json ... SC-10.json
  web/                   existing Next.js admin portal (static export)
  docs/                  compliance-map.md, demo-script.md, architecture.png
  scripts/               write-env.sh seed.sh scenario.sh smoke.sh
  Makefile
```

### Naming and global settings

- Region `ap-south-1` (change only if the sandbox forces another; then update `samconfig.toml` and the steering file together).
- Every resource is named `finshield-${Stage}-<name>`; stage `dev`. Tag `project=finshield`.
- Lambdas: Python 3.12, arm64, 512 MB, 30 s timeout (AI ones 60 s), structured JSON logs with `alert_id` and `event_id` when present.
- Runtime settings live in SSM under `/finshield/dev/`: `containment_mode` (LIVE or DRY\_RUN), `bedrock_model_id`, `guardrail_id`, `guardrail_version`, `kb_id` (empty means put regulation text in the prompt), `alert_email`.
- Frontend env, written by `scripts/write-env.sh` from stack outputs into `web/.env.local`: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_REGION`, `NEXT_PUBLIC_USER_POOL_ID`, `NEXT_PUBLIC_USER_POOL_CLIENT_ID`, `NEXT_PUBLIC_USE_MOCKS`.

### Event flow on EventBridge

One custom bus `finshield-dev-bus`. Every hop is an event, so each module can be tested with `aws events put-events` alone.

| Source | detail-type | Detail | Producer | Consumer |
| --- | --- | --- | --- | --- |
| `finshield.simulator`, `finshield.app` | `Raw Activity` | unified event, `source` field filled | M7 simulator, app | normalizer |
| `aws.s3`, `aws.signin`, `aws.sts`, `aws.cloudtrail` | `AWS API Call via CloudTrail`, `AWS Console Sign In via CloudTrail` | CloudTrail record | default bus rule forwards to our bus (M2) | normalizer |
| `aws.guardduty` | `GuardDuty Finding` | finding | forwarded (M2) | normalizer |
| `aws.config` | `Config Rules Compliance Change` | rule result | forwarded (M2) | normalizer (also writes `Posture`) |
| `finshield.normalizer` | `Normalized Event` | unified event | M3 | detection |
| `finshield.detection` | `Alert Raised` | `{alert_id, severity, previous_severity, score, user_id, principal_arn, detected_at}` | M3 | Step Functions (M4) |
| `finshield.response` | `Incident Updated` | `{alert_id, status, step}` | M4 | (dashboard polling only) |

### Unified event (every source becomes this)

```json
{"event_id":"evt-8f21","ts":"2026-11-20T23:48:12+05:30","source":"simulator|cloudtrail|guardduty|config|app",
 "scenario_id":"SC-01","is_replay":true,"user_id":"u-017","principal_arn":"arn:aws:iam::<acct>:role/finshield-dev-demo-ops-admin",
 "action":"LOGIN|MFA_PUSH|ASSUME_ROLE|VIEW|DOWNLOAD|PRESIGN|UPLOAD_EXTERNAL|LOGGING_CHANGE|BANK_ACCOUNT_CHANGE|DISBURSE|CONFIG_NONCOMPLIANT|GUARDDUTY_FINDING|KYC_FILE_UPLOADED",
 "object_id":"KYC-PAN-0042","customer_id":"C-10442","data_class":"KYC|FINANCIAL|PII|NONE","purpose":"loan_processing|collections|marketing|audit|registry_upload",
 "bytes":2150000,"amount_inr":null,"ip":"49.36.x.x","city":"Pune","device_id":"d-new-77","role":"KYC-Emergency",
 "destination":"files.example-share.com","resource_arn":null,"raw_ref":"s3://finshield-dev-raw-events/..."}
```

Required: `event_id`, `ts` (ISO 8601 with +05:30), `source`, `user_id`, `action`. Everything else may be null.

### Scoring (in `contract/config.json`; detection reads it, the Rules screen shows it)

| Code | Sign | Points |
| --- | --- | --- |
| S1 | Volume spike: 15-min downloads ÷ max(user p95, team p95, 5): ≥100× 40, ≥20× 30, ≥5× 20, ≥3× 10. PRESIGN over 50 counts as downloads | up to 40 |
| S2 | Slow leak: today > 5× daily average and > 200; only if higher than S1 | 25 |
| S3 | Emergency role assumed with no covering approval; service account outside its job window | 20 |
| S4 | UPLOAD\_EXTERNAL to a non-allowlisted destination: ≥100 MB or within 60 min of KYC downloads 15, else 8 | up to 15 |
| S5 | Risky login: new device 5, ≥5 MFA pushes in 2 min 6, two cities >500 km apart within 1 h 11 | max 11 |
| S6 | Off-hours by more than 1 h | 10 |
| S7 | ≥20 customers not assigned to the user or their partner within 1 h | 40 |
| S8 | Logging tampered (StopLogging, DeleteTrail, bucket logging off) | instant 100 |
| S9 | Purpose mismatch: KYC/PII read for a purpose the customer has not consented to (≥10 customers in 1 h) | 30 |
| S10 | Abnormal disbursement: DISBURSE to an account changed under 24 h ago 30, amount > 3× user's p95 20 | up to 50 |
| S11 | Sensitive resource misconfigured: Config non-compliant on a `data_class=KYC` resource 45, other 20 | up to 45 |

Exceptions: E1 scheduled job caps the score at 30; E2 approved ticket caps at 30, void if files exceed it by more than 20% (then +10); E3 an approval by the actor is ignored. Levels: **80+ Critical, 60–79 High, 40–59 Medium, below 40 logged only.** Score capped at 100.

**Incident dedup (required):** one open alert per `user_id` per 60-minute window. Detection updates the existing alert with a conditional write and emits `Alert Raised` only when severity goes up. Step Functions execution name = `<alert_id>-<severity>`, so a duplicate start fails harmlessly.

### DynamoDB tables (`finshield-dev-<Table>`, on-demand, PITR on, KMS)

| Table | PK / SK | GSIs | Main fields |
| --- | --- | --- | --- |
| Users | user\_id | — | name\_pseudo, team, role, is\_admin, is\_service, office\_start, office\_end, home\_city, devices\[\], partner\_id, iam\_principal\_arn |
| Customers | customer\_id | partner\_id | city, aadhaar\_last4, pan\_fake, loan\_id, assigned\_agent, partner\_id, bank\_account\_hash, bank\_account\_changed\_at |
| KycFiles | file\_id | customer\_id | doc\_type, s3\_key, size\_kb, ai\_label, unmasked\_aadhaar\_flag |
| Events | user\_id / ts#event\_id | scenario\_id + ts | unified event |
| Counters | user\_id#window / bucket\_start | — | downloads, distinct\_customers, bytes, mfa\_pushes, presigns |
| Baselines | subject\_id | — | p95\_15min, avg\_daily, usual\_hours, cities\[\], devices\[\], p95\_disburse\_inr |
| Approvals | approval\_id | subject\_id | type, subject\_id, max\_files, data\_class, valid\_from, valid\_to, approver\_id, job\_id |
| Consent | customer\_id | — | purposes\[\], given\_at, withdrawn\[\], notice\_version |
| Alerts | alert\_id | user\_id + detected\_at; status + detected\_at | see alert shape below |
| Evidence | alert\_id / seq (number) | — | ts, type, actor, payload, prev\_hash, hash |
| Reports | alert\_id / report\_type | — | status, body\_md, model\_id, generated\_at |
| Posture | control\_id | — | source (config, guardduty, internal), status, resource\_arn, last\_evaluated |
| AccuracyRuns | run\_id / scenario\_id | — | expected\_level, actual\_level, expected\_score, actual\_score, pass, time\_to\_alert\_ms |

S3 buckets: `finshield-dev-kyc-docs` (CloudTrail data events on, KMS, private), `finshield-dev-raw-events` (1-year lifecycle), `finshield-dev-rules` (regulation summaries), `finshield-dev-evidence` (Object Lock compliance mode, 1 year; must be created with Object Lock on), `finshield-dev-web` (static site behind CloudFront).

### Alert shape (`contract/schemas/alert.schema.json`)

```json
{"alert_id":"ALR-20261120-0007","user_id":"u-017","principal_arn":"arn:...","score":96,"severity":"CRITICAL",
 "status":"OPEN|CONTAINED|AWAITING_APPROVAL|LOCKED|RELEASED|CLOSED",
 "signals":[{"code":"S1","points":40,"facts":{"downloads_15m":212,"baseline_p95":2,"ratio":106}}],
 "exceptions_applied":[],"customers_affected":198,"data_classes":["KYC"],"event_ids":["evt-..."],
 "detected_at":"2026-11-20T23:49:02+05:30","window_start":"...","scenario_id":"SC-01",
 "deadlines":[{"body":"RBI","due_at":"..."},{"body":"CERT-In","due_at":"..."},{"body":"DPB","due_at":"..."}],
 "containment":[{"action":"REVOKE_SESSIONS","mode":"LIVE","result":"OK","at":"..."}],
 "ai":{ ... ai_explanation ... },"ai_status":"PENDING|OK|FALLBACK","execution_arn":"arn:..."}
```

Deadlines from `detected_at`: RBI +6 h, CERT-In +6 h, Data Protection Board detailed report +72 h (all in `config.json`; M8 confirms the wording).

### AI explanation shape (`ai_explanation.schema.json`)

```json
{"headline":"Privileged ops account bulk-exported 212 KYC files off-hours and sent them to an external share",
 "summary":"<= 80 words","why_unusual":["212 downloads vs usual 2 per 15 min (106x)"],
 "rules_affected":[{"regulation":"DPDP Act 2023","clause":"Sec 8(5)","why":"..."}],
 "root_cause_hypotheses":["..."],"affected_assets":["finshield-dev-kyc-docs"],
 "recommended_actions":["..."],"confidence":"high|medium|low","confidence_reason":"...",
 "numbers_used":{"downloads_15m":212,"customers_affected":198,"score":96}}
```

`numbers_used` must equal the alert's computed facts or the output is rejected and the template fallback is used (`ai_status=FALLBACK`). Input to Bedrock is masked JSON only. Guardrails run on input and output. Temperature 0.

### Step Functions `finshield-dev-incident` (Standard)

Input = the `Alert Raised` detail. Order: write evidence `ALERT_RAISED` → set deadlines → branch on severity. **Critical:** Parallel \[containment: revoke sessions, deactivate keys, bucket deny, DNS block — each a Lambda that writes its own evidence\] and \[AI explain, 8 s budget, then fallback\] → invoke AI reports asynchronously → SNS email + approval card with `waitForTaskToken` (30 min, on timeout escalate to compliance head, wait again) → APPROVE: quarantine policy (console off), status LOCKED; REJECT: record reason, containment stays → evidence `CLOSED_STEP` → export evidence to S3. **High:** notify + AI + step-up MFA flag. **Medium:** AI + status OPEN.

Every containment Lambda takes `{alert_id, principal_arn, mode}` and returns `{action, mode, result, detail}`. In DRY\_RUN it writes the exact IAM/S3 call it would make into evidence. `release` undoes all four (reversibility demo).

### Evidence entry and seal

`hash_n = SHA-256(hash_(n-1) + canonical_json(entry_n without hash))`; entry 1 chains from `GENESIS:<alert_id>`. `canonical_json` = sorted keys, separators `(',', ':')`, UTF-8. Only `finshield.evidence.append()` in the shared layer writes this table (conditional put on `seq`). No role has UpdateItem or DeleteItem on it.

### REST API (HTTP API, Cognito JWT authorizer, prefix `/v1`, envelope `{"data":...,"error":null}`)

| Method and path | Returns | Groups |
| --- | --- | --- |
| GET /posture | posture score 0–100, alerts by severity, Config results, consent risks, deadlines due soon | all |
| GET /alerts?status=&severity= | alert list | all |
| GET /alerts/{id} | alert with AI, signals, deadlines, containment | all |
| GET /alerts/{id}/timeline | events that built the alert | all |
| GET /alerts/{id}/evidence | evidence chain | all |
| POST /alerts/{id}/evidence/verify | `{valid, broken_at_seq}` | all |
| POST /alerts/{id}/evidence/tamper-demo | verify result on a tampered copy | Admin |
| POST /alerts/{id}/decision | `{decision: APPROVE or REJECT, reason}` → sends the task token | SecurityHead, ComplianceHead |
| POST /alerts/{id}/release | undoes containment | SecurityHead |
| GET /alerts/{id}/reports | 4 report drafts | all |
| POST /alerts/{id}/ask | `{question}` → Ask FinShield answer | Analyst and up |
| GET /users/{id} | profile, baseline, recent risk | all |
| GET /rules | contents of config.json | all |
| GET /compliance | control map with status per control | all |
| GET /privacy | consent risks, unmasked Aadhaar files, purpose mismatches | all |
| GET /approvals, POST /approvals | tickets and scheduled jobs (E1/E2) | SecurityHead |
| POST /simulate | `{scenario_id}` or `{guardduty_sample:true}` | Admin |
| POST /accuracy/run, GET /accuracy | run all scenarios; latest results | Admin |

Cognito groups: `Analyst`, `SecurityHead`, `ComplianceHead`, `Auditor` (read-only), `Admin`. Seed one user per group with a known demo password.

## Kiro steering files and the master spin-up prompt

M1 creates these five steering files first; every member's Kiro then reads them automatically. Each file starts with the front matter `---\ninclusion: always\n---`. Check the Kiro docs if your version uses different inclusion keys.

The five files (`product.md`, `tech.md`, `structure.md`, `contract.md`, `compliance.md`) live in `.kiro/steering/` and are the source of truth for their content. `structure.md` also says: "Put new Lambdas in backend/functions/\<name>/ and register them in infra/template.yaml in the same change."

### Master spin-up prompt (M1 runs this once, right now)

```text
You are setting up the FinShield AI monorepo. The Next.js admin portal already exists; move or keep it in web/.
Read every file in .kiro/steering first.

1. Create the repo layout from structure.md. Create contract/ with:
   - config.json holding scoring signs S1-S11, exceptions E1-E3, severity thresholds (80/60/40), deadlines (RBI 6h, CERT-In 6h, DPB 72h), incident window 60 min.
   - JSON Schemas for event, alert, ai_explanation, evidence_entry, report, matching the shapes in contract.md.
   - openapi.yaml for every endpoint in the API table, with the {data, error} envelope.
   - fixtures/: one valid example per schema and one response per endpoint (alert fixture = SC-01, score 96, CRITICAL).
2. Create backend/shared/python/finshield/ with: config.py (loads config.json bundled into the layer, reads SSM), ddb.py (table helpers by logical name), schema.py (jsonschema validation), events.py (put_event helper), evidence.py (append + verify, hash chain exactly as contract.md), bedrock.py (converse with guardrail and timeout). Add unit tests for evidence.py.
3. Create infra/template.yaml (SAM) with Parameters Stage, AlertEmail, ContainmentMode, CreateGuardDutyDetector, EnableConfigRules, EnableDnsFirewall, and every resource listed in the M2 module. Start with stub Lambdas that log the event and return OK, so the whole stack deploys now.
4. Create Makefile targets: build, deploy, env (scripts/write-env.sh from stack outputs into web/.env.local), seed, scenario SC=<id>, accuracy, test, smoke, logs FN=<name>.
5. In web/, add lib/api.ts (typed client from openapi.yaml, mock mode reads contract/fixtures when NEXT_PUBLIC_USE_MOCKS=true) and set next.config output to 'export'. If the boilerplate uses API routes, middleware or server actions, list them and stop: we will host on Amplify instead.
6. Generate one Kiro spec per module M2-M8 under .kiro/specs/ using the module descriptions in docs/playbook.md, each with requirements, design and tasks; tasks marked P0, P1, P2.
Finish by running sam validate --lint and pytest, and print what passed and what is stubbed.
```

After it finishes, M1 commits, pushes and tells everyone to pull.

## Member modules and prompts

Each module has a scope, a Start prompt (paste into Kiro once) and a Validate prompt (paste at every checkpoint, or any time you are unsure where you stand). Every prompt assumes Kiro has read `.kiro/steering/`, `contract/` and `docs/playbook.md`.

### M1 — Integration lead, Kiro specs and steering

**Scope.** P0: steering files, master spin-up prompt, `contract/`, Makefile, one spec per module. P1: Kiro hooks (on save in `backend/functions/**` run that function's pytest; on change in `contract/**` validate every fixture against its schema), `make smoke` end-to-end test, checkpoint runs. P2: CHANGES.md triage, final merge and rehearsal owner.

**Start prompt**

```text
I am M1, the FinShield integration lead. Run the master spin-up prompt in docs/playbook.md section 3.
Then create two Kiro hooks: (1) on save of backend/functions/<name>/**, run pytest backend/tests/test_<name>.py;
(2) on save of contract/**, validate every file in contract/fixtures against its schema and print failures.
Then write scripts/smoke.sh: deploy check, put SC-01 on the bus, poll GET /v1/alerts until one CRITICAL alert with score 96 exists (timeout 90 s),
verify its evidence chain, and print PASS/FAIL per step.
```

**Validate prompt**

```text
I am M1. Check the repo against the contract: (1) every Lambda in backend/functions is registered in infra/template.yaml and vice versa;
(2) every fixture validates; (3) every API path in openapi.yaml has a handler; (4) no module hardcodes table names, ARNs or scoring numbers;
(5) grep for "DPDP compliant" and "Consent Manager" in code, web and docs. Then run make test and make smoke.
Report a table: check, status, owner module, fix needed.
```

**Done when** `make smoke` passes at CP2 and every checkpoint after it.

### M2 — Infrastructure (SAM)

**Scope.** P0: Lambda layer; bus `finshield-dev-bus` plus default-bus rules that forward CloudTrail, GuardDuty and Config events; all 13 tables; 5 buckets (evidence bucket with Object Lock); every Lambda with its EventBridge or API trigger; HTTP API; SSM parameters; SNS topic with email subscription; state machine from `backend/statemachines/incident.asl.json` with DefinitionSubstitutions; demo IAM principals `finshield-dev-demo-ops-admin` (role) and `finshield-dev-demo-kyc-user` (user with access key, for real mode); CloudTrail trail with S3 data events on the KYC bucket only. P1: Cognito user pool, client, 5 groups and seed users; CloudFront with OAC for the web bucket; KMS key; Bedrock Guardrail resource; 3 Config rules (`s3-bucket-public-read-prohibited`, `cloudtrail-enabled`, `mfa-enabled-for-iam-console-access`), recorder only if none exists; GuardDuty detector only if none exists; CloudWatch dashboard and alarm on time-to-detect. P2: Route 53 Resolver DNS Firewall (needs a VPC, behind `EnableDnsFirewall`); Knowledge Base id into SSM.

**Start prompt**

```text
I am M2, infrastructure. First write scripts/sandbox-check.sh that tests, in ap-south-1: bedrock converse on the SSM model id,
cloudtrail put-event-selectors, s3 create-bucket with object lock, config describe-configuration-recorders, guardduty list-detectors,
iam put-role-policy on a test role, cognito-idp create-user-pool, route53resolver list-firewall-domain-lists, cloudfront list-distributions.
Print ALLOWED/DENIED per check. Then complete infra/template.yaml with every resource in my module scope, using Conditions for
GuardDuty, Config recorder and DNS Firewall. Least-privilege policies per function (SAM policy templates where possible).
The Evidence table must not be writable with UpdateItem/DeleteItem by any role. Outputs: ApiUrl, UserPoolId, UserPoolClientId, BusName,
StateMachineArn, WebBucket, CloudFrontUrl, KycBucket, EvidenceBucket. Then write scripts/write-env.sh and run make deploy.
```

**Validate prompt**

```text
I am M2. Run sam validate --lint, then compare the deployed stack with the contract: list every table, bucket, function, rule, API route,
SSM parameter and output, and mark missing or misnamed ones. Put a test Raw Activity event on finshield-dev-bus and show it reached the normalizer logs.
Download one object from the KYC bucket with the demo user and show the CloudTrail data event arriving on our bus (report the delay).
Print sandbox-check results and which features run in DRY_RUN because of a DENIED permission.
```

**Done when** the stack deploys from clean, all outputs exist, and a real KYC download reaches the normalizer.

### M3 — Detection pipeline

**Scope.** P0: `normalizer` (CloudTrail GetObject on the KYC bucket becomes DOWNLOAD with `object_id` from the key; ConsoleLogin becomes LOGIN; AssumeRole becomes ASSUME\_ROLE; StopLogging or DeleteTrail becomes LOGGING\_CHANGE; GuardDuty and Config map to their actions; dedup by `event_id`; archive raw to S3; emit `Normalized Event`); `detection` (atomic counters for 15-min and daily windows, signs S1–S8, exceptions E1–E3, incident dedup, emit `Alert Raised` when severity rises). P1: S9 consent mismatch, S10 abnormal disbursement, S11 misconfiguration; `baseline` Lambda (hourly schedule plus a run on demand after seeding; new users use team baseline until 14 days). P2: late events re-score their window; per-device counters across accounts (edge case 5). Presigned URLs leave no CloudTrail record, so PRESIGN comes only from app events.

**Start prompt**

```text
I am M3, detection. Implement backend/functions/normalizer and backend/functions/detection exactly to contract.md and contract/config.json.
Read points and thresholds only from config.json. Detection: update Counters with atomic ADD, compute signs, apply exceptions,
then upsert the open alert for this user in the 60-minute window with a conditional write; emit Alert Raised only when severity increases.
Write every signal with its facts (the numbers that triggered it). Write pytest cases that feed each scenario file in simulator/scenarios
through normalizer and detection with moto or a local DynamoDB, and assert the expected score and level from the scenario file.
Start with SC-01 (expect 96 CRITICAL) and SC-01b (81 CRITICAL), then the logged-only scenarios.
```

**Validate prompt**

```text
I am M3. Run every scenario test and print scenario, expected score/level, actual score/level, signals hit. Then on the deployed stack:
put SC-01 through make scenario SC=SC-01 and confirm exactly ONE alert exists for its user (not one per event), score 96,
and that exactly one Alert Raised event was emitted per severity step. Report time from last event to alert. Flag any number not read from config.json.
```

**Done when** all 10 scenarios produce their expected level in tests and SC-01 gives one alert in under 60 s on AWS.

### M4 — Response workflow and evidence

**Scope.** P0: `incident.asl.json`; `evidence` functions (append, verify, export to the Object Lock bucket); `contain_revoke_sessions` (inline deny on `aws:TokenIssueTime` earlier than now), `contain_deactivate_keys`, `contain_bucket_deny` (statement Sid `FinShieldDeny<user>` on the KYC bucket); `set_deadlines`; SNS notification. P1: `decision` handler (stores the task token on the alert; POST /decision sends success or failure), 30-min timeout escalation to ComplianceHead, `quarantine` after APPROVE, `release` that undoes all containment, `tamper_demo` (edits a copy and runs verify). P2: `contain_dns_block` (DNS Firewall), High branch step-up MFA flag.

**Start prompt**

```text
I am M4, response and evidence. Write backend/statemachines/incident.asl.json following the Step Functions section of contract.md:
containment and AI explanation run in parallel, containment never waits for AI, AI reports are invoked asynchronously,
approval uses waitForTaskToken with a 30-minute timeout and an escalation branch. Implement the containment, decision, quarantine,
release, set_deadlines and evidence Lambdas. Each containment Lambda reads containment_mode from SSM; in DRY_RUN it writes the exact
API call it would make into evidence. Every step appends an evidence entry via finshield.evidence.append. Use the demo principal from
the Users table (iam_principal_arn). Write tests for verify detecting a modified entry and reporting the first broken seq.
```

**Validate prompt**

```text
I am M4. Start the state machine with contract/fixtures/alert_raised_critical.json and show each state's result.
Confirm: containment finished before the AI step; 4 containment evidence entries exist; the chain verifies; tamper-demo reports the right broken seq;
POST /decision APPROVE moves the alert to LOCKED; POST /release removes every deny and the demo principal can read the bucket again.
Show IAM and bucket policy before and after in LIVE mode, or the recorded calls in DRY_RUN.
```

**Done when** the SC-01 alert runs the full workflow, containment is visible in IAM (or DRY\_RUN evidence), and release fully restores access.

### M5 — AI layer (Bedrock)

**Scope.** P0: `ai_explain` (masked facts in, explanation JSON out, schema and `numbers_used` check, 8 s budget, template fallback); Guardrail with PII filters plus regex for Aadhaar `\b\d{4}\s?\d{4}\s?\d{4}\b` and PAN `[A-Z]{5}[0-9]{4}[A-Z]`. P1: `ai_reports` (RBI incident report, CERT-In form, Data Protection Board notice, customer notice, each citing clauses from M8's summaries); Knowledge Base over `finshield-dev-rules` (if the sandbox blocks a vector store, leave `kb_id` empty and inject the summaries into the prompt); `ask` (answers only about the given case). P2: `kyc_label` on S3 upload (Bedrock image input: doc type, and a flag when a full 12-digit Aadhaar is visible, which emits a privacy event and appears on the Privacy screen).

**Start prompt**

```text
I am M5, AI. Read the model id and guardrail from SSM. Implement backend/functions/ai_explain: build masked facts from the alert
(pseudonymous user id, counts, signals with points and facts, data classes, affected regulation text), call Bedrock Converse at temperature 0
with the guardrail, require JSON matching contract/schemas/ai_explanation.schema.json, check numbers_used equals the alert's computed facts,
retry once, else write a template explanation from the same facts with ai_status=FALLBACK. Hard budget 8 seconds.
Then implement ai_reports (4 types, markdown, saved to Reports table), ask, and kyc_label. Keep prompts in backend/functions/<name>/prompts/.
Test with contract/fixtures/alert_sc01.json and print the outputs.
```

**Validate prompt**

```text
I am M5. Run ai_explain on the SC-01, SC-04, SC-06 and SC-08 fixtures. For each, show: schema valid yes/no, numbers match yes/no,
latency, and whether any name, Aadhaar or PAN appears in the input sent to Bedrock or in the output. Force a timeout and show the fallback.
Run ai_reports on SC-01 and confirm every cited clause exists in the regulation summaries. Report the Guardrail intervention count.
```

**Done when** SC-01 shows a valid, number-checked explanation in under 8 s, and the fallback works with Bedrock switched off.

### M6 — Frontend (existing Next.js admin portal)

**Scope.** P0: typed API client with mock mode; Overview (posture score, alerts by severity, active alerts list, compliance tiles, privacy tiles, regulator deadline countdowns); Alert detail (score bar split by signal with points and facts, event timeline, AI card with FALLBACK label, containment status, approve/reject, evidence chain with Verify). P1: Cognito sign-in with role-based buttons; Simulator panel (one button per scenario, GuardDuty sample, reset); Accuracy panel; Reports tabs; Release button; Tamper demo. P2: Privacy, Compliance map, Rules, Approvals screens; Ask FinShield chat; Architecture page.

**Start prompt**

```text
I am M6, frontend, in web/ (existing Next.js boilerplate). Keep its layout and components. Build screens against lib/api.ts in mock mode
(NEXT_PUBLIC_USE_MOCKS=true) using contract/fixtures only, so nothing waits for the backend. Screens: Overview, Alerts, Alert detail,
Simulator, Accuracy, Privacy, Compliance, Rules, Approvals, Architecture. Alert detail polls every 3 s while status is not CLOSED.
Severity colours: CRITICAL red, HIGH orange, MEDIUM amber. Show deadlines as live countdowns. Show "DPDP-aligned readiness" wording only.
Add Cognito sign-in (amazon-cognito-identity-js or aws-amplify Auth) reading ids from env; hide decision and release buttons unless the
user's group allows them. Static export must still build.
```

**Validate prompt**

```text
I am M6. Run next build with static export. Then switch NEXT_PUBLIC_USE_MOCKS=false, run make env, and click through: sign in as SecurityHead,
run SC-01 from the Simulator panel, watch the alert appear on Overview, open it, see signals, AI card, containment and deadlines update,
approve, verify evidence, run tamper demo, release. List every screen and API call that failed or showed a field missing from the response.
```

**Done when** the full SC-01 story can be clicked through on live data with no console errors.

### M7 — Data, simulator, API and accuracy

**Scope.** P0: seed generator (about 50 users across ops, KYC, collections agents, partner LSP, marketing, auditors and service accounts; 2,000 customers; KYC file metadata; 200 real sample files in S3 stamped SAMPLE; consent ledger; approvals; 30 normal days of events, then run baselines); scenario files SC-01 to SC-10 with relative timestamps and expected score and level; `simulator` (rewrites timestamps to now, batches put-events, `reset` clears Alerts and Counters for scenario users); read API handlers. P1: `test_runner` and Accuracy endpoints (expected vs actual, time to alert, false alerts on 7 normal days); real-mode script (demo user downloads 200 KYC files with boto3, then copies them to `finshield-dev-external-sim` as the unauthorized destination). P2: GuardDuty `create-sample-findings` button.

**Start prompt**

```text
I am M7, data, simulator, API and accuracy. Write simulator/seed/generate.py producing synthetic, SAMPLE-marked data for every table in
contract.md (Aadhaar last-4 and fake PAN only) and scripts/seed.sh to load it and upload 200 sample KYC files. Each scenario uses its own
user so incident dedup never merges scenarios. Write simulator/scenarios/SC-01..SC-10.json (event list with offset_seconds, expected_score,
expected_level) from the scenario table in docs/playbook.md section 5. Implement the simulator Lambda (POST /simulate with scenario_id or reset),
the read endpoints in openapi.yaml, test_runner (reset, replay each scenario plus 7 normal days, write AccuracyRuns), and scripts/real_mode.py.
Every API response must validate against openapi.yaml.
```

**Validate prompt**

```text
I am M7. Check seed counts per table and that baselines exist for every scenario user. Validate every scenario file (ids unique, users exist,
expected values present). Call every GET endpoint and validate responses against openapi.yaml. Run POST /accuracy/run and print the results table:
scenario, expected, actual, pass, time to alert; plus false alerts on normal days. Run real_mode.py once and report the CloudTrail delay.
```

**Done when** the Accuracy panel shows 11 of 11 (10 scenarios plus SC-01b) and 0 false alerts.

### M8 — Compliance, pitch and demo

**Scope.** P0: `docs/compliance-map.md` (table: obligation, FinShield control, evidence produced, screen), regulation summaries uploaded to `finshield-dev-rules` (DPDP Act 2023 and Rules phasing, RBI Digital Lending Directions, RBI IT governance and cyber security directions for NBFCs, RBI IT outsourcing directions, CERT-In 2022 directions); each clause checked against the official text before it goes in. P1: 8-slide deck, 6-minute demo script with exact clicks, business case (buyers, price tiers, AWS cost per million events), architecture diagram. P2: backup demo video, technical defence Q&A sheet, a slide showing the Kiro specs and steering.

**Start prompt**

```text
I am M8, compliance and pitch. Draft docs/compliance-map.md mapping each obligation to a FinShield control, the evidence it produces and
the screen that shows it, using only "DPDP-aligned readiness and controls" wording and marking every clause number I must verify.
Draft regulation summaries as markdown files (one per regulation, clause id + plain summary + why it matters to a digital lender) for
the finshield-dev-rules bucket. Then draft docs/demo-script.md (6 minutes, exact clicks, what to say, fallback if live CloudTrail is slow)
and an 8-slide outline: Problem and 3 deadlines, Who we protect, Product modules, Architecture on AWS, Live demo, Rules + edge cases +
accuracy, Compliance map, Business case and roadmap.
```

**Validate prompt**

```text
I am M8. Check every regulation clause cited in contract/config.json, ai_reports prompts, the web app and the deck appears in my verified summaries.
Check the deck covers each judging parameter with a screen or number. Time the demo script against the live app and list any step that
depends on something not yet working, with its fallback.
```

**Done when** the deck, demo script and backup video are final at CP5, and every cited clause is verified.

## Universal prompts, scenarios and demo script

### Prompts anyone can run at any stage

**Where am I?** (use when you join late, come back from a break, or feel lost)

```text
I am <M-number>. Read .kiro/steering, contract/, docs/playbook.md and .kiro/specs/<my module>.
Look at what exists in my module's folders and in git log for the last 2 hours.
Tell me: (1) which of my P0/P1/P2 items are done, partly done, not started; (2) anything I built that differs from the contract;
(3) which other modules I depend on and whether their parts exist yet (use fixtures if not); (4) the next 3 tasks in order;
(5) what the next checkpoint needs from me. Do not write code until I confirm.
```

**Before I commit**

```text
I am <M-number>. Before I commit: run my module's tests, validate any JSON I produce against contract/schemas,
check I read no hardcoded table names, ARNs or scoring numbers, check new Lambdas are in infra/template.yaml,
and check the compliance wording rules. List problems, fix them, then give me a one-line commit message.
```

**I'm blocked**

```text
I am <M-number>, blocked on <thing>. Propose the smallest workaround that keeps the contract intact
(fixture, DRY_RUN, stub returning the contract shape, or prompt-injected text instead of a service),
write it, and add a line to contract/CHANGES.md saying what is stubbed and who must replace it.
```

**Integration check** (M1 at every checkpoint)

```text
I am M1 running checkpoint <CP-number> from docs/playbook.md. Pull main, make deploy, make seed if needed, then test exactly what that
checkpoint's "passes when" says. Run make smoke. Read contract/CHANGES.md. Report: PASS/FAIL per criterion, the module that owns each
failure, the exact error, and the fix. List any stubs still in the demo path.
```

**Demo-ready check** (whole team, at CP5)

```text
Run the demo script in docs/demo-script.md against the deployed stack from a clean reset. For each step report pass/fail and timing.
Run POST /accuracy/run and show the table. Confirm: one alert per scenario user, evidence verifies for every alert, release restores access,
AI fallback works with Bedrock disabled, no console errors in the web app, no forbidden compliance wording anywhere.
List anything that must not be clicked during the live demo.
```

### Scenarios (M7 writes them, M3 tests them, the Accuracy panel checks them)

Each scenario uses its own user so incident dedup never merges two scenarios.

| ID | Story | Signs hit | Score | Level |
| --- | --- | --- | --- | --- |
| SC-01 | Ops admin assumes emergency role at 23:40 from a new device and second city, downloads 212 KYC files, uploads to an external share (mandatory demo) | S1 40, S3 20, S4 15, S5 11, S6 10 | 96 | Critical |
| SC-01b | Same, no external upload | S1 40, S3 20, S5 11, S6 10 | 81 | Critical |
| SC-02 | Nightly KYC registry upload by the service account inside its job window | S1, capped by E1 | 30 | Logged |
| SC-03 | Auditor pulls 90 files under an approved 100-file ticket | S1, capped by E2 | 30 | Logged |
| SC-04 | Collections agent opens 120 unassigned customers in 15 min | S7 40, S1 30 | 70 | High |
| SC-05 | One late download of 15 files | S1 10, S6 10 | 20 | Logged |
| SC-06 | Compromised cloud admin: 6 MFA pushes, login from a city 1,400 km away, emergency role, StopLogging | S5, S3, S8 | 100 | Critical |
| SC-07 | Marketing user reads KYC of 40 customers who consented only to loan processing | S9 30, S7 40 | 70 | High |
| SC-08 | Agent changes a borrower's bank account from a new device, ₹4.8 lakh disbursed to it at 01:40 | S10 50, S6 10, S5 5 | 65 | High |
| SC-09 | KYC bucket made public; Config marks it non-compliant | S11 45 | 45 | Medium |
| SC-10 | Auditor with a 100-file ticket downloads 150 (ticket exceeded by more than 20%) | S1 30, exceeded +10 | 40 | Medium |

Plus 7 normal days replayed with 0 expected alerts. The real-mode run repeats SC-01 with the demo IAM user through CloudTrail.

### Demo script (6 minutes; M8 owns the final version)

1. **0:00 Problem (30 s).** A lender holds KYC for every borrower; a leak triggers RBI and CERT-In 6-hour clocks and a DPB report. Show the Overview: posture score, compliance and privacy tiles.
2. **0:30 Attack (60 s).** Click SC-01 in the Simulator panel. The Critical alert appears on Overview in under 60 s. Point at the deadline countdowns starting.
3. **1:30 Investigate (60 s).** Open the alert: score bar by signal (106× normal volume, emergency role without approval, new device, off-hours, external upload), timeline, AI card with clause citations. Say "code computed every number, AI only wrote the words".
4. **2:30 Respond (60 s).** Containment already done before the AI finished: sessions revoked, keys off, bucket deny. Show it in IAM or the bucket policy. Approve as SecurityHead; status goes LOCKED. Show Release to prove it is reversible.
5. **3:30 Evidence (45 s).** Verify the chain (green), click Tamper demo (red from the edited entry). Show the drafted CERT-In report.
6. **4:15 Breadth (45 s).** Accuracy panel: 11/11, 0 false alerts. Show SC-07 consent mismatch and SC-03 auditor ticket staying quiet.
7. **5:00 Architecture and compliance (45 s).** AWS diagram, Mumbai region, Kiro specs and steering, compliance map with "DPDP-aligned readiness" wording.
8. **5:45 Close (15 s).** Who buys it and what it costs to run.

**Fallbacks:** if CloudTrail is slow, keep the real-mode run as a second demo only; if Bedrock fails, the AI card shows FALLBACK and the story still holds; if anything else fails, play the backup video from the same step.
