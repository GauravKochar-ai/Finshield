# Requirements: M2 Infrastructure (SAM)

Owner: M2. Needs from: M1 contract. Gives to: Stack outputs and `web/.env.local` for everyone.

Steering: `.kiro/steering/*`. Contract: `contract/` (config.json, schemas, openapi.yaml, fixtures). Playbook: `docs/playbook.md`. Contract changes go to `contract/CHANGES.md`, never silently.

## User story

As the infrastructure owner, I want one SAM template that deploys the whole FinShield stack in ap-south-1, so every other module can build and test against real tables, a bus, an API and an evidence bucket.

## Requirements

### R1. Single template and naming

1.1. WHEN the stack is deployed THE SYSTEM SHALL create every resource from `infra/template.yaml` with the name `finshield-${Stage}-<name>` and tag `project=finshield`.
1.2. THE SYSTEM SHALL run all Lambdas on Python 3.12, arm64, 512 MB, 30 s timeout (60 s for AI functions), handler `app.handler`, with shared code only from the `finshield` layer.

### R2. Data plane

2.1. THE SYSTEM SHALL create the 13 DynamoDB tables from the playbook (on-demand, PITR, KMS) with the listed keys and GSIs.
2.2. THE SYSTEM SHALL create buckets `kyc-docs` (KMS, private, CloudTrail data events), `raw-events` (1-year lifecycle), `rules`, `evidence` (Object Lock COMPLIANCE, 1 year, enabled at creation) and `web` (behind CloudFront with OAC).
2.3. THE SYSTEM SHALL grant no role UpdateItem or DeleteItem on the Evidence table.

### R3. Event plane

3.1. THE SYSTEM SHALL create the bus `finshield-dev-bus` and default-bus rules that forward CloudTrail, GuardDuty and Config events to it.
3.2. WHEN an event with a detail-type of Raw Activity, CloudTrail, GuardDuty or Config arrives THE SYSTEM SHALL route it to the normalizer; Normalized Event to detection; Alert Raised to the incident starter.
3.3. THE SYSTEM SHALL start the state machine with execution name `<alert_id>-<severity>`.

### R4. API and identity

4.1. THE SYSTEM SHALL expose an HTTP API under `/v1` with a Cognito JWT authorizer and one route per operation in `contract/openapi.yaml`.
4.2. THE SYSTEM SHALL create a Cognito pool, a web client, the five groups (Analyst, SecurityHead, ComplianceHead, Auditor, Admin) and, through `make seed`, one demo user per group.

### R5. Settings and demo principals

5.1. THE SYSTEM SHALL store `containment_mode`, `bedrock_model_id`, `guardrail_id`, `guardrail_version`, `kb_id` and `alert_email` under `/finshield/dev/`.
5.2. THE SYSTEM SHALL create the demo role `finshield-dev-demo-ops-admin` and the demo user `finshield-dev-demo-kyc-user` with an access key kept in Secrets Manager.

### R6. Optional features

6.1. WHERE `CreateGuardDutyDetector`, `EnableConfigRules` or `EnableDnsFirewall` is false THE SYSTEM SHALL skip the related resources.
6.2. WHEN the sandbox denies a permission THE SYSTEM SHALL let the affected feature run in DRY_RUN and `scripts/sandbox-check.sh` SHALL report it.

## Done when

The stack deploys from clean, all outputs exist, and a real KYC download reaches the normalizer.
