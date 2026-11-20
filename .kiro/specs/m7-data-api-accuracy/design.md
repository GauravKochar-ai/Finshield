# Design: M7 Data, simulator, API and accuracy

## Overview

`simulator/seed/generate.py` builds data for every table; `scripts/seed.sh` loads it. Lambdas `simulator`, `test_runner` and `api` replace their stubs; responses are checked against the OpenAPI schemas in tests.

## Components

| Component | Responsibility |
| --- | --- |
| generate.py | Deterministic seeds, per-scenario users with per-user baselines |
| scenarios | One JSON file each: events with `offset_seconds`, `expected_score`, `expected_level` |
| simulator | Timestamp rewrite, batching, reset |
| api | All read routes plus approvals |
| test_runner | Replay, poll Alerts, write AccuracyRuns |
| real_mode.py | Real CloudTrail path, reports the CloudTrail delay |

## Contract touchpoints

- Config: `contract/config.json` (the only place for scoring points, thresholds and deadlines).
- Schemas: `contract/schemas/*.schema.json`; fixtures: `contract/fixtures/`.
- API: `contract/openapi.yaml`.
- Settings: SSM `/finshield/dev/`; table names and ARNs from environment variables set by `infra/template.yaml`.

## Notes and open points

- Open point OPEN-1 in `contract/CHANGES.md`: seed per-user `p95_15min` so SC-01 (106x), SC-04, SC-05 and SC-10 land in the intended S1 tiers.
- `backend/tests/test_contract.py` already validates the `api_*` fixtures against `openapi.yaml`; reuse its approach for live responses.
