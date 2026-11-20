# Implementation Plan: FinShield AI

## Overview

This is the master checklist for FinShield AI. It describes future work. No application code is written as part of this deliverable. The design uses Python for the backend core and React for the dashboard (R20.4), so no language question is needed. Open decisions D-01 to D-13 in [design.md](design.md) use their recommended defaults. Requirements are in [requirements.md](requirements.md).

Related files (written in a later phase, links resolve once they exist):
[README.md](../../../docs/finshield/README.md), [roles/](../../../docs/finshield/roles/), [scenarios.md](../../../docs/finshield/scenarios.md), [contracts.md](../../../docs/finshield/contracts.md), [demo-and-evaluation.md](../../../docs/finshield/demo-and-evaluation.md), [decisions.md](../../../docs/finshield/decisions.md).

### Task ID scheme (stable, do not renumber)

- Format: `M<milestone>-<two digits>`, for example `T2.5`. IDs are never reused or renumbered. If a task is dropped, mark it dropped in place. New tasks get the next free number in their milestone.
- Role files in `docs/finshield/roles/` link back to tasks by ID.
- Every task has one accountable role, its dependencies, a concrete output, a "done when" check, and requirement IDs (R19.5).
- Person name for every task is `Unassigned` until the team assigns people.

### Roles

| Role | Short name | Owns |
|---|---|---|
| 01 Data and replay | 01 | Synthetic data, baselines, Replay_Engine, scenarios.md, evaluation harness |
| 02 Detection and backend | 02 | Contract, Intake_Service, Detection_Engine, Incident_Manager |
| 03 AI and controls | 03 | AI_Investigator, Response_Controller, masking, citation check, blind test design |
| 04 Dashboard and workflow | 04 | React Dashboard, analyst and lead workflow, final acceptance tests |
| 05 Platform and integration | 05 | Repo setup, Evidence_Store, local API server, AWS checks and path, integration tests |

Integration tests are owned by role 05 (T2.15, T3.11, T4.9). Final acceptance tests are owned by role 04 (T4.10).

### Milestone summary

| Milestone | Goal | Demo at the end |
|---|---|---|
| M1 | Agree the shared contract and sample fixtures | Frontend renders an example response, detection passes fixture files, AI passes a sample incident, all without AWS |
| M2 | Complete P1 end to end | One replay creates one Critical incident, updates to 300 files, shows evidence, records a reviewer decision |
| M3 | Add P2, P3, normal comparison cases, and the edge case | Registry upload and auditor export stay quiet, credit team 15 files late at night shows its explanation, all through the same pipeline |
| M4 | Integrate live AI if the sandbox permits, evaluate, rehearse, document status | Measured results, rehearsed judge walkthrough, recorded deployment status |

### Parallel work after contract agreement (after T1.2)

Nobody waits for the backend developer. Each role builds against a fixed stand-in until the real part exists.

| Role | Builds against | First tasks | Swaps to the real part at |
|---|---|---|---|
| 01 Data and replay | Contract v1.0 and its fixture schema | T1.5, T1.6, then T2.3 | T2.4 (real intake and store) |
| 02 Detection and backend | Fixture files read directly from disk, no storage | T1.8, then T2.1, T2.5 | T2.6 (real Evidence_Store) |
| 03 AI and controls | One sample incident file with evidence IDs | T1.9, then T2.8, T2.9 | T2.9 (real incident from Incident_Manager) |
| 04 Dashboard and workflow | Example API responses in contracts.md | T1.7, then T2.11 | T2.11 (local API server) |
| 05 Platform and integration | Local setup, schema file, AWS sandbox checks | T1.3, T1.4, T1.10, then T2.2 | T2.7 (local API server wires the core) |

### Short handoff sequence

1. 02 publishes contract v1.0 with example responses (T1.1). All five roles review and sign it (T1.2).
2. 01 hands fixtures and expected results to 02 (T1.6) and the sample normal activity to 03 and 04.
3. 03 receives a sample incident shape from the contract and works alone until T2.6 produces real incidents.
4. 05 hands the Evidence_Store and then the local API server to 02, 03, and 04 (T2.2, T2.7). 04 switches from example responses to the API.
5. 02 hands incidents to 03 (T2.6), who hands explanations and actions to 04 (T2.9, T2.8).
6. 05 runs integration tests at each milestone end. 04 runs final acceptance tests at M4.
7. Contract changes follow R19.2: bump the version, log in decisions.md, notify all five roles before merge.

## Tasks

