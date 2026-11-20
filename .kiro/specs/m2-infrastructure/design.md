# Design: M2 Infrastructure (SAM)

## Overview

One SAM template (`infra/template.yaml`) plus `infra/samconfig.toml` (stage=dev, ap-south-1). `make build` assembles `build/layer` (finshield package, contract data, arm64 dependencies) and runs `sam build`. All 21 Lambdas start as stubs from `finshield.stub`; the stub returns the matching contract fixture for HTTP calls, so the web app works on the live API from the first deploy.

## Components

| Component | Responsibility |
| --- | --- |
| Layer `finshield-dev-shared` | `backend/shared/python/finshield` + `contract/` data + jsonschema |
| Bus and rules | `finshield-dev-bus`; forward rules on the default bus (KYC S3 calls, identity calls, GuardDuty, Config) |
| Tables | 13 tables, env vars `TABLE_<UPPER>` injected through Globals |
| Buckets | kyc-docs, raw-events, rules, evidence (Object Lock), web, plus external-sim, trail and optional config buckets |
| State machine | `finshield-dev-incident` from `backend/statemachines/incident.asl.json` with DefinitionSubstitutions |
| IAM | SAM policy templates per function; Evidence gets a PutItem/GetItem/Query statement only |
| Edge | HTTP API (default stage, routes carry `/v1`), Cognito, CloudFront + OAC, KMS key, Bedrock Guardrail |
| Monitoring | CloudWatch dashboard and alarm on `FinShield/TimeToDetectMs` |

## Contract touchpoints

- Config: `contract/config.json` (the only place for scoring points, thresholds and deadlines).
- Schemas: `contract/schemas/*.schema.json`; fixtures: `contract/fixtures/`.
- API: `contract/openapi.yaml`.
- Settings: SSM `/finshield/dev/`; table names and ARNs from environment variables set by `infra/template.yaml`.

## Notes and open points

- Function ARNs inside Lambda environments are built from names (not `GetAtt`) to avoid a cycle with the state machine.
- SSM cannot hold an empty value, so `kb_id` is `NONE` when no Knowledge Base exists.
- Bucket names are fixed by the contract and are globally unique; a name clash fails the deploy.
- Group checks (`cognito:groups`) happen in handlers; the JWT authorizer only checks the token.
