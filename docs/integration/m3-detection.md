# Integration guide: M3 detection Lambdas

Owner: aekanshu (M3). Read this, or give it to your AI assistant, to connect to the detection pipeline.
Source of truth for shapes: `contract/schemas/*.schema.json`, `contract/openapi.yaml`, `contract/config.json`.
All data is synthetic and marked SAMPLE. Region `ap-south-1`, stage `dev`, every name is `finshield-dev-<name>`.

## 1. The pipeline in one picture

```
simulator / app / CloudTrail / GuardDuty / Config
        │  EventBridge bus finshield-dev-bus
        ▼  detail-type "Raw Activity" (or the AWS detail-types)
  normalizer ──► Events table (+ raw JSON in s3://finshield-dev-raw-events/YYYY/MM/DD/<event_id>.json, + Posture for Config)
        │  detail-type "Normalized Event"
        ▼
  detection ──► Counters table, Alerts table
        │  detail-type "Alert Raised"   (only when an alert's severity goes up)
        ▼
  start_incident (M4) ──► Step Functions finshield-dev-incident  (execution name <alert_id>-<severity>)
```

`baseline` runs every hour and writes the Baselines table. `test_runner` measures accuracy and writes AccuracyRuns.

## 2. The five Lambdas

| Lambda | How to call it | Input | Output |
|---|---|---|---|
| `finshield-dev-normalizer` | EventBridge only | `Raw Activity`, `AWS API Call via CloudTrail`, `AWS Console Sign In via CloudTrail`, `GuardDuty Finding`, `Config Rules Compliance Change` | one Events row + `Normalized Event` |
| `finshield-dev-detection` | EventBridge only (`Normalized Event`) | unified event | Counters, Alerts, `Alert Raised` |
| `finshield-dev-baseline` | hourly schedule, or direct invoke `{}` / `{"user_ids":["u-017"]}` | none | Baselines rows |
| `finshield-dev-simulator` | `POST /v1/simulate` (Admin), or direct invoke | `{"scenario_id":"SC-01"}` or `{"reset":true}` | events sent to the bus |
| `finshield-dev-test-runner` | `POST /v1/accuracy/run` (Admin), or direct invoke `{}` | none | accuracy result + AccuracyRuns rows |

## 3. HTTP endpoints (frontend)

Base URL: stack output `ApiUrl` (already ends in `/v1`). Send the Cognito ID token as `Authorization: Bearer <token>`.
Both routes need the user to be in the **Admin** group. Responses use the envelope `{"data": ..., "error": null}`.

**Run a scenario**
```http
POST /v1/simulate
{"scenario_id": "SC-01"}
```
```json
{"data": {"accepted": true, "scenario_id": "SC-01", "events_sent": 217}, "error": null}
```
Other bodies: `{"reset": true}` clears alerts, counters and replayed events for every scenario user;
`{"reset": true, "scenario_id": "SC-01"}` clears only that scenario's user. `{"guardduty_sample": true}` returns 501 (not built yet).
Errors: 403 not Admin, 404 unknown scenario, 400 bad body.

The alert shows up in the Alerts table, and in `GET /v1/alerts`, a few seconds after the events are sent. Poll every 2-3 s.

**Run the accuracy check** (takes up to about 100 s)
```http
POST /v1/accuracy/run
```
```json
{"data": {"run_id": "RUN-20261121-101500", "ran_at": "2026-11-21T10:15:00+05:30", "passed": 11, "total": 11,
          "false_alerts_normal_days": 0,
          "rows": [{"scenario_id": "SC-01", "expected_level": "CRITICAL", "actual_level": "CRITICAL",
                    "expected_score": 96, "actual_score": 96, "pass": true, "time_to_alert_ms": 12000}]},
 "error": null}
```
`time_to_alert_ms` is null for logged-only scenarios (no alert by design).

## 4. Scenarios (list them in the Simulator panel)

Files: `simulator/scenarios/<id>.json`. Each file has `scenario_id, title, user_id, start_time_ist, expected_score,
expected_level, signs, events[]` (events have `offset_seconds`). The simulator keeps the clock time (23:40 stays 23:40)
on today or yesterday, and tags every event_id with a run tag, so a scenario can be replayed any number of times.