- [ ] 1. Agree shared contract and sample fixtures
  - Goal: frontend builds against an example response, detection uses fixture files, AI uses a sample incident, all before AWS is ready.

  - [ ] 1.1 Draft contracts.md version 1.0 with example responses
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: none
    - Output: [contracts.md](../../../docs/finshield/contracts.md) with a MAJOR.MINOR version, the event format, API payloads (run, incident list, incident detail, evidence item, compare, explanation, action), one example response per payload for P1 (80, 90, 130 documents; 300 files, 180 customers), and the provenance marker. Also the machine-readable schema file in the repo.
    - Done when: every payload has a field table and an example, and the example P1 incident response validates against the schema file.
    - _Requirements: R19.1, R2.2, R2.6, R6.11, R20.5_

  - [ ] 1.2 Review and sign off contract 1.0
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T1.1
    - Output: a decisions.md entry recording contract 1.0 sign-off by all five roles, plus the change process (version bump, log, notify) written at the top of contracts.md.
    - Done when: each of the five roles has recorded approval or a logged change request, and version 1.0 is marked agreed.
    - _Requirements: R19.1, R19.2_

  - [ ] 1.3 Set up repository skeleton and local tooling
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: none
    - Output: Python core package layout, React app shell, test tooling (pytest, Hypothesis), one command to run all tests, and a check that fails when a test or task lacks a requirement ID.
    - Done when: a fresh clone runs the empty test suite and the requirement-ID check with no cloud access. Covers AT-CORE-02.
    - _Requirements: R19.5, R20.1, R20.4_

  - [ ] 1.4 Create handoff docs skeleton and decision log
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: none
    - Output: [README.md](../../../docs/finshield/README.md), [roles/](../../../docs/finshield/roles/) guides linking back to task IDs, [decisions.md](../../../docs/finshield/decisions.md) with D-01 to D-13 and their recommended defaults and owner roles, and [demo-and-evaluation.md](../../../docs/finshield/demo-and-evaluation.md) listing the acceptance test IDs from the Traceability table.
    - Done when: every D-01 to D-13 entry has an owner role, a default, and a status, and every acceptance test ID in requirements.md appears in demo-and-evaluation.md.
    - _Requirements: R19.2, R19.5, R3.7_

  - [ ] 1.5 Write scenarios.md with data, numbers, and expected results
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T1.1
    - Output: [scenarios.md](../../../docs/finshield/scenarios.md) covering P1, P2, P3, the P1 approval and upload variations, the registry upload, the auditor export cases, the credit team 15-file late-night case, and the generator profiles. Each case lists input events, expected alert or none, severity, and expected dashboard content.
    - Done when: each case has all three expected fields, and the late-night and weak-evidence expected results are derived from a written rule.
    - _Requirements: R12.7, R6.3, R9.13, R10.1, R3.5, R1.1_

  - [ ] 1.6 Create sample fixtures and expected outputs
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T1.1, T1.3
    - Output: fixture files for P1 events (80 at 10:00, 90 at 10:02, 130 at 10:04, document and customer IDs, 300 files, 180 customers), a small normal-activity file for the admin account (5 to 10 documents per five minutes), reference data (privileged flag, approvals, empty approvals), and an expected-results file for each.
    - Done when: fixtures validate against the contract schema, every record is marked synthetic, and the expected-results file states no alert at 80, Critical at 170, and 300 at the third event.
    - _Requirements: R6.3, R6.4, R6.5, R6.6, R3.5, R1.5, R18.6_

  - [ ] 1.7 Build dashboard shell against example responses
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T1.1, T1.3
    - Output: React incident list and incident detail reading the example responses from contracts.md. Shows severity, scenario, actor, files and distinct customers as two figures, conditions with value seen, limit, and result, missing evidence or "none missing", and the run ID.
    - Done when: the app builds and renders the P1 example with no backend running, and files and customers appear as two separately labelled numbers.
    - _Requirements: R16.1, R16.2, R16.3, R16.4, R16.7_

  - [ ] 1.8 Implement P1 rule core against fixture files
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T1.6, T1.3
    - Output: pure functions for the event-time rolling window, the volume, multiple-of-normal, and privileged conditions, condition results (value seen, limit, state), and the P1 decision table, reading fixture files directly with no storage. Configurable thresholds with defaults.
    - Done when: the fixture run gives no alert at 80, a Critical decision at 170 with all conditions shown, and a Critical decision at 300. Limit 100 does not trigger at 100 and triggers at 101.
    - _Requirements: R5.1, R5.2, R5.3, R5.6, R5.8, R6.1, R6.2, R6.3, R6.4_

  - [ ] 1.9 Build AI pieces against one sample incident
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T1.1, T1.3
    - Output: one sample incident file with evidence IDs, the masking function and masking check, the fallback summary template with four parts, the citation check, and the legal-finding phrase list (D-13 owner: this role).
    - Done when: masking leaves no actor name, customer ID, or incident ID in the payload, a blocked masking attempt sends nothing, and the citation check rejects an unknown evidence ID, a wrong customer count, and a legal phrase. All run with no AWS.
    - _Requirements: R13.2, R13.3, R13.4, R13.5, R18.4, R18.7, R18.8_

  - [ ] 1.10 Check AWS sandbox access and record status
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: none
    - Output: a dated note in decisions.md covering sandbox account access, Region, whether API Gateway, Lambda, and DynamoDB can be created, and which Bedrock models are available (D-04 needs official verification). Also the D-06 hosting default (run the React app locally).
    - Done when: each of the four AWS services is marked "available", "blocked", or "not checked" with a date and method.
    - _Requirements: R20.2, R20.7_

  - [ ]* 1.11 Property test: rolling window membership
    - **Property 5: Rolling window membership**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T1.8
    - Output: one Hypothesis test, at least 100 examples, including an event exactly at the window edge.
    - Done when: the test passes and its tag names Property 5.
    - **Validates: Requirements 5.3, 6.1, 9.3**

  - [ ]* 1.12 Property test: volume limit boundary
    - **Property 6: Volume limit boundary**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T1.8
    - Output: one Hypothesis test with boundary values 100 and 101.
    - Done when: the test passes and its tag names Property 6.
    - **Validates: Requirements 5.8, 6.1**

  - [ ]* 1.13 Property test: multiple-of-normal boundary
    - **Property 7: Multiple-of-normal boundary**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T1.8
    - Output: one Hypothesis test with boundary values 49 and 50.
    - Done when: the test passes and its tag names Property 7.
    - **Validates: Requirements 5.8, 6.1**

  - [ ]* 1.14 Property test: AI citations are a subset of the evidence trail
    - **Property 20: AI citations are a subset of the evidence trail**
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T1.9
    - Output: one Hypothesis test with random answers, real and fake evidence IDs, random counts, and legal phrases.
    - Done when: the test passes and its tag names Property 20.
    - **Validates: Requirements 13.2, 13.3, 13.4, 13.5, 13.7**

  - [ ]* 1.15 Property test: masking blocks identifiers
    - **Property 22: Masking blocks identifiers**
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T1.9
    - Output: one Hypothesis test with random actor names, customer IDs, and incident IDs.
    - Done when: the test passes and its tag names Property 22.
    - **Validates: Requirements 13.1, 18.7, 18.8**

  - [ ] 1.16 Checkpoint: M1 demonstrated
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T1.2, T1.4, T1.5, T1.7, T1.8, T1.9, T1.10
    - Output: a short recorded demo: the dashboard renders the example response, the P1 fixture run gives the expected results, the AI sample incident passes masking and citation checks.
    - Done when: all three run on a laptop with no AWS, and all tests pass. Ensure all tests pass, ask the user if questions arise.
    - _Requirements: R19.1, R20.1, R6.4_

