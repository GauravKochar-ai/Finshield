# Contract changes and open points (for the integration lead)

## OPEN-1: S1 divisor floor of 5 contradicts the SC-01 numbers
- Playbook scoring table: `ratio = downloads_15m / max(user p95, team p95, 5)`.
- Playbook alert shape and SC-01: 212 downloads, `baseline_p95: 2`, `ratio: 106`, S1 = 40 points, total 96.
- With a floor of 5, SC-01 gives 212/5 = 42x, which is 30 points (total 86, not 96). SC-05 (15 files, S1 10) and SC-04/SC-10 only work with a divisor of 3 to 6, which is a per-user baseline, not a global floor.
- **Applied for now:** `contract/config.json` sets `signals.S1.baseline_floor = 1` (only guards divide-by-zero) so SC-01 scores 96. Each scenario user must therefore have its own seeded `p95_15min` (SC-01: 2, SC-05: 3 to 5, SC-04: up to 6, SC-10: 2 to 7).
- **Decision needed:** keep floor 1 with per-user baselines (recommended), or raise the floor to 5 and change the SC-01 target score.
- Owners: M3 (detection), M7 (seed baselines).

## OPEN-2: report schema is not specified in the playbook
- `report.schema.json` is inferred from the Reports table (`alert_id`, `report_type`, `status`, `body_md`, `model_id`, `generated_at`).
- `report_type` values chosen: `RBI_INCIDENT`, `CERTIN_FORM`, `DPB_NOTICE`, `CUSTOMER_NOTICE`. `status`: `PENDING|DRAFT|FALLBACK|FAILED`.
- Owner: M5 to confirm.

## OPEN-3: shapes not given in the playbook, chosen by M1
- Response bodies for posture, privacy, compliance, accuracy, approvals, simulate and users are defined in `openapi.yaml` and shown by `contract/fixtures/api_*.json`. Treat them as the contract once M6/M7 agree.
- Alert `severity` has no LOW value: scores below 40 are logged only and create no alert record.
- Evidence entry `ts` is not restricted to +05:30; `hash` is 64 hex chars; entry 1 has `prev_hash = GENESIS:<alert_id>`.

## OPEN-4: legacy fs-* prototype in the repo root
- `template.yaml`, `src/`, `statemachine/`, `tools/`, `infra/infra.yaml`, `README_AWS.md` come from an earlier prototype (stack `fs-stack`). They conflict with "infra/template.yaml is the only template". Left untouched; decide whether to delete or move to `legacy/`.

## OPEN-5: attribute names the playbook leaves open (chosen in `infra/template.yaml`)
- Events: PK `user_id`, SK `sk` (= `ts#event_id`); GSI `scenario-ts-index` (`scenario_id`, `ts`).
- Counters: PK `pk` (= `user_id#window`), SK `bucket_start` (string).
- Alerts GSIs: `user-detected-index` (`user_id`, `detected_at`), `status-detected-index` (`status`, `detected_at`).
- Other GSIs: `partner-index`, `customer-index`, `subject-index`.
- Env vars: `TABLE_<LOGICAL_UPPER>` (e.g. `TABLE_ACCURACYRUNS`), `EVENT_BUS_NAME`, `KYC_BUCKET`, `RAW_BUCKET`, `RULES_BUCKET`, `EVIDENCE_BUCKET`, `ALERT_TOPIC_ARN`.

## OPEN-6: infrastructure choices that differ from, or add to, the playbook
- HTTP API uses the default stage and routes carry `/v1`; `ApiUrl` output ends in `/v1`, so clients append `/alerts`, not `/v1/alerts`.
- `Alert Raised` goes to a `start_incident` Lambda (EventBridge cannot set the execution name `<alert_id>-<severity>` on a Step Functions target).
- State machine passes `mode` from the `ContainmentMode` stack parameter; containment Lambdas should prefer the live SSM `containment_mode`.
- SSM `kb_id` is `NONE` when empty (SSM rejects empty values). Extra parameters: `CreateConfigRecorder`, `VpcId`, `BedrockModelId`.
- Extra buckets: `external-sim` (real-mode destination), `trail` (CloudTrail logs), optional `config`.
- Bucket names are fixed by the contract and global; a clash fails the deploy.
- The template has been linted only, never deployed. Guardrail PII types and Object Lock need a real deploy to confirm.

