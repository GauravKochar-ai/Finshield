# Design: M3 Detection pipeline

## Overview

`normalizer` and `detection` Lambdas in `backend/functions/`, tested with moto against the scenario files. Detection updates `Counters` with atomic ADD (15-minute and daily buckets), evaluates signs with pure functions that take (events, counters, baseline, config), then upserts the open alert.

## Components

| Component | Responsibility |
| --- | --- |
| normalizer | Raw Activity / CloudTrail / GuardDuty / Config to unified event; dedup by `event_id` with `put_if_absent` |
| detection | Counters, signs, exceptions, dedup, `Alert Raised` through `finshield.events.put_event` |
| baseline | Hourly schedule; writes `Baselines` |
| scoring module | Pure functions per sign so each scenario can be unit-tested without AWS |

## Contract touchpoints

- Config: `contract/config.json` (the only place for scoring points, thresholds and deadlines).
- Schemas: `contract/schemas/*.schema.json`; fixtures: `contract/fixtures/`.
- API: `contract/openapi.yaml`.
- Settings: SSM `/finshield/dev/`; table names and ARNs from environment variables set by `infra/template.yaml`.

## Notes and open points

- Open point OPEN-1 in `contract/CHANGES.md`: the S1 divisor floor. `config.json` currently has `baseline_floor = 1`; seed per-user p95 values so SC-01 gives 212 / 2 = 106x.
- PRESIGN leaves no CloudTrail record, so it only comes from app events.
- Exceptions: E1 cap 30; E2 cap 30, void above +20% (then +10); E3 ignores self-approval.