- [ ] 2. Complete P1 end to end
  - Goal: one replay creates one Critical alert, updates to 300 files, shows evidence, and records a reviewer decision.

  - [ ] 2.1 Implement Intake_Service
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T1.2, T1.3
    - Output: validation steps in the design order (contract version, schema with up to 50 failing fields, synthetic marker, document record fields, count match), write-only-if-absent, accepted or duplicate result, and a rejected-input area that keeps the raw copy.
    - Done when: valid events are accepted, duplicates return "duplicate", each invalid case returns the named fields and stores nothing in the run, and a count mismatch of 90 versus 89 reports both numbers.
    - _Requirements: R2.1, R2.2, R2.3, R2.4, R2.6, R2.7, R2.8, R1.5, R17.4, R19.3, R19.4, R20.6_

  - [ ] 2.2 Implement Evidence_Store repository and SQLite adapter
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T1.3
    - Output: repository interface (`put_if_absent`, `get`, `list_by_run`, `append_evidence`, `update_incident`), SQLite adapter with run-scoped keys, evidence ordering by timestamp then sequence, no update or delete path for evidence (D-01 default), and repository contract tests reusable for a DynamoDB-compatible fake.
    - Done when: contract tests pass on SQLite, reads need a run ID, and an attempt to change or delete evidence returns "evidence is immutable".
    - _Requirements: R15.1, R15.2, R15.5, R15.6, R4.3, R11.8_

  - [ ] 2.3 Implement baseline generator and builder
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T1.6
    - Output: seeded generator for at least 7 days and at least 30 samples per metric per account, baseline builder reading normal events only (min and max, D-02 default), role-level baseline, and the "fewer than 30 samples" error.
    - Done when: the P1 admin baseline is 5 to 10 documents per five minutes, adding injected events leaves the stored sample size unchanged, and 29 samples store no baseline and name account and metric.
    - _Requirements: R3.1, R3.2, R3.3, R3.4, R3.5, R3.6, R6.7_

  - [ ] 2.4 Implement Replay_Engine with run configuration
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T2.1, T2.2, T2.3
    - Output: `create_run` (run ID, copy of config and reference data, per-source "unavailable" switches, baseline build), `replay` (event-time then event-ID order), repeat replay into an existing run, file-error handling, out-of-range override rejection, and a change-one-value function that makes a new run and a compare result.
    - Done when: P1 fixtures replay with no live connection, a repeat replay leaves the incident count unchanged, a missing file starts no run, and the limit 100 to 170 change yields a second run with the first untouched.
    - _Requirements: R4.1, R4.2, R4.3, R4.4, R4.5, R4.6, R4.7, R4.8, R4.9_

  - [ ] 2.5 Implement approval matching and missing-evidence handling for P1
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T1.8, T2.2
    - Output: tri-state lookup (found, empty, unavailable), five-part approval match with the named mismatch and uncovered record count, baseline fallback to role-level then missing, `not_evaluated` conditions, High severity for missing approvals source or baseline, and re-evaluation to Critical when the source later returns no match.
    - Done when: a covering approval gives "approved activity" with no Critical alert, each mismatch (expiry, ticket, actor, operation, scope, destination) names what differed, an unavailable approvals source gives High with "approvals source" missing, and a later "no match" raises the same incident to Critical.
    - _Requirements: R6.7, R6.8, R6.9, R6.10, R7.1, R7.2, R7.3, R7.4, R7.5, R7.6, R7.7, R7.8, R7.9, R5.7_

  - [ ] 2.6 Implement Incident_Manager
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.2, T2.5
    - Output: grouping by run, scenario, actor, and the 15-minute gap, incident IDs derived from content (D-09: triggering event counts as 1), severity history, event counts, update time in UTC with milliseconds, total files and distinct customers as separate figures, evidence IDs derived from content, and one evidence item for each change.
    - Done when: P1 fixtures give no incident at 80, one Critical incident `inc-p1-evt-002` at 170, and the same incident at 300 files and 180 customers with no second incident.
    - _Requirements: R6.4, R6.5, R6.11, R11.1, R11.2, R11.3, R11.4, R11.5, R11.6, R11.7, R11.8, R15.5_

  - [ ] 2.7 Build local API server
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T2.1, T2.4, T2.6
    - Output: thin local Python server exposing the contract endpoints (create run, replay, list incidents, incident detail, evidence, compare) and calling only the shared core.
    - Done when: responses validate against the contract examples and the P1 run completes with the network disabled.
    - _Requirements: R20.1, R20.4, R20.5, R2.5, R4.7_

  - [ ] 2.8 Implement Response_Controller
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T2.2, T2.6
    - Output: 1 to 10 proposed simulated actions per incident (suspend account, request verification), state machine (pending approval, approved, rejected, simulated), reviewer identity from the two demo users (D-07), unauthorised and not-pending refusals, failed-write handling, and evidence items for each decision.
    - Done when: approving records reviewer, action, incident, and UTC timestamp, pending and rejected actions are never simulated, and nothing calls a real system.
    - _Requirements: R14.1, R14.2, R14.3, R14.4, R14.5, R14.6, R14.7, R14.8_

  - [ ] 2.9 Implement AI_Investigator core on real incidents
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T1.9, T2.6
    - Output: investigation flow (build facts, mask, masking check, validate, record `live` or `fallback`), the approvals question answers for `empty` and `unavailable`, the fallback used by default on the local path, and no write access to severity or alert state.
    - Done when: the incident after an explanation is identical to before it, a rejected answer shows the labelled fallback with the reason recorded, and the approvals question gives the exact wording for each lookup outcome.
    - _Requirements: R13.1, R13.2, R13.3, R13.4, R13.5, R13.6, R13.7, R13.8, R13.9, R13.10, R17.5, R18.7, R18.8_

  - [ ] 2.10 Implement evidence source retrieval and export
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T2.7
    - Output: endpoint for an evidence item's source event or record, and an export file with every item in order (ID, type, timestamp, source reference). Failure leaves evidence unchanged.
    - Done when: an export of a P1 run lists all items in order, an unretrievable source returns an error that keeps the item ID, and a failed export changes nothing.
    - _Requirements: R15.3, R15.4, R15.7, R15.8_

  - [ ] 2.11 Wire dashboard to the local API
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T1.7, T2.7
    - Output: the incident list (up to 100, newest first), incident detail, conditions, two count figures, missing evidence, and run ID reading from the API instead of example responses.
    - Done when: the P1 replay shows one Critical incident, then 300 files and 180 customers after the third export, with no code changes between the example and the API.
    - _Requirements: R16.1, R16.2, R16.3, R16.4, R16.7, R6.4, R6.5_

  - [ ] 2.12 Add evidence trail view and export to the dashboard
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T2.10, T2.11
    - Output: evidence trail with ordered items, source view on select, "source unavailable" with item ID, and an export action with error display.
    - Done when: selecting an evidence item shows its source, an unreachable source keeps the item visible with its ID, and export downloads the ordered file.
    - _Requirements: R15.1, R15.3, R15.4, R15.7, R15.8_

  - [ ] 2.13 Add replay controls and compare view to the dashboard
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T2.4, T2.11
    - Output: scenario selector, change one value, replay, side-by-side compare with highlighted differing fields and the changed rule condition, invalid-value error that keeps the previous result, and the 60-second failure display.
    - Done when: changing the document limit from 100 to 170 shows the new incident at the third export next to the old one with the changed condition highlighted, and an invalid value shows which value is invalid.
    - _Requirements: R4.5, R4.9, R16.5, R16.6, R16.7_

  - [ ] 2.14 Add investigation and response approval to the dashboard
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T2.8, T2.9, T2.11
    - Output: Investigate button, four-part explanation with a live or fallback label and "live model unavailable" message, the approvals question, pending actions with approve and reject for the security lead, and "simulated" labels.
    - Done when: a reviewer approves an action and the dashboard shows "simulated", never "executed", and a rejected AI answer shows the labelled fallback.
    - _Requirements: R13.2, R13.5, R13.6, R13.7, R14.3, R14.6, R17.5, R1.2_

  - [ ] 2.15 Write P1 integration tests
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T2.12, T2.13, T2.14
    - Output: automated tests for AT-P1-01, AT-P1-02, AT-P1-03, AT-P1-04, AT-P1-05, AT-P1-06, AT-P1-07, AT-P1-09, AT-CORE-01, AT-AI-01, and AT-RESP-01 through the local API, using the P1 fixtures and reference-data switches.
    - Done when: the full P1 flow (replay, one Critical incident, 300 files, evidence view, AI fallback, reviewer approval recorded) passes in one command.
    - _Requirements: R6.3, R6.4, R6.5, R6.9, R6.11, R7.3, R7.8, R13.5, R14.3, R4.4_

  - [ ]* 2.16 Property test: duplicate events never change results
    - **Property 1: Duplicate events never change results**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.1, T2.6
    - Output: one Hypothesis test inserting extra copies at random positions.
    - Done when: the test passes and its tag names Property 1.
    - **Validates: Requirements 2.4, 5.5, 11.7**

  - [ ]* 2.17 Property test: runs are isolated
    - **Property 2: Runs are isolated**
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T2.2, T2.4
    - Output: one Hypothesis test with two runs sharing event IDs.
    - Done when: the test passes and its tag names Property 2.
    - **Validates: Requirements 4.3, 11.8**

  - [ ]* 2.18 Property test: replay is deterministic and repeatable
    - **Property 3: Replay is deterministic and repeatable**
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T2.4, T2.6
    - Output: one Hypothesis test comparing two runs and a repeat replay.
    - Done when: the test passes and its tag names Property 3.
    - **Validates: Requirements 4.4, 4.6, 15.5**

  - [ ]* 2.19 Property test: arrival order does not matter
    - **Property 4: Arrival order does not matter**
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T2.4, T2.6
    - Output: one Hypothesis test shuffling arrival order, including late events, with ties on event time.
    - Done when: the test passes and its tag names Property 4.
    - **Validates: Requirements 4.2, 5.3, 5.4**

  - [ ]* 2.20 Property test: P1 severity follows the decision table
    - **Property 9: P1 severity follows the decision table**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.5
    - Output: one Hypothesis test over all condition state combinations, including the High to Critical upgrade.
    - Done when: the test passes and its tag names Property 9.
    - **Validates: Requirements 6.1, 6.7, 6.8, 6.9, 6.10, 7.3**

  - [ ]* 2.21 Property test: files and distinct customers are counted separately
    - **Property 10: Files and distinct customers are counted separately**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.6
    - Output: one Hypothesis test with repeated customer IDs.
    - Done when: the test passes and its tag names Property 10.
    - **Validates: Requirements 6.11, 16.3**

  - [ ]* 2.22 Property test: approval covers an export only when everything matches
    - **Property 11: Approval covers an export only when everything matches**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.5
    - Output: one Hypothesis test changing one field at a time, and partial scopes for the uncovered count.
    - Done when: the test passes and its tag names Property 11.
    - **Validates: Requirements 7.1, 7.3, 7.4, 7.5, 7.6, 7.7**

  - [ ]* 2.23 Property test: one incident per group with correct event counts
    - **Property 15: One incident per group, with correct event counts**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.6
    - Output: one Hypothesis test over event streams with gaps around 15 minutes.
    - Done when: the test passes and its tag names Property 15.
    - **Validates: Requirements 6.4, 6.5, 9.4, 9.6, 11.1, 11.2, 11.3, 11.5, 11.6**

  - [ ]* 2.24 Property test: baseline excludes injected events and is well-formed
    - **Property 16: Baseline excludes injected events and is well-formed**
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T2.3
    - Output: one Hypothesis test mixing normal and injected events, and sample counts below 30.
    - Done when: the test passes and its tag names Property 16.
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

  - [ ]* 2.25 Property test: intake rejects invalid input and stores nothing
    - **Property 17: Intake rejects invalid input and stores nothing**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.1
    - Output: one Hypothesis test mutating valid events, run through the local adapter.
    - Done when: the test passes and its tag names Property 17.
    - **Validates: Requirements 1.5, 2.3, 2.5, 2.6, 2.7, 2.8, 17.4, 19.3, 20.6**

  - [ ]* 2.26 Property test: event serialization round trip
    - **Property 18: Event serialization round trip**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.1, T2.2
    - Output: one Hypothesis test serializing, parsing, storing, and reading back events.
    - Done when: the test passes and its tag names Property 18.
    - **Validates: Requirements 2.2, 20.5**

  - [ ]* 2.27 Property test: configuration validation keeps the last good value
    - **Property 19: Configuration validation keeps the last good value**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T2.5
    - Output: one Hypothesis test with missing, non-numeric, negative, and out-of-range values.
    - Done when: the test passes and its tag names Property 19.
    - **Validates: Requirements 4.9, 5.9, 9.5, 10.7, 10.8**

  - [ ]* 2.28 Property test: approvals answer matches the lookup state
    - **Property 21: Approvals answer matches the lookup state**
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T2.9
    - Output: one Hypothesis test over the three lookup outcomes for live answers and fallbacks.
    - Done when: the test passes and its tag names Property 21.
    - **Validates: Requirements 7.8, 13.8, 13.9**

  - [ ]* 2.29 Property test: AI explanation does not change detection state
    - **Property 23: AI explanation does not change detection state**
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T2.9
    - Output: one Hypothesis test with accepted answers, rejected answers, and Bedrock errors.
    - Done when: the test passes and its tag names Property 23.
    - **Validates: Requirements 5.1, 13.10**

  - [ ]* 2.30 Property test: response actions follow the approval state machine
    - **Property 24: Response actions follow the approval state machine**
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T2.8
    - Output: one Hypothesis test over random reviewer request sequences.
    - Done when: the test passes and its tag names Property 24.
    - **Validates: Requirements 10.5, 14.1, 14.2, 14.3, 14.4, 14.5, 14.8**

  - [ ]* 2.31 Property test: evidence is ordered and immutable
    - **Property 25: Evidence is ordered and immutable**
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T2.2
    - Output: one Hypothesis test over random record order and timestamp ties, run on SQLite and the DynamoDB-compatible fake.
    - Done when: the test passes and its tag names Property 25.
    - **Validates: Requirements 15.1, 15.2, 15.6, 15.7**

  - [ ]* 2.32 Property test: changing one value shows only caused differences
    - **Property 27: Changing one value shows only caused differences**
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T2.4
    - Output: one Hypothesis test over pairs of configurations that differ in one value.
    - Done when: the test passes and its tag names Property 27.
    - **Validates: Requirements 4.5, 16.5**

  - [ ] 2.33 Checkpoint: P1 demonstrated end to end
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T2.15
    - Output: recorded P1 demo: one replay, one Critical incident at the second export, 300 files at the third, evidence view, a reviewer decision recorded.
    - Done when: T2.15 passes and the demo runs on a laptop with the network off. Ensure all tests pass, ask the user if questions arise.
    - _Requirements: R1.3, R6.4, R6.5, R14.3, R15.3, R20.1_