## OPEN-7: response and AI layer behaviour (Keshav, P0 done)
- `containment_mode` in SSM decides LIVE vs DRY_RUN and is read fresh on every call; the state machine's `mode` input is only a fallback. LIVE runs only against principals named `finshield-dev-demo-*`; any other principal is forced to DRY_RUN and the reason is recorded.
- Containment results use `result` OK, FAILED or NOT_APPLICABLE (roles have no access keys, so DEACTIVATE_KEYS on the SC-01 role principal is NOT_APPLICABLE).
- Evidence appends from the workflow are idempotent: payload carries `dedup_key = <execution name>:<type>`.
- Alert status moves OPEN → CONTAINED (end of the containment branch) → AWAITING_APPROVAL (before the approval wait), set by the state machine with a conditional DynamoDB update; each change also emits `Incident Updated`.
- `ai_explain` accepts `{"force_fallback": true}`. It rejects Bedrock output whose numbers are not computed facts or whose clauses are not in `backend/functions/ai_explain/regulations.json`. That file is the boilerplate's regulation list, NOT VERIFIED; fallback text marks each clause "pending verification" until Arvind replaces it.
- `contain_bucket_deny` edits the KYC bucket policy at runtime; the next `sam deploy` resets it to the template (removes any deny).

## CHANGE-7 (M3, aekanshu): windows added to config.json, version 1.1.0
- `signals.S1.window_minutes = 15`, `signals.S2.window_hours = 24`, new `baselines` block (`lookback_days 30`,
  `min_history_days 14`, `percentile 95`). They were fixed numbers in the playbook text; R2.1 says windows come only from config.
- `contract/fixtures/api_rules.json` mirrors config.json and does not show these keys yet (owner of GET /rules to refresh).

## OPEN-10 (M3): where the E2 overage +10 is shown
- The alert schema only allows signal codes S1-S11, so there is no `E2X` signal. Detection adds the 10 overage points to the
  S1 (or S2) signal and records `ticket_id`, `ticket_max_files`, `files_in_window`, `ticket_overage_points` in its facts.
  SC-10 therefore shows S1 = 40 (30 + 10). Alternative: allow an `E2X` code in alert.schema.json. Decision needed (M3, M6).

## OPEN-11 (M3): scope of S7 and the score of logged-only results
- S7 applies only to users with `Users.access_scope = "ASSIGNED"` (agents, partner agents, marketing). Ops, KYC, auditors and
  service accounts have `ALL`; otherwise SC-01 would also score S7.
- Scores below 40 create no alert, so detection keeps the highest score per user in `Counters` (`<user_id>#score` / `max`)
  for the accuracy runner. One open alert per user is enforced with a pointer item `Counters` (`<user_id>#alert` / `open`),
  the daily alert number lives in `Counters` (`alert_seq` / `YYYYMMDD`).

## CHANGE-8 (M3): template permissions
- simulator: CRUD on Events (reset deletes replayed events). test_runner: read on Counters (logged-only scores).
  baseline: Timeout 120 s. Makefile `layer` copies `simulator/scenarios` and `simulator/seed/generate.py` (as `finshield/seedgen.py`).

## OPEN-12 (M3): real-mode role name
- S3 matches `signals.S3.emergency_roles = ["KYC-Emergency"]`. The template has no role with that name; real mode via
  CloudTrail needs either a role named KYC-Emergency or this list extended. TimeToDetectMs uses event ts, which the simulator
  sets to the scenario clock time (can be hours ago); test_runner's time_to_alert_ms measures from send time instead.
