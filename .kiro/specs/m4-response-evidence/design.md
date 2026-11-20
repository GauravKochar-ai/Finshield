# Design: M4 Response workflow and evidence

## Overview

`backend/statemachines/incident.asl.json` (skeleton written by M1, M4 owns it) orchestrates Lambdas listed in the template. `finshield.evidence` implements `hash_n = SHA-256(hash_(n-1) + canonical_json(entry_n without hash))`, entry 1 chained from `GENESIS:<alert_id>`.

## Components

| Component | Responsibility |
| --- | --- |
| incident.asl.json | Evidence, deadlines, severity Choice, Critical Parallel (containment || AI), async reports, SNS, approval wait, quarantine or reject, close, export |
| contain_* Lambdas | Read `containment_mode` from SSM; write their own evidence |
| decision | Stores the task token (STORE_TOKEN) and sends success or failure from POST /decision |
| quarantine / release | Quarantine policy and console off; release undoes all four containments |
| evidence | append, verify, export to the Object Lock bucket |
| tamper_demo | Edits a copy and runs verify; read-only on the Evidence table |

## Contract touchpoints

- Config: `contract/config.json` (the only place for scoring points, thresholds and deadlines).
- Schemas: `contract/schemas/*.schema.json`; fixtures: `contract/fixtures/`.
- API: `contract/openapi.yaml`.
- Settings: SSM `/finshield/dev/`; table names and ARNs from environment variables set by `infra/template.yaml`.

## Notes and open points

- The skeleton passes `mode` from the `ContainmentMode` stack parameter; Lambdas should prefer the live SSM value so the mode can change without a deploy.
- Duplicate execution starts fail harmlessly because the name repeats.
- No role has UpdateItem or DeleteItem on Evidence; `ddb.update_item` refuses the table.