- [ ] 3. Add P2, P3, normal comparison cases, and the edge case
  - Goal: P2, P3, the registry upload, the auditor export, and the credit team 15-file late-night case run through the same pipeline.

  - [ ] 3.1 Create fixtures and expected results for P2, P3, and accuracy cases
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T2.33
    - Output: P2 dataset (120 distinct unassigned records, assignments, delegations, expired delegation, empty and unavailable lookups), P3 sequences (5 failures then new device, 4 failures, 3 accounts, known device, 600 and 601 seconds), P1 upload events, registry upload, auditor export with valid and expired ticket, credit team 15-file download at night with normal volume, and expected-results files.
    - Done when: all fixtures validate against the contract, are marked synthetic, and each matches its case in scenarios.md.
    - _Requirements: R9.13, R10.1, R10.2, R10.4, R8.1, R12.1, R12.2, R12.3, R12.4, R12.5, R1.5_

  - [ ]* 3.12 Record future detection backlog entries
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: none
    - Output: backlog section in [scenarios.md](../../../docs/finshield/scenarios.md) for "possible duplicate loan payout" and "sensitive customer data sent to an unapproved destination", each with 1 to 3 sentences, required data fields, and at least one measurable promotion criterion. No code.
    - Done when: both entries exist, the duplicate definition and the reportable-event definition match R21, and no backlog detection is wired into the pipeline.
    - _Requirements: R21.1, R21.2, R21.3, R21.4, R21.5, R21.6, R21.7, R1.6_

  - [ ] 3.2 Implement P2 rule
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.1, T2.6
    - Output: access classification (assigned, delegated, unassigned, unverified) at access time, distinct unassigned count per actor per window, failed accesses ignored, default 5 customers in 30 minutes with validated ranges, High incident at the reaching access, and updates of the same incident.
    - Done when: the 120-record dataset gives one High incident with count 120, an expired delegation counts, an unavailable assignment source marks the access "unverified: assignment data missing" and does not count it, and an empty lookup counts.
    - _Requirements: R9.1, R9.2, R9.3, R9.4, R9.5, R9.6, R9.7, R9.8, R9.9, R9.10, R9.11, R9.12, R9.13_

  - [ ] 3.3 Implement P3 rule
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.1, T2.6
    - Output: per-account failure count since the last success (D-03 default), 0 to 600 seconds from the latest failure, device history lookup, High "possible account takeover" incident with ordered login sequence, device history, and event IDs, no incident for a known device or unavailable history, and validated configuration ranges.
    - Done when: five failures then a new device gives one High incident, 4 failures, 3 accounts, a known device, and 601 seconds give none, and unavailable device history gives a `not_evaluated` non-incident item.
    - _Requirements: R10.1, R10.2, R10.3, R10.4, R10.6, R10.7, R10.8_

  - [ ] 3.4 Implement P1 external upload variation
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.1, T2.6
    - Output: upload attachment to the open P1 incident when it has an export and the upload is later than the earliest export (D-08 default), one transfer label per fact, "confirmed transfer" only with receipt evidence, severity stays Critical, and an error for a closed fixture incident (D-12 default).
    - Done when: an upload requested only is "attempted upload", a receipt gives "confirmed transfer", no second incident opens, and attaching to the closed fixture incident changes nothing and shows an error.
    - _Requirements: R8.1, R8.2, R8.3, R8.4, R8.5, R8.6, R8.7_

  - [ ] 3.5 Implement accuracy cases
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.1, T2.5
    - Output: approved activity for the registry upload and the auditor export with zero alerts, standard rules for an expired or non-covering ticket with the failed check named, the credit team late-night rule (22:00 to 05:59, configurable) showing normal daily volume, 15 observed, and rule applied, and the "no Medium on weak evidence" result with a reason up to 200 characters.
    - Done when: each case matches its expected result in scenarios.md and no Medium alert appears for insufficient evidence.
    - _Requirements: R12.1, R12.2, R12.3, R12.4, R12.5, R12.6, R7.1_

  - [ ] 3.6 Add replay catalogue for all scenarios
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T3.2, T3.3, T3.5
    - Output: scenario catalogue (P1, P2, P3, registry upload, auditor export, credit team case), change-one-value on P2 and P3 thresholds, per-source "unavailable" switches for assignments and device history, and accuracy results reported apart from the three scenarios.
    - Done when: each catalogue entry replays through the same intake, detection, and incident code as P1 and the accuracy cases are counted separately from P1, P2, and P3.
    - _Requirements: R4.5, R9.5, R10.7, R12.6, R1.4, R1.7_

  - [ ] 3.7 Add verification request and per-scenario actions
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T3.3
    - Output: proposed actions per scenario, and a P3 verification request recording reviewer, account owner as recipient, and timestamp as simulated.
    - Done when: approving a P3 verification request records all three fields and nothing is simulated before approval.
    - _Requirements: R10.5, R14.1, R14.2, R14.3_

  - [ ] 3.8 Implement result state assignment in the backend
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.2, T3.3
    - Output: one state per check (successful empty result, missing evidence, invalid input, unavailable AI service, and the fifth label "completed, findings shown" from D-10), missing evidence list limited to 20 names plus omitted count, and non-incident items for unverified accesses and unavailable device history.
    - Done when: no check has two states, a missing-evidence check is never "checked, nothing found", and the P2 empty lookup is a successful empty result.
    - _Requirements: R17.1, R17.2, R17.3, R17.6, R17.7_

  - [ ] 3.9 Add P2, P3, and accuracy views to the dashboard
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T3.5, T3.7, T3.8
    - Output: P2 and P3 incident details (login sequence, device history, event IDs), non-incident items, approved activity list, the credit team panel (normal daily volume, 15 observed, rule applied), result state labels, and the missing-evidence display.
    - Done when: each scenario and accuracy case shows its expected dashboard content from scenarios.md, with approved activity visible within 5 seconds and missing evidence visibly distinct from "checked, nothing found".
    - _Requirements: R10.3, R10.6, R12.1, R12.2, R12.4, R12.5, R16.2, R17.2, R17.3, R17.6, R17.7_

  - [ ] 3.10 Add compliance wording and review action to the dashboard
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T2.33
    - Output: "DPDP-aligned readiness and controls" wording, "needs official verification" labels beside unverified mappings, "potential" and "may require review" phrasing, a "Suggest compliance review" action on mapped alerts, and a wording check over screens and exports.
    - Done when: no screen or export states a breach, violation, or non-compliance, and the review action appears within 2 seconds of opening a mapped alert.
    - _Requirements: R18.1, R18.2, R18.3, R18.4, R18.5, R20.7_

  - [ ] 3.11 Write P2, P3, and accuracy integration tests
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T3.6, T3.9, T3.10
    - Output: automated tests for AT-P2-01 to AT-P2-04, AT-P3-01 to AT-P3-04, AT-P1-08, and AT-ACC-01 through the local API.
    - Done when: all pass in one command, the three priority scenarios are counted as three, and the accuracy cases are reported separately.
    - _Requirements: R9.4, R9.13, R10.1, R10.5, R10.6, R8.1, R12.6, R1.1_

  - [ ]* 3.13 Property test: transfer labels
    - **Property 12: Transfer labels**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.4
    - Output: one Hypothesis test over random upload events, with and without receipts.
    - Done when: the test passes and its tag names Property 12.
    - **Validates: Requirements 8.2, 8.3, 8.4, 8.5, 8.6**

  - [ ]* 3.14 Property test: P2 counts distinct unassigned customers only
    - **Property 13: P2 counts distinct unassigned customers only**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.2
    - Output: one Hypothesis test over random accesses, delegations, and outcomes.
    - Done when: the test passes and its tag names Property 13.
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.7, 9.8, 9.9, 9.10**

  - [ ]* 3.15 Property test: P3 trigger boundaries
    - **Property 14: P3 trigger boundaries**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.3
    - Output: one Hypothesis test with 600 and 601 second boundaries and multi-account failures.
    - Done when: the test passes and its tag names Property 14.
    - **Validates: Requirements 10.1, 10.2, 10.4**

  - [ ]* 3.16 Property test: missing evidence is never a pass
    - **Property 8: Missing evidence is never a pass**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.2, T3.3
    - Output: one Hypothesis test over subsets of unavailable sources across P1, P2, and P3.
    - Done when: the test passes and its tag names Property 8.
    - **Validates: Requirements 5.7, 6.8, 6.9, 7.9, 9.11, 9.12, 10.6, 17.6, 17.7**

  - [ ]* 3.17 Property test: every check has exactly one result state
    - **Property 26: Every check has exactly one result state**
    - Owner: 02 Detection and backend (Unassigned)
    - Depends on: T3.8
    - Output: one Hypothesis test over check outcomes, including more than 20 missing sources.
    - Done when: the test passes and its tag names Property 26.
    - **Validates: Requirements 17.1, 17.2, 17.3, 17.5, 17.6, 17.7**

  - [ ] 3.18 Checkpoint: all scenarios and accuracy cases demonstrated
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T3.11
    - Output: recorded demo of P1, P2, P3, registry upload, auditor export, and the credit team case, each with one input change and replay.
    - Done when: T3.11 passes and every case matches scenarios.md. Ensure all tests pass, ask the user if questions arise.
    - _Requirements: R1.7, R4.5, R12.6, R20.1_

