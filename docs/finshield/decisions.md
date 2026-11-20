# FinShield AI: decision log

This log holds every open choice and every contract change. Build with the recommended default. If the team picks something else, change the status and add a short note. Primary homes: payload fields in [contracts.md](contracts.md), scenario rules in [scenarios.md](scenarios.md), requirements in [requirements.md](../../.kiro/specs/finshield-ai/requirements.md), design in [design.md](../../.kiro/specs/finshield-ai/design.md), tasks in [tasks.md](../../.kiro/specs/finshield-ai/tasks.md). Task T4.13 closes this log before release.

Owner roles: 01 Data and replay, 02 Detection and backend, 03 AI and controls, 04 Dashboard and workflow, 05 Platform and integration. Role guides are linked from [README.md](README.md).

## Summary

| ID | Title | Owner role | Status |
|---|---|---|---|
| [D-01](#d-01) | Local storage | 05 Platform and integration | Open - default applies |
| [D-02](#d-02) | Baseline method | 01 Data and replay | Open - default applies |
| [D-03](#d-03) | P3 meaning of "after the fifth failure" | 02 Detection and backend | Open - default applies |
| [D-04](#d-04) | Bedrock model and AWS Region | 03 AI and controls, with 05 | Open - default applies |
| [D-05](#d-05) | Placeholders or real synthetic IDs in AI answers | 03 AI and controls | Open - default applies |
| [D-06](#d-06) | Dashboard hosting on the AWS path | 05 Platform and integration | Open - default applies |
| [D-07](#d-07) | Reviewer identity in the demo | 04 Dashboard and workflow | Open - default applies |
| [D-08](#d-08) | Uploads and the 15-minute grouping window | 02 Detection and backend | Open - default applies |
| [D-09](#d-09) | Incident event count versus window events | 02 Detection and backend | Open - default applies |
| [D-10](#d-10) | Fifth result label for checks that find something | 04 Dashboard and workflow | Open - default applies |
| [D-11](#d-11) | Live-event feed | 04 Dashboard and workflow | Open - default applies |
| [D-12](#d-12) | Closing an incident | 02 Detection and backend | Open - default applies |
| [D-13](#d-13) | Owner of the legal-finding phrase list | 03 AI and controls | Open - default applies |
| [D-14](#d-14) | Response actions limited to two simulated types | 03 AI and controls | Agreed |

## Decisions

<a id="d-01"></a>
### D-01: Local storage

- **Question:** Should the local path store data in a SQLite file or in DynamoDB Local (which needs Docker)?
- **Owner role:** 05 Platform and integration
- **Recommended default:** SQLite file behind the same repository interface.
- **Status:** Open - default applies
- **Affects:** [R20](../../.kiro/specs/finshield-ai/requirements.md), [R15](../../.kiro/specs/finshield-ai/requirements.md). Task [T2.2](../../.kiro/specs/finshield-ai/tasks.md) (repository and SQLite adapter), T1.3.

<a id="d-02"></a>
### D-02: Baseline method

- **Question:** Is the normal range the minimum and maximum of normal samples, or a percentile?
- **Owner role:** 01 Data and replay
- **Recommended default:** Minimum and maximum of normal samples. This matches the "5 to 10 documents" example.
- **Status:** Open - default applies
- **Affects:** [R3](../../.kiro/specs/finshield-ai/requirements.md) (R3.7). Task [T2.3](../../.kiro/specs/finshield-ai/tasks.md) (baseline generator and builder).

<a id="d-03"></a>
### D-03: P3 meaning of "after the fifth failure"

- **Question:** What does "after the fifth failure" mean when more than five failures exist?
- **Owner role:** 02 Detection and backend
- **Recommended default:** Count failures since the account's last successful login. Compare the success with the latest failure (0 to 600 seconds inclusive).
- **Status:** Open - default applies
- **Affects:** [R10](../../.kiro/specs/finshield-ai/requirements.md). Task [T3.3](../../.kiro/specs/finshield-ai/tasks.md) (P3 rule). Scenario rules in [scenarios.md](scenarios.md).

<a id="d-04"></a>
### D-04: Bedrock model and AWS Region

- **Question:** Which Bedrock model and AWS Region does the sandbox use?
- **Owner role:** 03 AI and controls, with 05 Platform and integration
- **Recommended default:** Choose a model offered in the sandbox Region. Availability needs official verification.
- **Status:** Open - default applies
- **Affects:** [R13](../../.kiro/specs/finshield-ai/requirements.md), [R20](../../.kiro/specs/finshield-ai/requirements.md). Tasks [T1.10](../../.kiro/specs/finshield-ai/tasks.md) (sandbox check), [T4.5](../../.kiro/specs/finshield-ai/tasks.md) (live Bedrock, optional).

<a id="d-05"></a>
### D-05: Placeholders or real synthetic IDs inside AI answers

- **Question:** Should AI answers show masked placeholders or real synthetic IDs?
- **Owner role:** 03 AI and controls
- **Recommended default:** Keep placeholders (`ACTOR-1`, `CUSTOMER-1`) in the answer text. Show real IDs only in the incident header.
- **Status:** Open - default applies
- **Affects:** [R18](../../.kiro/specs/finshield-ai/requirements.md) (R18.7, R18.8), [R13](../../.kiro/specs/finshield-ai/requirements.md). Tasks [T1.9](../../.kiro/specs/finshield-ai/tasks.md), [T2.9](../../.kiro/specs/finshield-ai/tasks.md). Payload: AI explanation in [contracts.md](contracts.md#ai-explanation).

<a id="d-06"></a>
### D-06: Dashboard hosting on the AWS path

- **Question:** Where is the dashboard hosted on the AWS path?
- **Owner role:** 05 Platform and integration
- **Recommended default:** Run the React app locally against the API Gateway URL. No S3 hosting.
- **Status:** Open - default applies
- **Affects:** [R20](../../.kiro/specs/finshield-ai/requirements.md) (R20.3). Task [T4.6](../../.kiro/specs/finshield-ai/tasks.md) (AWS adapters, optional).

<a id="d-07"></a>
### D-07: Reviewer identity in the demo

- **Question:** How is the reviewer chosen in the demo?
- **Owner role:** 04 Dashboard and workflow
- **Recommended default:** Two fixed demo users (`user-analyst`, `user-security-lead`) chosen from a list. Labelled "demo sign-in, not authentication".
- **Status:** Open - default applies
- **Affects:** [R14](../../.kiro/specs/finshield-ai/requirements.md). Task [T2.8](../../.kiro/specs/finshield-ai/tasks.md) (Response_Controller). Payload: reviewer action in [contracts.md](contracts.md#reviewer-action).

<a id="d-08"></a>
### D-08: Uploads and the 15-minute grouping window

- **Question:** R8.1 and R11.1 differ on when an upload joins an incident. Which wins?
- **Owner role:** 02 Detection and backend
- **Recommended default:** R8.1 wins for uploads. Attach to the open P1 incident when the upload is later than the earliest export.
- **Status:** Open - default applies
- **Affects:** [R8](../../.kiro/specs/finshield-ai/requirements.md), [R11](../../.kiro/specs/finshield-ai/requirements.md). Task [T3.4](../../.kiro/specs/finshield-ai/tasks.md) (upload variation).

<a id="d-09"></a>
### D-09: Incident event count versus window events

- **Question:** R6.4 and R11.2 differ on what the incident event count includes.
- **Owner role:** 02 Detection and backend
- **Recommended default:** The event that triggers the incident counts as 1. Earlier window events are referenced by the rule result, not counted again. Example: `inc-p1-evt-002` has event count 1 after `evt-002` and 2 after `evt-003`.
- **Status:** Open - default applies
- **Affects:** [R6](../../.kiro/specs/finshield-ai/requirements.md), [R11](../../.kiro/specs/finshield-ai/requirements.md). Task [T2.6](../../.kiro/specs/finshield-ai/tasks.md) (Incident_Manager). Payload: incident `event_count` in [contracts.md](contracts.md#incident).

<a id="d-10"></a>
### D-10: Fifth label for checks that find something

- **Question:** R17.1 lists four states, but a check that finds something has none. What is shown?
- **Owner role:** 04 Dashboard and workflow, with the requirements owner
- **Recommended default:** Add a fifth neutral label "completed, findings shown". The four states stay as written.
- **Status:** Open - default applies
- **Affects:** [R17](../../.kiro/specs/finshield-ai/requirements.md). Task [T3.8](../../.kiro/specs/finshield-ai/tasks.md) (result state assignment). Payload: result states in [contracts.md](contracts.md#result-states).

<a id="d-11"></a>
### D-11: Live-event feed

- **Question:** Is the live-event feed (`[DECK]`, R16.8) built?
- **Owner role:** 04 Dashboard and workflow
- **Recommended default:** Not built in the first release.
- **Status:** Open - default applies
- **Affects:** [R16](../../.kiro/specs/finshield-ai/requirements.md) (R16.8). Dashboard tasks [T2.11](../../.kiro/specs/finshield-ai/tasks.md) to [T2.14](../../.kiro/specs/finshield-ai/tasks.md).

<a id="d-12"></a>
### D-12: Closing an incident

- **Question:** R8.7 mentions closed incidents. Is there a close action?
- **Owner role:** 02 Detection and backend
- **Recommended default:** No close action in the first release. Tests use a fixture incident marked closed.
- **Status:** Open - default applies
- **Affects:** [R8](../../.kiro/specs/finshield-ai/requirements.md) (R8.7). Task [T3.4](../../.kiro/specs/finshield-ai/tasks.md).

<a id="d-13"></a>
### D-13: Owner of the legal-finding phrase list

- **Question:** Who maintains the phrase list used by the citation check?
- **Owner role:** 03 AI and controls
- **Recommended default:** 03 AI and controls maintains it, reviewed with the security lead.
- **Status:** Open - default applies
- **Affects:** [R13](../../.kiro/specs/finshield-ai/requirements.md) (R13.4), [R18](../../.kiro/specs/finshield-ai/requirements.md) (R18.4). Task [T1.9](../../.kiro/specs/finshield-ai/tasks.md).

<a id="d-14"></a>
### D-14: Response actions limited to two simulated types

- **Question:** Which response actions does the first release offer?
- **Owner role:** 03 AI and controls (with 04 Dashboard and workflow for labels)
- **Decision:** Only two action types exist: **suspend account** and **request verification**. Both are simulated. Nothing calls a real system. The dashboard says "simulated", never "executed". No other action type is accepted by the API.
- **Status:** Agreed
- **Affects:** [R14](../../.kiro/specs/finshield-ai/requirements.md), [R10](../../.kiro/specs/finshield-ai/requirements.md) (R10.5). Tasks [T2.8](../../.kiro/specs/finshield-ai/tasks.md), [T3.7](../../.kiro/specs/finshield-ai/tasks.md). Payload: `action_type` in [contracts.md](contracts.md#reviewer-action).

## Template: new decision

Copy this block to the end of the Decisions section. Use the next free number. Never reuse or renumber IDs.

```markdown
<a id="d-NN"></a>
### D-NN: Short title

- **Question:** One sentence.
- **Owner role:** 01 Data and replay / 02 Detection and backend / 03 AI and controls / 04 Dashboard and workflow / 05 Platform and integration
- **Options considered:** A, B (one line each, with the trade-off).
- **Recommended default:** What applies until the team decides.
- **Status:** Open - default applies / Agreed / Superseded by D-NN
- **Affects:** Requirement IDs (for example R6.4) and task IDs (for example T2.6), as links.
- **Date and who agreed:** (when status becomes Agreed)
```

Add a row to the Summary table in the same change.

## Template: contract change

Use this for every change to [contracts.md](contracts.md). Process: propose in a role note, add this entry, bump the version, notify affected roles, then merge.

```markdown
<a id="c-NN"></a>
### C-NN: Short title of the contract change

- **Proposed by:** role and name, with link to the role note.
- **Old version -> new version:** for example 1.0 -> 1.1
- **Change type:** MINOR (additive, optional fields only) / MAJOR (removal, rename, change of meaning or type, field becomes required)
- **What changes:** payload, field, old and new definition.
- **Reason:** One or two sentences.
- **Affected roles notified:** 01 / 02 / 03 / 04 / 05 (tick each and note the date).
- **Requirements and tasks affected:** R-numbers and task IDs, as links.
- **Status:** Proposed / Merged / Rejected
```

No contract changes have been logged. Contract version is 1.0.
