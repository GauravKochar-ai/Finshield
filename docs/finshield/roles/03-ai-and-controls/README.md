# 03 AI and controls

## Role and purpose

This role makes the AI part safe and checkable. It masks what is sent to the AI, checks that explanations cite real evidence, maps alerts to compliance review wording, provides a fallback when the AI is unavailable, runs reviewer-approved simulated actions, and designs the blind tests.

## Owner and contributors

Owner: Unassigned
Contributors: none yet

## What I own

- AI_Investigator: masked AI input, evidence-based explanations, the citation check, the legal-finding phrase list (D-13).
- Compliance mapping: "DPDP-aligned readiness and controls" wording. Mappings are labelled "needs official verification". Alerts never state that a breach has happened.
- Fallback summary template (four parts) and the live or fallback label.
- Response_Controller: simulated actions that only run after reviewer approval.
- Blind test design (T4.1) and the judge walkthrough rehearsal (T4.11).

## What I need from other roles

- From 02 (T2.6): real incidents from Incident_Manager. Workaround: use the one sample incident file with evidence IDs (T1.9), based on the P1 incident in [contracts.md](../../contracts.md).
- From 05 (T1.10): AWS sandbox status for Bedrock. Workaround: the fallback path needs no AWS, so build and measure that first.
- From 01 (T4.2): the evaluation harness for citation accuracy. Workaround: run the check on a hand-picked set of sample incidents and label it fallback only.

## What I provide to other roles

- Masking and citation check to 05 for the local API server (T1.9).
- Explanations and actions to 04 for the Investigate button and approval screens (T2.9, T2.8).
- Blind test set and results inputs to 05 (T4.1, then T4.3).
- Compliance wording and the legal phrase list to 04 for the wording check (T3.10).

## First task I can start today

T1.9, build AI pieces against one sample incident. It depends on T1.1 and T1.3, but you can start from the explanation example in [contracts.md](../../contracts.md) and write the masking function and citation check as plain functions with no repo tooling.

## Task checklist with shared task IDs

Master list: [tasks.md](../../../../.kiro/specs/finshield-ai/tasks.md)

- [ ] T1.9 Build AI pieces against one sample incident
- [ ]* T1.14 Property test: AI citations are a subset of the evidence trail
- [ ]* T1.15 Property test: masking blocks identifiers
- [ ] T2.8 Implement Response_Controller
- [ ] T2.9 Implement AI_Investigator core on real incidents
- [ ]* T2.28 Property test: approvals answer matches the lookup state
- [ ]* T2.29 Property test: AI explanation does not change detection state
- [ ]* T2.30 Property test: response actions follow the approval state machine
- [ ] T3.7 Add verification request and per-scenario actions
- [ ] T4.1 Design blind tests
- [ ] T4.4 Measure AI citation accuracy
- [ ]* T4.5 Integrate live Bedrock path
- [ ] T4.11 Rehearse the judge walkthrough

Items marked `*` are optional.

## Files or components I expect to change

- AI_Investigator, masking function, citation check, legal phrase list
- Fallback summary template
- Response_Controller and its state machine
- Blind test set under `docs/finshield`

## Example input and expected output

Input: the sample incident `inc-p1-evt-002` (actor `acct-admin-07`, 300 files, 180 customers) and one AI answer citing evidence IDs.

| Check | Input | Expected result |
|---|---|---|
| Masking | Payload for `inc-p1-evt-002` | No actor name, customer ID or incident ID left in the payload |
| Citation | Answer cites `ev-999` (not in the trail) | Rejected, `failed_checks` includes `evidence_ids`, labelled fallback shown |
| Wording | Answer says "this is a legal breach" | Rejected, `failed_checks` includes `legal_findings` |
| Action | Reviewer approves "request verification" | Status `simulated`, reviewer, action, incident and UTC time recorded |

Shapes: [contracts.md](../../contracts.md#ai-explanation) and [contracts.md](../../contracts.md#reviewer-action). Scenario facts: [scenarios.md](../../scenarios.md).

## How I test my work

- Unit tests for masking, citation check, fallback and the action state machine. All run with no AWS.
- A blocked masking attempt must send nothing to the model.
- Compare the incident before and after an explanation. They must be identical.
- Blind tests are written from [scenarios.md](../../scenarios.md) thresholds only, without reading rule code.

## What I must demonstrate before handoff

- Masking leaves no actor name, customer ID or incident ID in the payload, and the citation check rejects an unknown evidence ID, a wrong customer count and a legal phrase.
- The approvals question gives the exact wording for each lookup outcome (found, empty, unavailable).
- Pending and rejected actions are never simulated, and nothing calls a real system.
- Compliance mappings carry "needs official verification" and use "potential" or "may require review" wording.

## Open decisions and blockers

- [D-04 Bedrock model and AWS Region](../../decisions.md#d-04)
- [D-05 Placeholders or real synthetic IDs inside AI answers](../../decisions.md#d-05)
- [D-07 Reviewer identity in the demo](../../decisions.md#d-07)
- [D-13 Owner of the legal-finding phrase list](../../decisions.md#d-13)
- [D-14 Response actions limited to two simulated types](../../decisions.md#d-14)
- Blocker: Bedrock access is unknown until T1.10 records it. T4.5 is skipped if blocked.

## Links to additional Markdown files for this role

No role notes yet. Add topic files in this folder (for example the legal phrase list or blind test notes) and link them here, one line each.