- [ ] 4. Integrate live AI if sandbox permits, evaluate, rehearse, document status
  - Goal: measured results, a rehearsed judge walkthrough, and an honest record of what is deployed.

  - [ ] 4.1 Design blind tests
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T3.18
    - Output: a blind test set under docs/finshield (cases, inputs, and sealed expected outcomes) written from [scenarios.md](../../../docs/finshield/scenarios.md) thresholds only, without reading rule code. Includes cases near each boundary, benign look-alikes, and missing-evidence cases.
    - Done when: decisions.md records the designer and shows they did not author the rules (not 01 or 02 for the rule being tested), and expected outcomes are committed before any blind run.
    - _Requirements: R12.7, R12.6, R5.8, R19.5_

  - [ ] 4.2 Build evaluation harness
    - Owner: 01 Data and replay (Unassigned)
    - Depends on: T3.18
    - Output: a harness that replays a case set and reports correct alerts, false alarms, missed cases, and time to alert (event time from first relevant event to alert, and wall-clock time of the replay), with counts per scenario and accuracy cases reported separately.
    - Done when: running it on the M1 to M3 fixtures reproduces their expected results and prints all four measures plus the method and date.
    - _Requirements: R4.4, R12.6, R20.7_

  - [ ] 4.3 Run blind tests and record results
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T4.1, T4.2
    - Output: results table (correct alerts, false alarms, missed cases, time to alert) from the blind set, with date, method, and each miss or false alarm explained. No rule or threshold is tuned on the blind set. Fixes go to decisions.md first.
    - Done when: the table is committed, each figure carries its date and method, and any figure not from a run is labelled "proposed, not measured".
    - _Requirements: R20.7, R12.6, R5.2, R19.2_

  - [ ] 4.4 Measure AI citation accuracy
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T4.2
    - Output: for a fixed incident set, the share of answers (live if T4.5 is done, otherwise fallback only and labelled so) whose cited evidence IDs all exist, with counts of rejections by reason and the method and date.
    - Done when: the result states how many answers were live and how many were fallback, and no live figure is claimed when no live call was made.
    - _Requirements: R13.3, R13.4, R13.5, R13.7, R20.7_

  - [ ]* 4.5 Integrate live Bedrock path
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T1.10, T3.18
    - Output: Bedrock adapter behind the investigator using the D-04 model and Region, 10-second limit, error and timeout fallback, and a masked-facts-only request. Skip if T1.10 recorded Bedrock as blocked. Record the skip in decisions.md.
    - Done when: one live explanation for P1 passes the citation check with masked facts only and is recorded `live`, a forced timeout shows the labelled fallback, and the local path still makes zero cloud requests by default.
    - _Requirements: R13.1, R13.6, R13.7, R17.5, R18.7, R18.8, R20.1, R20.2_

  - [ ]* 4.6 Build AWS path adapters
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T1.10, T3.18
    - Output: DynamoDB adapter with conditional writes, Lambda handlers for intake, replay, incidents, investigate, and respond, and API Gateway routes. Dashboard runs locally against the API Gateway URL (D-06). Skip if T1.10 recorded the services as blocked. Record the skip in decisions.md.
    - Done when: the repository contract tests pass on DynamoDB, the P1 round trip runs through API Gateway, Lambda, and DynamoDB, and the same event gives the same validation result as the local path.
    - _Requirements: R20.2, R20.5, R2.5, R2.4_

  - [ ] 4.7 Run business-value experiment
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T4.3
    - Output: a written protocol and recorded results comparing time and steps for an analyst to reach an evidence-backed conclusion on P1, P2, and P3 using raw synthetic event files versus the dashboard. States the number of participants, the method, and the date. Any time or cost saving is labelled "proposed, not measured" until recorded.
    - Done when: results are committed with method and date, and every business-value claim in the demo script points to a recorded result or carries the "proposed, not measured" label.
    - _Requirements: R20.7, R16.2, R1.2_

  - [ ] 4.8 Measure timing targets
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T3.18
    - Output: timed example runs for intake (500 ms), run creation (2 s), evidence view (2 s), lookups and incident updates (5 s), AI (10 s), export (30 s for up to 10,000 items), and replay (60 s), with date and method.
    - Done when: each target shows "met", "not met", or "not measured" with its measurement, and unmeasured figures keep the "proposed, not measured" label.
    - _Requirements: R20.7, R2.1, R4.1, R15.3, R15.7, R16.6_

  - [ ] 4.9 Run offline smoke and release-boundary tests
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T3.18
    - Output: automated tests that run all demo scenarios with outbound network blocked and assert zero cloud requests, replay without a live connection, exactly three priority scenarios, detections in the backlog absent, and every task and test citing a requirement ID.
    - Done when: all pass with the network blocked and AT-CORE-02 passes.
    - _Requirements: R20.1, R4.7, R1.1, R1.6, R19.5, R21.5_

  - [ ] 4.10 Run final acceptance tests through the dashboard
    - Owner: 04 Dashboard and workflow (Unassigned)
    - Depends on: T4.3, T4.4, T4.8, T4.9, T4.12
    - Output: a signed results sheet for every acceptance test ID in [demo-and-evaluation.md](../../../docs/finshield/demo-and-evaluation.md) (AT-P1-01 to AT-P1-09, AT-P2-01 to AT-P2-04, AT-P3-01 to AT-P3-04, AT-CORE-01, AT-CORE-02, AT-AI-01, AT-RESP-01, AT-ACC-01), run by a person who did not write the code under test.
    - Done when: every test shows pass or a logged failure with a decisions.md entry, and the P1 demo completes before the others.
    - _Requirements: R1.3, R1.7, R6.4, R6.5, R9.13, R10.1, R12.6, R19.5_

  - [ ] 4.11 Rehearse the judge walkthrough
    - Owner: 03 AI and controls (Unassigned)
    - Depends on: T4.7, T4.10, T4.12
    - Output: a rehearsal log from at least two timed run-throughs with the final demo script: P1 first, change one value and replay for each scenario, approvals question with both lookup outcomes, simulated action approval, and the live or fallback label. Includes planned answers on "proposed, not measured" figures and the DPDP-aligned wording.
    - Done when: two consecutive run-throughs finish without a code change, each change-one-value replay shows its reason on screen, and every issue found has an owner and a decision.
    - _Requirements: R1.3, R4.5, R16.5, R13.8, R13.9, R18.1, R20.7_

  - [ ] 4.12 Document actual deployment status
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T4.5, T4.6, T4.8, T4.9
    - Output: a status table in [README.md](../../../docs/finshield/README.md) listing, for the local path and each AWS service (API Gateway, Lambda, DynamoDB, Bedrock), whether it is "built and verified", "built, not verified", "skipped: sandbox blocked", or "not built", with date and method. States that S3 and EventBridge are not used.
    - Done when: no claim of a deployed service exists without a recorded verification, and the table matches T4.5, T4.6, and T4.9 outcomes.
    - _Requirements: R20.1, R20.2, R20.3, R20.7_

  - [ ] 4.13 Close the decision log
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T4.3, T4.7, T4.8, T4.12
    - Output: [decisions.md](../../../docs/finshield/decisions.md) updated so D-01 to D-13 each show the final choice, any baseline-method or contract change with reason (R3.7, R19.2), skipped optional tasks, and the open items carried forward. Includes D-03, D-08, D-09, D-10 wording gaps returned to the requirements owner.
    - Done when: every D-01 to D-13 entry has a final status and no entry is marked open without an owner.
    - _Requirements: R19.2, R3.7, R20.7_

  - [ ] 4.14 Final checkpoint
    - Owner: 05 Platform and integration (Unassigned)
    - Depends on: T4.11, T4.13
    - Output: a final run of the full test suite and the walkthrough on a clean laptop with the network off.
    - Done when: all tests pass and the deployment status table is current. Ensure all tests pass, ask the user if questions arise.
    - _Requirements: R20.1, R19.5_

