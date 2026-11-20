# Design: M8 Compliance, pitch and demo

## Overview

Documents only: `docs/compliance-map.md`, `docs/demo-script.md`, `docs/architecture.png`, regulation summaries (markdown) for the rules bucket, deck outline and Q&A sheet.

## Components

| Component | Responsibility |
| --- | --- |
| compliance-map.md | Obligation, control, evidence, screen, clause-to-verify flag |
| regulation summaries | One file per regulation; source for M5 prompts |
| demo-script.md | Follows the 8-step timing in the playbook; fallbacks per step |
| deck | Problem and 3 deadlines, who we protect, modules, architecture, live demo, rules and accuracy, compliance map, business case |

## Contract touchpoints

- Config: `contract/config.json` (the only place for scoring points, thresholds and deadlines).
- Schemas: `contract/schemas/*.schema.json`; fixtures: `contract/fixtures/`.
- API: `contract/openapi.yaml`.
- Settings: SSM `/finshield/dev/`; table names and ARNs from environment variables set by `infra/template.yaml`.

## Notes and open points

- All sample data is synthetic and marked SAMPLE.
- The `GET /compliance` response uses status IN_PLACE, GAP, NOT_APPLICABLE or UNKNOWN, never a compliance claim.
