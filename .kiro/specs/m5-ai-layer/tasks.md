# Tasks: M5 AI layer (Bedrock)

P0 carries the mandatory demo, P1 the other scenarios and judging points, P2 depth. Do not start P1 until P0 passes its checkpoint.

## P0

- [ ] P0.1 `ai_explain` with masked facts, schema and `numbers_used` check, 8 s budget, template fallback
- [x] P0.2 Guardrail with PII filters and Aadhaar and PAN regexes (resource defined in the template)
- [ ] P0.3 Test on `contract/fixtures/alert_sc01.json`; show fallback with Bedrock off

## P1

- [ ] P1.1 `ai_reports`: four drafts citing M8 clauses, saved to Reports
- [ ] P1.2 Knowledge Base over `finshield-dev-rules`, or prompt injection when `kb_id` is NONE
- [ ] P1.3 `ask` limited to the given case

## P2

- [ ] P2.1 `kyc_label` with Aadhaar flag and privacy event