## Notes

- Tasks marked with `*` are optional. Property tests are optional by workflow convention. T3.12 (backlog) is optional because the backlog is outside the critical path (R1.6). T4.5 (live Bedrock) and T4.6 (AWS path) are optional because they need sandbox access. If T1.10 records a service as blocked, skip the task and log the skip in decisions.md (T4.13 collects it).
- Each task cites requirement IDs for traceability (R19.5). Property tests also name their property number from [design.md](design.md).
- Milestones M2 to M4 start only after the previous checkpoint. Within a milestone, tasks with no shared dependency run in parallel.
- Dashboard tasks T2.12, T2.13, and T2.14 must use separate components so they can run in the same wave without editing the same files. The same applies to T3.2 to T3.5 and their rule modules.
- Timing, sample size, and cost figures stay "proposed, not measured" until a dated measurement with its method is attached (R20.7).
- This workflow creates planning artifacts only. Implementation starts by opening this file and choosing "Start task" beside a task.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3", "1.4", "1.10", "3.12"] },
    { "id": 1, "tasks": ["1.2", "1.5", "1.6", "1.7", "1.9"] },
    { "id": 2, "tasks": ["1.8", "1.14", "1.15"] },
    { "id": 3, "tasks": ["1.11", "1.12", "1.13"] },
    { "id": 4, "tasks": ["1.16"] },
    { "id": 5, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 6, "tasks": ["2.4", "2.5", "2.24", "2.25", "2.26", "2.31"] },
    { "id": 7, "tasks": ["2.6", "2.17", "2.20", "2.22", "2.27", "2.32"] },
    { "id": 8, "tasks": ["2.7", "2.8", "2.9", "2.16", "2.18", "2.19", "2.21", "2.23"] },
    { "id": 9, "tasks": ["2.10", "2.11", "2.28", "2.29", "2.30"] },
    { "id": 10, "tasks": ["2.12", "2.13", "2.14"] },
    { "id": 11, "tasks": ["2.15"] },
    { "id": 12, "tasks": ["2.33"] },
    { "id": 13, "tasks": ["3.1", "3.10"] },
    { "id": 14, "tasks": ["3.2", "3.3"] },
    { "id": 15, "tasks": ["3.4", "3.5", "3.7", "3.14", "3.15"] },
    { "id": 16, "tasks": ["3.6", "3.8", "3.13", "3.16"] },
    { "id": 17, "tasks": ["3.9", "3.17"] },
    { "id": 18, "tasks": ["3.11"] },
    { "id": 19, "tasks": ["3.18"] },
    { "id": 20, "tasks": ["4.1", "4.2", "4.5", "4.6", "4.8", "4.9"] },
    { "id": 21, "tasks": ["4.3", "4.4", "4.12"] },
    { "id": 22, "tasks": ["4.7", "4.10"] },
    { "id": 23, "tasks": ["4.11", "4.13"] },
    { "id": 24, "tasks": ["4.14"] }
  ]
}
```
