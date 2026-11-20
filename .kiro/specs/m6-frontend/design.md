# Design: M6 Frontend (Next.js admin portal)

## Overview

Existing Next.js app in `web/`, TypeScript, static export. `web/lib/api.ts` is a typed client, one method per `operationId`, with an in-memory mock for approve and release. `scripts/write-env.sh` writes `web/.env.local`.

## Components

| Component | Responsibility |
| --- | --- |
| lib/api.ts | Typed client, envelope unwrapping, `setTokenProvider`, `can.*` role helpers |
| next.config.mjs | `output: 'export'`, `images.unoptimized`, `experimental.externalDir` for fixture imports |
| Screens | Overview, Alerts, Alert detail, Simulator, Accuracy, Privacy, Compliance, Rules, Approvals, Architecture |
| Auth | amazon-cognito-identity-js or aws-amplify Auth reading ids from env |

## Contract touchpoints

- Config: `contract/config.json` (the only place for scoring points, thresholds and deadlines).
- Schemas: `contract/schemas/*.schema.json`; fixtures: `contract/fixtures/`.
- API: `contract/openapi.yaml`.
- Settings: SSM `/finshield/dev/`; table names and ARNs from environment variables set by `infra/template.yaml`.

## Notes and open points

- `web/` held no Next.js app when M1 set up the repo (no package.json). M6 must add the portal, then confirm it uses no API routes, middleware or server actions; if it does, stop and host on Amplify.
- Countdowns compute from `due_at`, not from `seconds_remaining`.