| ID | User | Story | Expected |
|---|---|---|---|
| SC-01 | u-017 | Ops admin, emergency role at 23:40, new device, second city, 212 KYC files, external upload (mandatory demo) | 96 CRITICAL |
| SC-01b | u-018 | Same, no upload | 81 CRITICAL |
| SC-02 | svc-ckyc | Nightly registry job inside its window (E1 cap) | 30 LOGGED |
| SC-03 | u-041 | Auditor, 90 files under a 100-file ticket (E2 cap) | 30 LOGGED |
| SC-04 | u-031 | Collections agent opens 120 unassigned customers | 70 HIGH |
| SC-05 | u-011 | One late download of 15 files | 20 LOGGED |
| SC-06 | u-046 | Cloud admin: MFA fatigue, distant city, emergency role, StopLogging | 100 CRITICAL |
| SC-07 | u-037 | Marketing reads KYC of 40 customers without marketing consent | 70 HIGH |
| SC-08 | u-032 | Bank account changed from a new device, Rs 4.8 lakh disbursed at 01:40 | 65 HIGH |
| SC-09 | svc-aws-config | KYC bucket made public (Config non-compliant) | 45 MEDIUM |
| SC-10 | u-042 | Auditor downloads 150 on a 100-file ticket (more than 20% over) | 40 MEDIUM |

LOGGED = below 40: no alert record, no `Alert Raised`.

## 5. Events on the bus

**Send your own activity** (app events, P2 buttons): put `Raw Activity` with a unified event as the detail.
```bash
aws events put-events --entries '[{"EventBusName":"finshield-dev-bus","Source":"finshield.app","DetailType":"Raw Activity",
  "Detail":"{\"event_id\":\"app-0001\",\"ts\":\"2026-11-21T10:00:00+05:30\",\"source\":\"app\",\"user_id\":\"u-017\",\"action\":\"DOWNLOAD\",\"customer_id\":\"C-10442\",\"data_class\":\"KYC\",\"purpose\":\"loan_processing\"}"}]'
```
Required: `event_id`, `ts` (ISO 8601, +05:30), `source`, `user_id`, `action`. Allowed actions: LOGIN, MFA_PUSH, ASSUME_ROLE, VIEW,
DOWNLOAD, PRESIGN, UPLOAD_EXTERNAL, LOGGING_CHANGE, BANK_ACCOUNT_CHANGE, DISBURSE, CONFIG_NONCOMPLIANT, GUARDDUTY_FINDING,
KYC_FILE_UPLOADED. No other fields are allowed (schema `additionalProperties: false`). Invalid events are logged and dropped.
The same `event_id` twice is processed once.

**Alert Raised** (detection → M4): one per severity step of an alert. SC-01 usually gives MEDIUM, then HIGH, then CRITICAL
for the same `alert_id`; each starts its own execution `<alert_id>-<severity>`.
```json
{"alert_id": "ALR-20261121-0007", "severity": "CRITICAL", "previous_severity": "HIGH", "score": 81,
 "user_id": "u-017", "principal_arn": "arn:aws:iam::<acct>:role/finshield-dev-demo-ops-admin",
 "detected_at": "2026-11-21T10:15:02+05:30"}
```
The score can keep rising after the last `Alert Raised` (96 arrives with the upload, still CRITICAL). Read the Alerts row
for the latest numbers.

## 6. Tables detection writes (read them, do not write them)

**Alerts** (`alert_id`; GSIs `user-detected-index`, `status-detected-index`): exactly `alert.schema.json`.
Detection creates the row (`status OPEN`, `ai_status PENDING`, `containment []`, `ai null`, `execution_arn null`,
deadlines from config) and later updates only `score, severity, signals, exceptions_applied, customers_affected,
data_classes, event_ids`, only when the new score is higher. Everything else (status, containment, ai, execution_arn)
belongs to M4/M5 and is never touched by detection.

One open alert per user: an alert is open while `status != CLOSED` and `detected_at` is within the last 60 minutes.
After that a new event starts a new alert.

Each signal: `{"code": "S1", "points": 40, "facts": {...}}`. Facts hold the numbers that triggered it, e.g.
S1 `{"downloads_15m":212,"baseline_p95":2,"ratio":106}`, S5 `{"new_device":"d-new-77","cities":["Pune","Delhi"],"distance_km":1180,"window_minutes":40}`.
The AI number check (M5) compares against these.

