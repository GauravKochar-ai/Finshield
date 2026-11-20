# 04 Dashboard and workflow

## Role and purpose

This role builds the React dashboard that analysts and the security lead use: activity feed, incident list and detail, evidence timeline, reviewer actions and replay controls. This role is also the final acceptance owner and runs the acceptance tests through the dashboard.

## Owner and contributors

Owner: Unassigned
Contributors: none yet

## What I own

- Incident list (newest first) and incident detail with conditions, files and distinct customers as two separate figures, missing evidence and run ID.
- Activity feed (see D-11 for whether the live-event feed is built).
- Evidence timeline with source view and export.
- Reviewer actions: Investigate, approve or reject, "simulated" labels.
- Replay controls: scenario selector, change one value, side-by-side compare.
- Compliance wording and the "Suggest compliance review" action.
- Final acceptance tests (T4.10) and the business-value experiment (T4.7).

## What I need from other roles

- From 02 (T1.1): contract examples. Workaround: build against the example responses in [contracts.md](../../contracts.md) with no backend running.
- From 05 (T2.7): local API server. Workaround: keep reading the example responses and switch to the API at T2.11.
- From 03 (T2.8, T2.9): explanations and actions. Workaround: render the explanation and action examples from [contracts.md](../../contracts.md).
- From 01: replay controls need the replay engine (T2.4). Workaround: stub the run and compare responses from the contract example.

## What I provide to other roles

- Dashboard views that show every incident field from the contract, so 02 and 03 can see their output (T2.11, T2.14).
- Replay controls to 05 for integration tests (T2.13).
- Final acceptance results sheet to the whole team (T4.10).

## First task I can start today

T1.7, build the dashboard shell against example responses. It depends on T1.1 and T1.3. Workaround: start from the P1 incident example already in [contracts.md](../../contracts.md#worked-example-one-p1-kyc-incident) and a plain React app shell. Move into the shared repo skeleton when T1.3 lands.

## Task checklist with shared task IDs

Master list: [tasks.md](../../../../.kiro/specs/finshield-ai/tasks.md)

- [ ] T1.7 Build dashboard shell against example responses
- [ ] T2.11 Wire dashboard to the local API
- [ ] T2.12 Add evidence trail view and export to the dashboard
- [ ] T2.13 Add replay controls and compare view to the dashboard
- [ ] T2.14 Add investigation and response approval to the dashboard
- [ ] T3.9 Add P2, P3, and accuracy views to the dashboard
- [ ] T3.10 Add compliance wording and review action to the dashboard
- [ ] T4.7 Run business-value experiment
- [ ] T4.10 Run final acceptance tests through the dashboard

## Files or components I expect to change

- React app: incident list, incident detail, evidence trail, replay controls, investigation panel, compliance wording
- Keep T2.12, T2.13 and T2.14 in separate components so they can be built in parallel
- Final results sheet linked from [demo-and-evaluation.md](../../demo-and-evaluation.md)

## Example input and expected output

Input: the P1 example incident response (run `run-7f3a9c21`, incident `inc-p1-evt-002`).

| Screen element | Expected content |
|---|---|
| Incident list row | Critical, P1, `acct-admin-07` |
| Detail figures | Files: 300. Distinct customers: 180 (two separate labels) |
| Conditions | Each shows value seen, limit and result |
| Missing evidence | "none missing" or the named sources |
| Action after approve | Shown as "simulated", never "executed" |

Full payload: [contracts.md](../../contracts.md#worked-example-one-p1-kyc-incident). Expected dashboard content per case: [scenarios.md](../../scenarios.md).

## How I test my work

- Build the app and render the P1 example with no backend running.
- Compare each scenario's screen with the expected dashboard content in [scenarios.md](../../scenarios.md).
- Run a wording check over screens and exports for the words breach, violation and non-compliance.
- For final acceptance, run each test in [demo-and-evaluation.md](../../demo-and-evaluation.md) as a person who did not write the code under test.

## What I must demonstrate before handoff

- The app renders the P1 example with files and customers as two separately labelled numbers.
- With the API wired in, a P1 replay shows one Critical incident, then 300 files and 180 customers after the third export, with no code change between example and API.
- Changing the limit from 100 to 170 shows the new incident next to the old one with the changed condition highlighted.
- Missing evidence looks different from "checked, nothing found".

## Open decisions and blockers

- [D-06 Dashboard hosting on the AWS path](../../decisions.md#d-06)
- [D-07 Reviewer identity in the demo](../../decisions.md#d-07)
- [D-10 Fifth label for checks that find something](../../decisions.md#d-10)
- [D-11 Live-event feed](../../decisions.md#d-11)
- [D-12 Closing an incident](../../decisions.md#d-12)
- Blocker: the local API server (T2.7) is built by role 05. Use example responses until then.

## Links to additional Markdown files for this role

No role notes yet. Add topic files in this folder (for example screen notes) and link them here, one line each.
