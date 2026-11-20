# 01 Data and replay

## Role and purpose

This role makes the fake business data and the replay that feeds it into the system. It supplies normal history, scenario fixtures, and the expected outcome for each fixture, so every team can test against the same inputs and get the same results every time.

## Owner and contributors

Owner: Unassigned
Contributors: none yet

## What I own

- Fake business records (accounts, documents, customers). Everything is marked synthetic.
- Normal activity history and baselines (for example 5 to 10 documents per five minutes for `acct-admin-07`).
- Scenario fixtures and the expected-results file for each, plus [scenarios.md](../../scenarios.md).
- The replay engine: deterministic replay inputs, run configuration, change-one-value runs.
- The evaluation harness (T4.2).

## What I need from other roles

- From 02 (T1.1): contract v1.0 and its schema. Workaround while waiting: copy the shape of `evt-002` from the worked example in [contracts.md](../../contracts.md) and check your fixtures against it later.
- From 05 (T1.3): repo skeleton and test tooling. Workaround: keep fixtures as plain JSON files in a scratch folder and move them in once the skeleton lands.
- From 02 and 05 (T2.1, T2.2): real intake and Evidence_Store for the replay engine. Workaround: replay into a stub that only checks order and counts.

## What I provide to other roles

- Fixture files and expected results to 02 and 03 (T1.6). 02 reads them directly from disk for T1.8.
- Sample normal activity to 03 and 04.
- Baselines (T2.3) and the replay engine (T2.4) to 05 for the local API server.
- Scenario fixtures for P2, P3 and accuracy cases (T3.1), and the evaluation harness (T4.2).

## First task I can start today

T1.5, write scenarios.md with data, numbers and expected results. It depends on T1.1, but you can start from the worked example in [contracts.md](../../contracts.md) (run `run-7f3a9c21`, events `evt-001` to `evt-003`) and the P1 rules already in [scenarios.md](../../scenarios.md). Then T1.6.

## Task checklist with shared task IDs

Master list: [tasks.md](../../../../.kiro/specs/finshield-ai/tasks.md)

- [ ] T1.5 Write scenarios.md with data, numbers, and expected results
- [ ] T1.6 Create sample fixtures and expected outputs
- [ ] T2.3 Implement baseline generator and builder
- [ ] T2.4 Implement Replay_Engine with run configuration
- [ ]* T2.18 Property test: replay is deterministic and repeatable
- [ ]* T2.19 Property test: arrival order does not matter
- [ ]* T2.24 Property test: baseline excludes injected events and is well-formed
- [ ]* T2.32 Property test: changing one value shows only caused differences
- [ ] T3.1 Create fixtures and expected results for P2, P3, and accuracy cases
- [ ] T3.6 Add replay catalogue for all scenarios
- [ ] T4.2 Build evaluation harness

Items marked `*` are optional.

## Files or components I expect to change

- [docs/finshield/scenarios.md](../../scenarios.md)
- Fixture and expected-results files (synthetic data folder)
- Baseline generator and builder, Replay_Engine, evaluation harness

## Example input and expected output

Input: the P1 fixture for `acct-admin-07`, three exports replayed in event-time order.

| Event | Time (UTC) | Files | Expected result |
|---|---|---|---|
| `evt-001` | 2026-03-12 10:00 | 80 | No alert |
| `evt-002` | 2026-03-12 10:02 | 90 | One Critical incident `inc-p1-evt-002` at 170 files |
| `evt-003` | 2026-03-12 10:04 | 130 | Same incident updates to 300 files |

Full numbers: [scenarios.md](../../scenarios.md). Payload shape: [contracts.md](../../contracts.md).

## How I test my work

- Validate every fixture against the contract schema, and check that each record has `synthetic: true`.
- Replay the same fixtures twice and compare results. They must match.
- Shuffle arrival order and confirm the same incidents appear.
- Run the baseline builder with 29 samples and confirm it refuses and names the account and metric.

## What I must demonstrate before handoff

- The expected-results file states no alert at 80, Critical at 170, and 300 files at the third event.
- A P1 replay runs with no live connection and a repeat replay leaves the incident count unchanged.
- Changing the limit from 100 to 170 creates a second run and leaves the first one untouched.

## Open decisions and blockers

- [D-02 Baseline method](../../decisions.md#d-02)
- [D-03 P3 meaning of "after the fifth failure"](../../decisions.md#d-03)
- Blocker: T1.1 contract not yet signed off (T1.2). Use the worked example until then.

## Links to additional Markdown files for this role

No role notes yet. Add topic files in this folder and link them here, one line each.
