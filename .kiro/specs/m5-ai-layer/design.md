# Design: M5 AI layer (Bedrock)

## Overview

Lambdas `ai_explain`, `ai_reports`, `ask`, `kyc_label` use `finshield.bedrock.converse` (guardrail required, hard timeout, masked input) and `finshield.schema.validate`. Prompts live in `backend/functions/<name>/prompts/`. Model id, guardrail id and version come from SSM.

## Components

| Component | Responsibility |
| --- | --- |
| ai_explain | build_facts, call, schema check, numbers check, one retry, template fallback |
| ai_reports | Four prompts; saves to Reports; invoked asynchronously by the state machine |
| ask | Case-scoped Q&A over the alert and evidence |
| kyc_label | Bedrock image input on S3 upload (P2) |
| Guardrail | `AWS::Bedrock::Guardrail` in the template, version exposed through SSM |

## Contract touchpoints

- Config: `contract/config.json` (the only place for scoring points, thresholds and deadlines).
- Schemas: `contract/schemas/*.schema.json`; fixtures: `contract/fixtures/`.
- API: `contract/openapi.yaml`.
- Settings: SSM `/finshield/dev/`; table names and ARNs from environment variables set by `infra/template.yaml`.

## Notes and open points

- `BedrockModelId=NONE` makes every call fall back, which is the Bedrock-off test.
- `finshield.bedrock.mask_text` is a last-line regex mask, not a replacement for masking facts before the call.
