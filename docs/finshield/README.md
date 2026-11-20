# FinShield AI: team handoff

FinShield AI is built by Team Global Nodes for the AI FORGE 2026 hackathon. It helps the security team of a fictional Indian digital lender investigate unusual access to KYC documents, loan records and privileged accounts. All data is synthetic. This folder is where the team works day to day. The formal spec lives in `.kiro/specs/finshield-ai/` and is not edited from here.

## Find your first task in two minutes

1. Pick your role in the table below.
2. Open your role README (column "Role guide"). It has your sample input and your acceptance check.
3. Open your first task in the [master task list](../../.kiro/specs/finshield-ai/tasks.md) (search for the task ID).
4. Claim the role (see [How to claim a role](#how-to-claim-a-role)).

| Role | Owner | First task | Role guide | Task in tasks.md |
|---|---|---|---|---|
| 01 Data and replay | Unassigned | T1.5 (then T1.6) | [roles/01-data-and-replay/README.md](roles/01-data-and-replay/README.md) | [T1.5](../../.kiro/specs/finshield-ai/tasks.md) |
| 02 Detection and backend | Unassigned | T1.1 (then T1.8) | [roles/02-detection-and-backend/README.md](roles/02-detection-and-backend/README.md) | [T1.1](../../.kiro/specs/finshield-ai/tasks.md) |
| 03 AI and controls | Unassigned | T1.9 | [roles/03-ai-and-controls/README.md](roles/03-ai-and-controls/README.md) | [T1.9](../../.kiro/specs/finshield-ai/tasks.md) |
| 04 Dashboard and workflow | Unassigned | T1.7 | [roles/04-dashboard-and-workflow/README.md](roles/04-dashboard-and-workflow/README.md) | [T1.7](../../.kiro/specs/finshield-ai/tasks.md) |
| 05 Platform and integration | Unassigned | T1.3 (then T1.4, T1.10) | [roles/05-platform-and-integration/README.md](roles/05-platform-and-integration/README.md) | [T1.3](../../.kiro/specs/finshield-ai/tasks.md) |

The Owner column here is a summary. The Owner line inside each role README is the one to edit.

Task IDs (T1.1, T2.5 and so on) are stable and never renumbered. Requirement IDs (R6.4 and so on) point into [requirements.md](../../.kiro/specs/finshield-ai/requirements.md).

One person may take two roles. Several people may share one role. If you share, write all names in the Owner line.

### Sample input and acceptance check for everyone

The shared sample is the P1 bulk KYC export. Account `acct-admin-07` (privileged, normal range 5 to 10 documents per five minutes) exports 80, 90 and 130 documents at 10:00, 10:02 and 10:04.

- Expected: no alert at 80. One Critical incident `inc-p1-evt-002` at 170 files. The same incident grows to 300 files at the third export. No second incident.
- Acceptance tests: AT-P1-01, AT-P1-02, AT-P1-03. Full rules are in [scenarios.md](scenarios.md). Test list and demo script are in [demo-and-evaluation.md](demo-and-evaluation.md).

## Glossary

This is the working glossary. [requirements.md](../../.kiro/specs/finshield-ai/requirements.md#glossary) holds the spec copy with the full list of system parts. If the two ever disagree, raise it as a decision in [decisions.md](decisions.md).

- **KYC (Know Your Customer)**: The identity checks a lender must do before giving a loan. KYC documents are the files collected for this, such as ID cards, address proof and photos. They are highly sensitive.
- **NBFC (Non-Banking Financial Company)**: A regulated Indian lender that is not a bank. The fictional lender in this project is a digital NBFC.
- **Baseline**: What is normal for one account (or one role) over time, for example "this admin exports 5 to 10 documents in a five-minute period". It is calculated from normal activity only, never from injected suspicious events.
- **Incident**: One tracked case. It groups related events, has a severity (Critical, High or Medium) and is updated as new events arrive instead of creating duplicates.
- **Evidence trail**: The ordered list of events, rule results, approval lookups and actions that explain why an incident exists. Every item has an ID, so any claim can be traced to its source.

Other terms (Replay_Run, rolling window, approval, observed export, attempted upload, confirmed transfer, missing evidence) are defined in the requirements glossary. Where a term matters for a rule, [scenarios.md](scenarios.md) repeats the meaning in context.

Compliance wording: always "DPDP-aligned readiness and controls". Alerts can suggest a compliance review. They never state that a legal breach has happened.

## How to claim a role

1. Open your role README, for example `roles/02-detection-and-backend/README.md`.
2. Change the line `Owner: Unassigned` to `Owner: <your name>`.
3. Open a pull request with that one change. Merge it once a teammate has seen it.
4. Update the Owner column in the table above in the same pull request.

## How to add your own notes

Role notes are working documents. They do not replace the shared contract or the scenario rules.

**Add a topic file to your role folder.** Create a Markdown file in your role folder and link it from the role README. Concrete example: a detection developer writing down thinking about the KYC rule creates `roles/02-detection-and-backend/kyc-rule-notes.md`, then adds a line to `roles/02-detection-and-backend/README.md`:

```markdown
- [KYC rule notes](kyc-rule-notes.md): open questions on the P1 window and approval matching.
```

**Create a new role.** Copy [roles/ROLE-TEMPLATE.md](roles/ROLE-TEMPLATE.md) into `roles/NN-short-name/README.md`, fill it in, and add a row to the table above.

**Propose a change to a shared file.** Shared contracts and scenario rules stay in their primary file ([contracts.md](contracts.md), [scenarios.md](scenarios.md)). A role note may propose a change. Once the team agrees, the change is made in the primary file, logged in [decisions.md](decisions.md), and the role note links to the agreed result instead of copying it.

## Map of files (one primary home per fact)

| Fact | Primary home |
|---|---|
| What the system must do, requirement IDs R1 to R21 | [requirements.md](../../.kiro/specs/finshield-ai/requirements.md) |
| How it is built, architecture, correctness properties | [design.md](../../.kiro/specs/finshield-ai/design.md) |
| Task IDs, owners, dependencies, "done when" | [tasks.md](../../.kiro/specs/finshield-ai/tasks.md) |
| Scenario rules, numbers, severities, examples | [scenarios.md](scenarios.md) |
| Event and API payloads, contract version, change process | [contracts.md](contracts.md) |
| Open decisions D-01 to D-13 and contract change entries | [decisions.md](decisions.md) |
| Demo script, acceptance tests, evaluation | [demo-and-evaluation.md](demo-and-evaluation.md) |
| Role responsibilities, sample input, role notes | `roles/NN-.../README.md`, starting from [roles/ROLE-TEMPLATE.md](roles/ROLE-TEMPLATE.md) |
| Terms | This README (working glossary), requirements.md (spec copy) |

## Rules for all notes

- Synthetic data only. No real names, IDs or documents.
- Mark any unmeasured number "proposed, not measured" or "demo setting".
- Cite a requirement ID (for example R6.4) in every task and test.
