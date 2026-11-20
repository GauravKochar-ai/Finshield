# FinShield AI - AWS module

Detects a **privileged account exporting unusual volumes of KYC documents**, raises a
**CRITICAL alert with a tamper-proof evidence trail**, auto-contains, waits for **CISO
approval**, disables the account and drafts **RBI / CERT-In / DPDP** reports.

## What gets created (one `sam deploy`)

| Resource | Name | Purpose |
|---|---|---|
| HTTP API | `POST /events` | Events come in here |
| Lambda | `fs-ingest` | Raw copy to S3, store event, correlate last 60 min, case score, start workflow once per case |
| Lambda | `fs-analyze` | Mask Aadhaar/PAN (regex + optional Guardrail), Bedrock verdict, MITRE, regulations |
| Lambda | `fs-evidence` | SHA-256 hash-chained evidence pack in S3 |
| Lambda | `fs-contain` | MOCK: revoke session + block destination |
| Lambda | `fs-store-token` | Saves the approval token so the dashboard can approve |
| Lambda | `fs-respond` | MOCK: disable account after approval |
| Lambda | `fs-report` | RBI / CERT-In / DPDP drafts in S3 |
| Step Functions | `fs-response-workflow` | The response playbook |
| EventBridge rule | (created by SAM) | `case_score >= 0.7` -> start workflow |
| DynamoDB | `fs-events`, `fs-cases` | Events and cases |
| S3 | `fs-raw-logs-<acct>-<region>`, `fs-evidence-<acct>-<region>` (versioned) | Raw logs, evidence packs, reports |
| SNS | `fs-alerts` | Email alerts |

## Folder layout

```
template.yaml                 SAM template (all AWS resources)
statemachine/workflow.asl.json  Step Functions definition
src/ingest/                   fs-ingest  (+ baselines.json, approved_destinations.json)
src/analyze/                  fs-analyze
src/evidence/                 fs-evidence (+ chain.py, shared with tools/dashboard)
src/workflow/                 fs-contain, fs-store-token, fs-respond
src/report/                   fs-report
tools/                        test scripts (send events, approve, status, verify, reset)
```

## Deploy

```bash
cd ~/Globalnodes\ projects/AWS\ Hackathon/Finshield
aws sts get-caller-identity          # check you are in the sandbox account
sam validate
sam build
sam deploy --guided
```

Answers for `--guided` (first time only):

| Question | Answer |
|---|---|
| Stack Name | `fs-stack` (the tools expect this name) |
| AWS Region | your sandbox region |
| AlertEmail | team email |
| ModelId | Bedrock model / inference profile ID from the console, or `NONE` for rule-based text |
| GuardrailId | Priya's guardrail ID, or `NONE` |
| GuardrailVersion | `1` |
| Confirm changes before deploy | `y` |
| Allow SAM CLI IAM role creation | `Y` |
| Disable rollback | `N` |
| IngestFunction has no authentication. Is this okay? | `y` (demo only) |
| Save arguments to configuration file | `Y` |

**After the first deploy: open your inbox and click "Confirm subscription" (SNS).**

Next deploys: `sam build && sam deploy`
Change model / guardrail later: `sam deploy --parameter-overrides ModelId=... GuardrailId=...`
Live logs: `sam logs -n IngestFunction --stack-name fs-stack --tail`

## Test (5 minutes)

```bash
pip install boto3                    # tools only need boto3
python3 tools/send_events.py --scenario hero          # score 0.3 -> 0.3 -> 0.6 -> 1.0, workflow starts
python3 tools/status.py                               # see the case, status PENDING_APPROVAL
python3 tools/approve.py --latest                     # CISO approves -> account disabled -> reports
python3 tools/status.py --case-id case-ADM-07-<YYYYMMDD>
python3 tools/verify_evidence.py --case-id case-ADM-07-<YYYYMMDD> --tamper   # ✅ then ❌
python3 tools/send_events.py --scenario decoy         # must stay LOW (0.1), no workflow
python3 tools/send_events.py --scenario all --delay 1 # every scenario
python3 tools/reset_data.py --yes                     # clean before the demo
```

Expected scores: hero 1.0 CRITICAL, decoy 0.1 LOW, login_only 0.3 LOW,
night_bulk 0.6 WATCH, personal_cloud 0.4 WATCH.

A case starts its workflow **only once**. To re-run the hero, use `--actor ADM-09`
or run `reset_data.py --yes` first.

## Detection rules (fs-ingest)

| Signal | When | Score |
|---|---|---|
| PRIVILEGED_ACTOR | privileged = true | +0.1 |
| ANOMALOUS_LOGIN | LOGIN with no MFA, unknown-vpn, or 22:00-06:00 | +0.2 |
| BULK_KYC_ACCESS | doc_count >= 10 x actor baseline (`baselines.json`) | +0.3 |
| UNAUTHORIZED_DESTINATION | destination not in `approved_destinations.json` | +0.4 |
| AUTHORIZED_TICKET | approved destination + ticket_id | -0.3 |

>= 0.9 CRITICAL, >= 0.7 HIGH (starts workflow), >= 0.4 WATCH, else LOW.
The AI can raise severity but never lower it; PRIVILEGED + BULK + UNAUTHORIZED is always CRITICAL.

## Event format (POST /events)

```json
{"actor_id":"ADM-07","actor_role":"db_admin","privileged":true,"event_type":"DATA_TRANSFER",
 "ts":"2026-11-20T01:41:00+05:30","destination":"s3://ext-backup-7781","doc_count":4800}
```
`event_type`: LOGIN | ASSUME_ROLE | KYC_DOC_DOWNLOAD | DATA_TRANSFER | TRANSACTION.
`ts` must be ISO-8601 with `+05:30`.

## For the dashboard (fs-cases fields)

`case_id, actor_id, case_score, severity_rule, severity, signals, event_ids, docs_involved,
destinations, status, detected_at, summary, mitre, regulation, recommended_actions,
masked_timeline, pii_masked_count, ai_used, evidence_key, evidence_hash, containment,
contained_at, approval_token, approver, disabled_at, report_keys, reporting_deadline`

Status flow: `OPEN -> ANALYZED -> CONTAINED -> PENDING_APPROVAL -> ACCOUNT_DISABLED | FALSE_POSITIVE`

Approve from code (same as `tools/approve.py`):
```python
boto3.client("stepfunctions").send_task_success(
    taskToken=case["approval_token"],
    output=json.dumps({"decision": "APPROVED", "approver": "ciso@finshield.in"}))
```
Verify evidence from code: `from chain import verify_pack` (see `tools/verify_evidence.py`).

## Troubleshooting

1. Deploy failed -> CloudFormation console -> `fs-stack` -> Events -> first `CREATE_FAILED`.
2. No email -> confirm the SNS subscription.
3. Score not increasing -> all `ts` values must use the same `+05:30` format and same day.
4. No workflow -> score below 0.7, or the case already started one (use a new actor).
5. Red state in Step Functions -> click it, read Input / Error (usually IAM or a missing field).
6. `ai_used = false` on a case -> ModelId is NONE or Bedrock failed; see `ai_error` and fs-analyze logs.

If SAM is blocked in the sandbox, create the same resources in the console (same names, same code).
