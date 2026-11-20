# Requirements: M5 AI layer (Bedrock)

Owner: M5. Needs from: M8 regulation texts, M3 alert shape. Gives to: AI JSON on each alert, four report drafts.

Steering: `.kiro/steering/*`. Contract: `contract/` (config.json, schemas, openapi.yaml, fixtures). Playbook: `docs/playbook.md`. Contract changes go to `contract/CHANGES.md`, never silently.

## User story

As the AI owner, I want Bedrock to write the explanation and report drafts from masked facts, so analysts get words while code keeps every number.

## Requirements

### R1. Explanation

1.1. WHEN an alert needs an explanation THE SYSTEM SHALL send masked facts (pseudonymous user, counts, signals, data classes, regulation text) to Bedrock Converse at temperature 0 with the Guardrail applied.
1.2. THE SYSTEM SHALL require output that validates against `ai_explanation.schema.json` and whose `numbers_used` equals the alert's computed facts.
1.3. WHEN validation fails twice, Bedrock times out (8 s budget) or is unavailable THE SYSTEM SHALL write a template explanation from the same facts and set `ai_status=FALLBACK`.

### R2. Masking and Guardrail

2.1. THE SYSTEM SHALL send no names, Aadhaar or PAN to Bedrock and SHALL flag any in the output.
2.2. THE SYSTEM SHALL configure a Guardrail with PII filters plus regexes for Aadhaar `\b\d{4}\s?\d{4}\s?\d{4}\b` and PAN `[A-Z]{5}[0-9]{4}[A-Z]`.

### R3. Reports

3.1. THE SYSTEM SHALL draft an RBI incident report, a CERT-In form, a Data Protection Board notice and a customer notice, each citing clauses present in the M8 summaries, and save them to the Reports table.
3.2. THE SYSTEM SHALL use the Knowledge Base when `kb_id` is set, otherwise inject the regulation summaries into the prompt.

### R4. Ask and labelling

4.1. WHEN an analyst asks a question THE SYSTEM SHALL answer only from the given case.
4.2. WHEN a KYC file is uploaded THE SYSTEM SHALL label the document type and flag a visible 12-digit Aadhaar, emitting a privacy event.

### R5. Wording

5.1. THE SYSTEM SHALL use the phrase "DPDP-aligned readiness and controls" and the term "consent ledger" in all generated text.

## Done when

SC-01 shows a valid, number-checked explanation in under 8 s, and the fallback works with Bedrock switched off.