**Counters** (`pk`, `bucket_start`):
| pk | bucket_start | Fields |
|---|---|---|
| `<user_id>#15m` | 15-min bucket start (local) | downloads, bytes_total, mfa_pushes, presigns, events_total, customer_ids (set) |
| `<user_id>#1d` | local date | same |
| `device#<device_id>#1d` | local date | events_total, user_ids (set) |
| `<user_id>#score` | `max` | highest score so far, also below 40 (used by test_runner) |
| `<user_id>#alert` | `open` | pointer to the open alert (dedup lock) |
| `alert_seq` | `YYYYMMDD` | daily alert counter for `ALR-YYYYMMDD-NNNN` |

**Events** (`user_id`, `sk = <ts>#<event_id>`; GSI `scenario-ts-index`): the unified event; null fields are left out.
Replays have `is_replay: true` and `scenario_id`. Timeline API: query by `user_id` and an `sk` range, or by scenario on the GSI.

**Baselines** (`subject_id` = user_id or `team:<team>`): `p95_15min, avg_daily, usual_hours, cities, devices,
p95_disburse_inr, days_of_history, source` (`user`, or `team` when the user has less than 14 days of history).

**AccuracyRuns** (`run_id`, `scenario_id`): one row per scenario (fields of the accuracy row above) plus `NORMAL-7D`
with `false_alerts` and `events`. `GET /v1/accuracy` = latest `run_id`.

**Posture** (`control_id`): normalizer writes `config:<rule>:<resource>` with `status` COMPLIANT / NON_COMPLIANT,
and `config:simulated:<resource>` for SC-09.

## 7. Scoring (how a number becomes a level)

Code: `backend/shared/python/finshield/scoring.py` (pure functions, no AWS). Every point value, threshold and window comes
from `contract/config.json`; change the number there, rebuild the layer, deploy. `GET /v1/rules` shows that file.
Levels: 80+ CRITICAL, 60-79 HIGH, 40-59 MEDIUM, below 40 logged. Score capped at 100.

| Sign | Fires when | Points |
|---|---|---|
| S1 | 15-min downloads ÷ max(user p95, team p95, 1): ≥100×, ≥20×, ≥5×, ≥3× | 40, 30, 20, 10 |
| S2 | today's downloads > 5× daily average and > 200 (only if higher than S1) | 25 |
| S3 | emergency role with no approval, or service account outside its job window | 20 |
| S4 | upload to a destination not on the allowlist (≥100 MB or within 60 min of KYC downloads = high) | 15 / 8 |
| S5 | new device 5, ≥5 MFA pushes in 2 min 6, two cities >500 km apart within 1 h 11 | max 11 |
| S6 | activity more than 1 h outside usual hours | 10 |
| S7 | ≥20 customers not assigned to the user in 1 h (only users with `access_scope = ASSIGNED`) | 40 |
| S8 | logging switched off | instant 100 |
| S9 | KYC/PII read for a purpose the customer has not consented to, ≥10 customers in 1 h | 30 |
| S10 | disbursement to an account changed <24 h ago 30; amount >3× user's p95 +20 | max 50 |
| S11 | Config non-compliant: KYC resource 45, other 20 | max 45 |

Exceptions: E1 scheduled job in its window caps at 30. E2 approved ticket caps at 30; more than 20% over the ticket voids
the cap and adds 10 (shown inside the S1 signal facts: `ticket_overage_points`). E3 an approval by the actor is ignored.
GuardDuty findings are normalized but not scored.

## 8. Run it

```bash
make deploy                 # build layer + SAM deploy
make seed                   # Cognito demo users + seed data (simulator/seed/generate.py --load)
make scenario SC=SC-01      # replay; then check Alerts for u-017: one alert, score 96, CRITICAL
make accuracy               # 11 of 11, 0 false alerts
make logs FN=detection      # tail logs
```
Seed JSON for tests or mocks: `python3 simulator/seed/generate.py --out build/seed`.
Tests: `make test` (fast); `RUN_SLOW=1 make test` replays every scenario through mocked AWS.

## 9. Known limits

- `TimeToDetectMs` (CloudWatch, namespace FinShield) is now minus the event's `ts`. Simulated events keep the scenario's
  clock time, so for replays it can show hours. Use `time_to_alert_ms` from the accuracy run for the "under 60 s" check.
- Real mode through CloudTrail: S3 only fires for roles named in `signals.S3.emergency_roles` (`KYC-Emergency`). The demo
  role is `finshield-dev-demo-ops-admin`; extend the list or add the role (contract/CHANGES.md OPEN-12).
- Late or out-of-order events re-score their window; severity never goes down, the score never goes down.
