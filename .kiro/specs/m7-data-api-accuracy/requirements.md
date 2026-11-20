# Requirements: M7 Data, simulator, API and accuracy

Owner: M7. Needs from: M2 tables, M3 scoring rules. Gives to: Seeded DynamoDB, replayable scenarios, REST API.

Steering: `.kiro/steering/*`. Contract: `contract/` (config.json, schemas, openapi.yaml, fixtures). Playbook: `docs/playbook.md`. Contract changes go to `contract/CHANGES.md`, never silently.

## User story

As the data owner, I want synthetic seed data, replayable scenarios, the read API and an accuracy runner, so every detection claim is measured.

## Requirements

### R1. Seed data

1.1. THE SYSTEM SHALL generate about 50 users (ops, KYC, collections agents, partner LSP, marketing, auditors, service accounts), 2,000 customers, KYC file metadata, a consent ledger, approvals and 30 normal days of events.
1.2. THE SYSTEM SHALL store only Aadhaar last-4 and a fake PAN, mark all data SAMPLE, and upload 200 sample KYC files stamped SAMPLE.
1.3. THE SYSTEM SHALL run baselines after seeding and give every scenario its own user.

### R2. Scenarios and simulator

2.1. THE SYSTEM SHALL provide `simulator/scenarios/SC-01.json` to `SC-10.json` plus SC-01b with relative timestamps, expected score and expected level matching the playbook table.
2.2. WHEN POST /simulate runs THE SYSTEM SHALL rewrite timestamps to now and batch put-events; WHEN reset runs it SHALL clear Alerts and Counters for scenario users.

### R3. API

3.1. THE SYSTEM SHALL implement every read endpoint in `contract/openapi.yaml` and validate each response against it, with the `{data, error}` envelope.

### R4. Accuracy

4.1. WHEN POST /accuracy/run is called THE SYSTEM SHALL reset, replay each scenario and 7 normal days, and write `AccuracyRuns` with expected and actual level and score, time to alert and false alerts.
4.2. THE SYSTEM SHALL show 11 of 11 passing and 0 false alerts.

### R5. Real mode

5.1. THE SYSTEM SHALL provide `scripts/real_mode.py`: the demo user downloads 200 KYC files with boto3 and copies them to `finshield-dev-external-sim`.

## Done when

The Accuracy panel shows 11 of 11 (10 scenarios plus SC-01b) and 0 false alerts.
