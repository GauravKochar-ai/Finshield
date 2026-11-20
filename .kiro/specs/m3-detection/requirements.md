# Requirements: M3 Detection pipeline

Owner: M3. Needs from: M2 tables and bus, M7 seed data. Gives to: Alerts in DynamoDB and `Alert Raised` events.

Steering: `.kiro/steering/*`. Contract: `contract/` (config.json, schemas, openapi.yaml, fixtures). Playbook: `docs/playbook.md`. Contract changes go to `contract/CHANGES.md`, never silently.

## User story

As the detection owner, I want raw activity turned into unified events and scored into one alert per user per window, so the mandatory demo produces exactly one CRITICAL alert scoring 96.

## Requirements

### R1. Normalizer

1.1. WHEN a CloudTrail GetObject on the KYC bucket arrives THE SYSTEM SHALL emit a DOWNLOAD event with `object_id` taken from the key.
1.2. THE SYSTEM SHALL map ConsoleLogin to LOGIN, AssumeRole to ASSUME_ROLE, StopLogging or DeleteTrail to LOGGING_CHANGE, and map GuardDuty and Config findings to their actions.
1.3. WHEN an `event_id` was already processed THE SYSTEM SHALL ignore it (idempotent).
1.4. THE SYSTEM SHALL archive the raw record to the raw-events bucket and emit a `Normalized Event` that validates against `event.schema.json`.

### R2. Scoring

2.1. THE SYSTEM SHALL read every point value, threshold and window only from `contract/config.json`.
2.2. THE SYSTEM SHALL compute signs S1 to S8 (P0) and S9 to S11 (P1), apply exceptions E1 to E3, cap the score at 100 and derive severity from the thresholds.
2.3. THE SYSTEM SHALL record each signal with the facts that triggered it.

### R3. Incident dedup

3.1. THE SYSTEM SHALL keep one open alert per `user_id` per 60-minute window using a conditional write.
3.2. WHEN the severity rises THE SYSTEM SHALL emit exactly one `Alert Raised` event for that step; otherwise it SHALL emit none.

### R4. Baselines

4.1. THE SYSTEM SHALL compute per-user and per-team baselines hourly and on demand after seeding.
4.2. WHILE a user has less than 14 days of history THE SYSTEM SHALL use the team baseline.

### R5. Accuracy

5.1. WHEN each scenario in `simulator/scenarios` is replayed THE SYSTEM SHALL produce the expected score and level, with SC-01 scoring 96 CRITICAL in under 60 s on AWS.

## Done when

All 10 scenarios produce their expected level in tests and SC-01 gives one alert in under 60 s on AWS.
