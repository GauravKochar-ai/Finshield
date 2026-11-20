# 02 Detection and backend

## Role and purpose

This role writes the contract and the core logic that turns events into incidents. It covers event intake, detection rules, incident grouping, the APIs' shared core, and evidence retrieval.

## Owner and contributors

Owner: Unassigned
Contributors: none yet

## What I own

- [contracts.md](../../contracts.md) and the machine-readable schema file.
- Intake_Service: validation, duplicates, rejected-input area.
- Detection rules for P1, P2, P3, the upload variation and the accuracy cases.
- Incident_Manager: grouping, severity history, event counts, files and distinct customers as separate figures.
- Approval matching and missing-evidence handling.
- Result states and the detection backlog entries.

## What I need from other roles

- From 01 (T1.6): fixture files and expected results. Workaround: write the rule functions against the P1 numbers in [scenarios.md](../../scenarios.md) (80, 90, 130 documents) and swap in the real files later.
- From 05 (T2.2): Evidence_Store. Workaround: read fixture files directly from disk with no storage (this is how T1.8 is built).
- From 05 (T1.2): contract sign-off. Workaround: build against v1.0 as drafted, and log any change request in [decisions.md](../../decisions.md).

## What I provide to other roles

- Contract v1.0 with example responses to all four other roles (T1.1).
- Rule core to 01 and 05 for replay and the local API server (T1.8, T2.5).
- Incidents to 03 (T2.6), who builds explanations and actions on them.
- Result states and incident data to 04 for the dashboard views (T3.8).

## First task I can start today

T1.1, draft contracts.md version 1.0 with example responses. It has no dependency. Start from the worked example already in [contracts.md](../../contracts.md) and make sure every payload has a field table and an example. Then T1.8.

## Task checklist with shared task IDs

Master list: [tasks.md](../../../../.kiro/specs/finshield-ai/tasks.md)

- [ ] T1.1 Draft contracts.md version 1.0 with example responses
- [ ] T1.8 Implement P1 rule core against fixture files
- [ ]* T1.11 Property test: rolling window membership
- [ ]* T1.12 Property test: volume limit boundary
- [ ]* T1.13 Property test: multiple-of-normal boundary
- [ ] T2.1 Implement Intake_Service
- [ ] T2.5 Implement approval matching and missing-evidence handling for P1
- [ ] T2.6 Implement Incident_Manager
- [ ]* T2.16 Property test: duplicate events never change results
- [ ]* T2.20 Property test: P1 severity follows the decision table
- [ ]* T2.21 Property test: files and distinct customers are counted separately
- [ ]* T2.22 Property test: approval covers an export only when everything matches
- [ ]* T2.23 Property test: one incident per group with correct event counts
- [ ]* T2.25 Property test: intake rejects invalid input and stores nothing
- [ ]* T2.26 Property test: event serialization round trip
- [ ]* T2.27 Property test: configuration validation keeps the last good value
- [ ] T3.2 Implement P2 rule
- [ ] T3.3 Implement P3 rule
- [ ] T3.4 Implement P1 external upload variation
- [ ] T3.5 Implement accuracy cases
- [ ] T3.8 Implement result state assignment in the backend
- [ ]* T3.12 Record future detection backlog entries
- [ ]* T3.13 Property test: transfer labels
- [ ]* T3.14 Property test: P2 counts distinct unassigned customers only
- [ ]* T3.15 Property test: P3 trigger boundaries
- [ ]* T3.16 Property test: missing evidence is never a pass
- [ ]* T3.17 Property test: every check has exactly one result state

Items marked `*` are optional.

## Files or components I expect to change

- [docs/finshield/contracts.md](../../contracts.md) and the schema file
- Intake_Service, rule modules (one module per scenario), Incident_Manager
- Backlog section in [scenarios.md](../../scenarios.md) (T3.12 only)

## Example input and expected output

Input: events `evt-001` (80 files), `evt-002` (90 files), `evt-003` (130 files) by `acct-admin-07`, run `run-7f3a9c21`, normal range 5 to 10 per five minutes, no approval found.

Expected output:

```json
{
  "incident_id": "inc-p1-evt-002",
  "severity": "Critical",
  "total_files": 300,
  "distinct_customers": 180
}
```

Nothing is raised at `evt-001`. The incident opens at 170 files on `evt-002` and grows to 300 on `evt-003`. Full response: [contracts.md](../../contracts.md#worked-example-one-p1-kyc-incident). Rules: [scenarios.md](../../scenarios.md).

## How I test my work

- Run the P1 fixture files through the rule core and compare with the expected-results file.
- Boundary tests: limit 100 does not trigger at 100 and triggers at 101. Multiple-of-normal at 49 and 50.
- Send each invalid intake case and confirm it returns the named fields and stores nothing.
- Send the same event twice and confirm the second returns `duplicate`.

## What I must demonstrate before handoff

- The example P1 incident response validates against the schema file (T1.1).
- The fixture run gives no alert at 80, Critical at 170 with all conditions shown, and 300 files at the third event with no second incident.
- An unavailable approvals source gives High with "approvals source" missing, and a later "no match" raises the same incident to Critical.

## Open decisions and blockers

- [D-03 P3 meaning of "after the fifth failure"](../../decisions.md#d-03)
- [D-08 Uploads and the 15-minute grouping window](../../decisions.md#d-08)
- [D-09 Incident event count versus window events](../../decisions.md#d-09)
- [D-10 Fifth label for checks that find something](../../decisions.md#d-10)
- [D-12 Closing an incident](../../decisions.md#d-12)
- Blocker: T1.6 fixtures from role 01. Use the example numbers until they arrive.

## Links to additional Markdown files for this role

- `kyc-rule-notes.md`: not yet created (turn this into a link once the file exists). Example of a role note (open questions on the P1 window and approval matching).
