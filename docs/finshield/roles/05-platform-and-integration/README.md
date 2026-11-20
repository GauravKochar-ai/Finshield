# 05 Platform and integration

## Role and purpose

This role makes the parts work together. It covers local setup, AWS sandbox checks, wiring the parts into a local API server, end-to-end tests, measured results and demo readiness.

## Owner and contributors

Owner: Unassigned
Contributors: none yet

## What I own

- Repository skeleton, test tooling, and the requirement-ID check.
- Handoff docs skeleton and decision log ([decisions.md](../../decisions.md)).
- Evidence_Store (SQLite adapter) and the local API server.
- AWS sandbox checks and the optional AWS path (DynamoDB, Lambda, API Gateway).
- Integration tests at each milestone end.
- Measured results: blind test results, timing targets, deployment status table.
- Checkpoints and the final demo run.

## What I need from other roles

- From 02 (T1.1): contract v1.0, needed for sign-off (T1.2). Workaround: start T1.3, T1.4 and T1.10, which have no dependency, and review the draft in [contracts.md](../../contracts.md) as it grows.
- From 02, 03, 04 (T2.1, T2.6, T2.8, T2.9): core parts for the local API server (T2.7). Workaround: build the server skeleton and routes against the example responses in [contracts.md](../../contracts.md).
- From 03 and 01 (T4.1, T4.2): blind test set and harness for T4.3. Workaround: prepare the results table format and the timing measurement method first.

## What I provide to other roles

- Repo skeleton and one test command to everyone (T1.3).
- Evidence_Store to 02, 03 and 04 (T2.2), then the local API server (T2.7). 04 switches from example responses to the API.
- AWS sandbox status to 03 for the Bedrock decision (T1.10).
- Integration test results at each milestone end (T2.15, T3.11, T4.9).

## First task I can start today

T1.3, set up the repository skeleton and local tooling. It has no dependency. Then T1.4 and T1.10, which also have none.

## Task checklist with shared task IDs

Master list: [tasks.md](../../../../.kiro/specs/finshield-ai/tasks.md)

- [ ] T1.2 Review and sign off contract 1.0
- [ ] T1.3 Set up repository skeleton and local tooling
- [ ] T1.4 Create handoff docs skeleton and decision log
- [ ] T1.10 Check AWS sandbox access and record status
- [ ] T1.16 Checkpoint: M1 demonstrated
- [ ] T2.2 Implement Evidence_Store repository and SQLite adapter
- [ ] T2.7 Build local API server
- [ ] T2.10 Implement evidence source retrieval and export
- [ ] T2.15 Write P1 integration tests
- [ ]* T2.17 Property test: runs are isolated
- [ ]* T2.31 Property test: evidence is ordered and immutable
- [ ] T2.33 Checkpoint: P1 demonstrated end to end
- [ ] T3.11 Write P2, P3, and accuracy integration tests
- [ ] T3.18 Checkpoint: all scenarios and accuracy cases demonstrated
- [ ] T4.3 Run blind tests and record results
- [ ]* T4.6 Build AWS path adapters
- [ ] T4.8 Measure timing targets
- [ ] T4.9 Run offline smoke and release-boundary tests
- [ ] T4.12 Document actual deployment status
- [ ] T4.13 Close the decision log
- [ ] T4.14 Final checkpoint

Items marked `*` are optional.

## Files or components I expect to change

- Repo layout: Python core package, React app shell, test tooling
- [docs/finshield/decisions.md](../../decisions.md) and [README.md](../../README.md) (deployment status table)
- Evidence_Store, local API server, AWS adapters and handlers
- Integration test suites and results tables

## Example input and expected output

Input: `POST /v1/runs` for the P1 scenario on the local API server, then `GET /v1/runs/run-7f3a9c21/incidents`.

```json
{
  "contract_version": "1.0",
  "incidents": [
    { "incident_id": "inc-p1-evt-002", "severity": "Critical", "total_files": 300 }
  ]
}
```

The run completes with the network disabled. Full request and response: [contracts.md](../../contracts.md#worked-example-one-p1-kyc-incident). Case numbers: [scenarios.md](../../scenarios.md).

## How I test my work

- Run the empty suite and the requirement-ID check on a fresh clone with no cloud access.
- Repository contract tests on SQLite (and on DynamoDB if T4.6 is built).
- Integration tests through the local API for each acceptance test ID (AT-P1-01 and so on, listed in [demo-and-evaluation.md](../../demo-and-evaluation.md)).
- Offline smoke run with outbound network blocked, asserting zero cloud requests.
- Every figure gets a date and method, or the label "proposed, not measured".

## What I must demonstrate before handoff

- A fresh clone runs the test suite with one command and no cloud access.
- The P1 flow (replay, one Critical incident, 300 files, evidence view, AI fallback, reviewer approval recorded) passes in one command.
- Each AWS service is marked "available", "blocked" or "not checked" with a date and method.
- The deployment status table claims nothing without a recorded verification.

## Open decisions and blockers

- [D-01 Local storage](../../decisions.md#d-01)
- [D-04 Bedrock model and AWS Region](../../decisions.md#d-04)
- [D-06 Dashboard hosting on the AWS path](../../decisions.md#d-06)
- Blocker: AWS sandbox access is unconfirmed until T1.10. The local path does not need it.

## Links to additional Markdown files for this role

No role notes yet. Add topic files in this folder (for example AWS check notes) and link them here, one line each.
