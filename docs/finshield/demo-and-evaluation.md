# Demo and evaluation handoff

This file is the team handoff for testing, measuring and demonstrating FinShield AI. It defines the acceptance test IDs (AT-*) used in the [requirements traceability table](../../.kiro/specs/finshield-ai/requirements.md#traceability) and in [tasks.md](../../.kiro/specs/finshield-ai/tasks.md) (milestone M4, T4.1 to T4.14).

Related files: [scenarios.md](scenarios.md) (rules and numbers), [contracts.md](contracts.md) (payload fields), [decisions.md](decisions.md) (decision log), [README.md](README.md) (overview and deployment status).

All data is synthetic. Every threshold below is a **demo setting** taken from [scenarios.md](scenarios.md). Any number not yet measured is labelled "proposed, not measured". Compliance wording is always "DPDP-aligned readiness and controls". No alert or answer states that a legal breach or violation has happened. Any regulatory item is marked "needs official verification".

## Owners

| Work | Owner | Task |
|---|---|---|
| Integration tests | 05 Platform and integration | T2.15, T3.11, T4.9 |
| Final acceptance tests through the dashboard | 04 Dashboard and workflow | T4.10 |
| Blind test design | 03 AI and controls | T4.1 |
| Evaluation harness | 01 Data and replay | T4.2 |
| Blind test run and results | 05 Platform and integration | T4.3 |
| AI citation accuracy | 03 AI and controls | T4.4 |
| Business-value experiment | 04 Dashboard and workflow | T4.7 |
| Judge walkthrough rehearsal | 03 AI and controls | T4.11 |

Final acceptance (T4.10) must be run by a person who did not write the code under test.

## 1. Test matrix

Reused IDs come from the requirements traceability table. IDs marked **new** follow the same scheme (AT-P1-10 onward, AT-P2-05 onward, AT-P3-05 onward, AT-ACC-02 onward, AT-CORE-03 onward). The requirements traceability table and the T4.10 list need these new IDs added by the requirements owner. Until then they are proposed names.

"Incidents" means the number of incidents that exist for that actor or account after the input is processed. "Evidence" is what the dashboard must show.

### P1: bulk KYC export by a privileged account

| ID | Input variation | Alert | Severity | Incidents | Evidence that must appear |
|---|---|---|---|---|---|
| AT-P1-01 | `evt-001`: 80 documents at 10:00, no approval | No alert | none | 0 | Window sum 80 against limit "more than 100" |
| AT-P1-02 | `evt-002`: 90 more at 10:02, window sum 170 | Opens one incident | Critical | 1 (`inc-p1-evt-002`, 1 event) | Event IDs, rule result `rr-evt-002-p1` with each condition, approval lookup "returned no match", baseline `bl-001`, missing evidence "none" |
| AT-P1-03 | `evt-003`: 130 more at 10:04, window sum 300 | Updates same incident | Critical | 1 (2 events) | 300 files, event 3 attached, same incident ID |
| AT-P1-05 | Same data, files versus customers | n/a | Critical | 1 | Two separate figures: files and customers (300 and 180 in the illustrative data) |
| AT-P1-10 (new) | Window sum exactly 100, then exactly 101 (privileged, no approval) | 100: no alert. 101: alert | 101: Critical | 100: 0. 101: 1 | Limit "more than 100" shown with the value seen |
| AT-P1-11 (new) | Multiplier boundary. Set document limit to 40 (configuration, R6.2). Upper end of normal is 10. Window sum 49, then 50 | 49: no alert. 50: alert | 50: Critical | 49: 0. 50: 1 | Multiplier condition "at least 5 times 10 = 50" with value seen |
| AT-P1-06 | Valid scoped approval `appr-001`: same actor, operation, scope covers all records, valid 09:30 to 12:00, destination `dest-int-archive` | No Critical alert | none (approved activity) | 0 | Approval ID and the five matched checks, label "approved activity" |
| AT-P1-07a | Expired approval: export at or after expiry | Incident stays open | Critical | 1 | Expiry time and export time |
| AT-P1-07b | Unrelated ticket (or different actor, operation or record scope) | Incident stays open | Critical | 1 | Which of ticket, actor, operation or record scope did not match |
| AT-P1-07c | Destination mismatch: approved destination differs from export destination | Incident stays open | Critical | 1 | Approved destination and export destination |
| AT-P1-07d | Partial scope: approval covers 100 documents, export is 130 | Incident stays open | Critical | 1 | Count of uncovered records (30) |
| AT-P1-04a | Approvals source unavailable (volume and privileged pass) | Opens incident | High | 1 | "approvals source" in missing evidence. Text says missing evidence, not proof of wrongdoing |
| AT-P1-04b | Approvals source later answers "no match" for the High incident | Same incident raised | Critical | 1 (same ID) | "approvals source" removed from missing evidence |
| AT-P1-04c | No personal or role-level baseline | Opens incident | High | 1 | "baseline" in missing evidence |
| AT-P1-12 (new) | Personal baseline has fewer than 30 samples, role-level baseline exists | Opens incident | Critical | 1 | Label "baseline: role-level" |
| AT-P1-09 | Approvals lookup in three states | n/a | n/a | n/a | Dashboard shows exactly one of "returned a match", "returned no match", "unavailable" |
| AT-P1-08 | External upload variation: `evt-004` at 10:05, upload requested to `dest-ext-host-7`, open incident exists | Attaches to open incident | Critical (unchanged) | 1 (no new incident) | Label "attempted upload". "confirmed transfer" does not appear without a receipt event |

### P2: unassigned customer access by a collection agent or loan officer

Threshold 5 distinct customers, window 30 minutes (both demo settings). Only successful accesses count.

| ID | Input variation | Alert | Severity | Incidents | Evidence that must appear |
|---|---|---|---|---|---|
| AT-P2-01a | Fourth distinct unassigned customer | No alert | none | 0 | Distinct count 4 against threshold 5 |
| AT-P2-01b | Fifth distinct unassigned customer within 30 minutes (`evt-105`) | Opens incident | High | 1 (`inc-p2-evt-105`, count 5) | Event IDs of counted accesses, class of each, count against threshold |
| AT-P2-01c | Sixth distinct customer | Updates same incident | High | 1 (count 6) | Count 6, new event attached |
| AT-P2-02a | Customers on the agent's assignment list | No alert | none | 0 | Class "assigned", not counted |
| AT-P2-02b | Active (approved, unexpired) delegation | No alert | none | 0 | Class "delegated", not counted |
| AT-P2-02c | Expired delegation (including access exactly at expiry time) | Counted | High once 5 reached | 1 | Class "unassigned", delegation expiry shown |
| AT-P2-03a | Assignment feed unavailable | Not counted | none from these accesses | 0 | "unverified: assignment data missing", feed named as missing evidence |
| AT-P2-03b | Feed answers "no record for customer" | Counted | High once 5 reached | 1 | Class "unassigned" |
| AT-P2-05 (new) | Same unassigned customer opened 5 times | No alert | none | 0 | Distinct count 1 |
| AT-P2-06 (new) | Failed access (permission denied) to unassigned customers | Not counted | none | 0 | Failed accesses not in the count |
| AT-P2-04 | Deck dataset: 120 distinct unassigned customers in one 30-minute window (one access every 10 seconds). `[DECK]`, not a release gate | Opens at the fifth access | High | 1 (distinct count 120) | Distinct count 120, incident opened at fifth access |

### P3: possible privileged account takeover

Five failures and a 600-second window (both demo settings). 600 triggers, 601 does not.

| ID | Input variation | Alert | Severity | Incidents | Evidence that must appear |
|---|---|---|---|---|---|
| AT-P3-01 | Five failures (`evt-201` to `evt-205`), then success from new device `dev-new-91` after 240 seconds (`evt-206`) | Opens incident "possible account takeover" | High | 1 (`inc-p3-evt-206`) | Login sequence in time order, full device history, event IDs `evt-201` to `evt-206` |
| AT-P3-05 (new) | Success exactly 600 seconds after the fifth failure | Opens incident | High | 1 | Gap 600 seconds shown |
| AT-P3-06 (new) | Success 601 seconds after the fifth failure | No alert | none | 0 | Gap 601 seconds, outside window |
| AT-P3-07 (new) | Four failures then new-device success | No alert | none | 0 | Failure count 4 against 5 |
| AT-P3-02a | Five failures, then success from a familiar device | No alert | none | 0 | Device found in history |
| AT-P3-02b | Failures spread across different accounts (for example 5 failures over 3 accounts) | No alert | none | 0 | Per-account failure counts |
| AT-P3-04 | Device history unavailable | No incident | none | 0 | Non-incident item "not evaluated: missing evidence", "device history" named |
| AT-P3-03 | Reviewer requests owner verification | Simulated action recorded | n/a | unchanged | Reviewer identity, recipient (account owner), timestamp |

### Normal and edge accuracy cases

| ID | Input variation | Alert | Severity | Incidents | Evidence that must appear |
|---|---|---|---|---|---|
| AT-ACC-01a | Registry upload: `svc-kyc-registry` uploads `batch-2026-03-12-daily` to `dest-int-registry` with a `registry_batch` approval | No alert | none | 0 | "approved activity", visible within 5 seconds (proposed, not measured) |
| AT-ACC-01b | Auditor export: `acct-auditor-02`, ticket `tkt-audit-114` valid and covering records, time and destination | No alert | none | 0 | "approved activity" with ticket ID |
| AT-ACC-01c | Credit team: `acct-credit-31` downloads 15 files at 23:40. Normal is 10 to 20 per day | No alert (derived from documented rules, no Medium rule exists in the first release) | none | 0 | Normal volume 10 to 20 per day, 15 files observed, rule applied, reason of up to 200 characters: "No alert. 15 files is within this person's normal 10 to 20 per day. No first-release rule covers late-night downloads by non-privileged accounts, and P1 needs more than 100 documents in 5 minutes." |
| AT-ACC-02 (new) | Auditor export with expired ticket, or ticket that does not cover records, time or destination | Standard rules apply (P1 if volume is high) | Critical when P1 conditions pass | 1 | Which check failed |

### Replay, duplicates, isolation and late events

| ID | Input variation | Expected result | Incidents | Evidence that must appear |
|---|---|---|---|---|
| AT-CORE-01a | Duplicate delivery of `evt-002` (same event ID, same run) | Counted once. Window sum stays 170 | 1, event count unchanged | Duplicate noted, no second count |
| AT-CORE-01b | Replay reset, then replay the same dataset a second time | Identical results, IDs and counts both times | Same as first run | Run ID, same incident ID and values |
| AT-CORE-01c | Late arrival: an event with an earlier event time arrives after later events | Windows use event time. Result equals in-order replay | Same as in-order run | Event time and arrival order both visible |
| AT-CORE-03 (new) | Cross-run isolation: two judges each start a run (`run-A`, `run-B`) and replay P1 | Each run has its own incident and counts. Actions in one run never appear in the other | 1 per run | Run ID on every incident and evidence item |
| AT-AI-01 | AI answer cites evidence IDs, including a forced bad citation and a forced timeout | Answers with unknown IDs are rejected. Timeout shows labelled fallback | n/a | Live or fallback label, cited IDs present in evidence |
| AT-RESP-01 | Reviewer approves a proposed simulated action | Action recorded as simulated | unchanged | Who, what, when, label "simulated" |
| AT-CORE-02 | Every task and test cites a requirement ID | Pass | n/a | Requirement IDs listed |

## 2. Blind tests

One blind test per priority scenario. They check that the rules work on cases the rule author did not pick.

| ID | Scenario | Designer | Runner | Task |
|---|---|---|---|---|
| BT-P1 | P1 bulk KYC export | 03 AI and controls (not 01 or 02) | 05 Platform and integration | T4.1, T4.3 |
| BT-P2 | P2 unassigned access | 03 AI and controls (not 01 or 02) | 05 Platform and integration | T4.1, T4.3 |
| BT-P3 | P3 account takeover | 03 AI and controls (not 01 or 02) | 05 Platform and integration | T4.1, T4.3 |

Rules:

1. The designer writes cases from [scenarios.md](scenarios.md) thresholds only, without reading rule code.
2. Each set includes cases near each boundary, benign look-alikes, and missing-evidence cases.
3. Expected outcomes (alert or no alert, severity, incident count, evidence) are sealed: committed to the repository before any blind run. [decisions.md](decisions.md) records the designer and confirms they did not author the rules for that scenario.
4. The runner replays the set through the harness (T4.2) and does not see or change expected outcomes during the run.
5. Scoring compares each case to its sealed outcome. A case is correct only if alert state, severity and incident count all match.
6. No rule or threshold is tuned on the blind set. A fix goes into [decisions.md](decisions.md) first. A fixed rule is then tested on a new set, not this one.
7. Each miss or false alarm is explained in the results with its case ID.
8. Each figure carries its date and method. A figure not from a run is "proposed, not measured".

## 3. Metrics

Counts are per case. Prioritised scenarios (P1, P2, P3) and accuracy cases (AT-ACC) are reported separately.

| Metric | Definition | Formula |
|---|---|---|
| Correct alerts | Cases where an alert was expected and the system raised it with the expected severity and incident count | Count of cases with expected alert and matching result. Also shown as a share of cases that expect an alert |
| False alarms | Cases where no alert was expected and the system raised one (or raised a higher severity than expected) | Count of such cases. Share = false alarms / cases that expect no alert |
| Missed cases | Cases where an alert was expected and the system raised none (or a lower severity) | Count of such cases. Share = missed / cases that expect an alert |
| Time to alert | Event time of the first relevant event to the moment the incident is visible on the dashboard | Report two figures: event-time gap (alert event time minus first relevant event time) and wall-clock replay time (incident visible time minus replay start) |
| AI citation accuracy | Share of cited evidence IDs that exist in the incident's evidence | Cited IDs that exist in evidence / total cited IDs. Report live and fallback answers separately, with counts of rejections by reason |

### Results (blank until measured)

Method and date go beside each figure when it is measured (T4.3, T4.4).

| Metric | P1 | P2 | P3 | Accuracy cases | Actual |
|---|---|---|---|---|---|
| Correct alerts | not yet measured | not yet measured | not yet measured | not yet measured | not yet measured |
| False alarms | not yet measured | not yet measured | not yet measured | not yet measured | not yet measured |
| Missed cases | not yet measured | not yet measured | not yet measured | not yet measured | not yet measured |
| Time to alert (event time) | not yet measured | not yet measured | not yet measured | n/a | not yet measured |
| Time to alert (wall-clock replay) | not yet measured | not yet measured | not yet measured | n/a | not yet measured |
| AI citation accuracy, live answers | not yet measured | not yet measured | not yet measured | n/a | not yet measured |
| AI citation accuracy, fallback answers | not yet measured | not yet measured | not yet measured | n/a | not yet measured |

Timing targets from T4.8 are listed in [tasks.md](../../.kiro/specs/finshield-ai/tasks.md) and stay "proposed, not measured" until a run is recorded.

## 4. Business-value experiment (T4.7)

Status: **proposed, not measured**. Question: does the dashboard let an analyst reach an evidence-backed conclusion faster than raw logs?

Protocol:

- **Participants:** 4 to 6 people who have not seen the cases (proposed, not measured). Record the actual number and their background.
- **Case pairs:** for each of P1, P2 and P3, build two comparable cases (A and B) of similar size and difficulty. Both have a known correct answer.
- **Conditions:** raw synthetic event files (searching with a text viewer or spreadsheet) versus the FinShield dashboard.
- **Counterbalancing:** half the participants do case A with raw logs and case B with the dashboard. The other half swap. Order of scenarios is rotated across participants.
- **Timed:** from the moment the participant is given the case to the moment they state a conclusion. Also record steps taken (opens, searches, clicks).
- **Correct answer:** the participant names the right actor or account, the right conclusion (alert or no alert, and which rule), and at least the key evidence IDs listed in the answer key. A wrong or incomplete answer is recorded as incorrect and its time is reported separately, not averaged in silently.
- **Reported:** median time and steps per condition and per scenario, share of correct answers, number of participants, method and date.

| Scenario | Raw logs: median time | Dashboard: median time | Correct (raw) | Correct (dashboard) | Status |
|---|---|---|---|---|---|
| P1 | not yet measured | not yet measured | not yet measured | not yet measured | proposed, not measured |
| P2 | not yet measured | not yet measured | not yet measured | not yet measured | proposed, not measured |
| P3 | not yet measured | not yet measured | not yet measured | not yet measured | proposed, not measured |

Any time or cost saving stated in the demo carries "proposed, not measured" until this table is filled.

## 5. Five-minute judge walkthrough

The demo uses P1 first. Run on the local path, no network needed. Every step shows its reason on screen.

| Time | Step | What the judge sees |
|---|---|---|
| 0:00 to 0:30 | Context. Say that all data is synthetic and the settings are demo settings. | Dashboard home with the run ID |
| 0:30 to 1:30 | Replay two KYC exports of equal size, 130 documents each, by privileged accounts with normal range 5 to 10. Place them in separate windows or on separate accounts so the sums do not combine. Export 1 has a valid scoped approval. Export 2 is outside its approval (destination mismatch). | Export 1: "approved activity", no Critical alert. Export 2: one Critical incident, reason "Approval does not match: approved destination X, export destination Y". Files and customers shown as two figures |
| 1:30 to 2:30 | The judge changes one input and replays: fix the destination, or move the approval expiry past the export time. Replay. | Export 2 changes to approved activity, or (if expiry is moved earlier) an expired approval keeps the Critical. The reason line shows exactly what changed |
| 2:30 to 3:15 | P2: replay the five-customer access sequence, then the judge changes one value (for example marks one customer assigned). | Incident opens at the fifth distinct unassigned customer, or stays at 4 after the change. Count and class of each access shown |
| 3:15 to 3:45 | P3: replay five failures then a new-device login. Judge changes the gap to 601 seconds or the device to a known one. | High "possible account takeover" with sequence and device history, then no incident after the change |
| 3:45 to 4:30 | AI answer. Ask: "Was this export covered by a valid audit approval?" on the Critical incident. | Answer cites evidence IDs (approval lookup `al-evt-002`, rule result `rr-evt-002-p1`, event IDs). Each cited ID is checked against evidence. Label "live" or "fallback" |
| 4:30 to 5:00 | Review history. A reviewer approves a proposed action (for example request verification). | Review history shows who, what, when, and the label "simulated". Close with the deployment status from [README.md](README.md) and any "proposed, not measured" figure labelled |

Fallback if Bedrock is unavailable (or T4.5 was skipped):

1. The investigator returns the deterministic fallback explanation built from the same evidence.
2. The dashboard labels it "fallback", not "live". Never describe a fallback answer as a live model call.
3. The citation check still runs on the fallback answer.
4. The script keeps the same question and evidence IDs, so the judge sees the same flow.
5. Say plainly which one is shown. Live figures are claimed only if a live call was made (T4.4).

The rehearsal (T4.11) needs two timed run-throughs without a code change. Prepare answers for "proposed, not measured" figures and for the DPDP-aligned wording.

## 6. Criteria map

| Judging criterion | Visible proof | Proof type |
|---|---|---|
| Problem understanding | Three priority scenarios (P1, P2, P3) told as business stories with synthetic KYC and access data, shown in the walkthrough | Live interaction |
| Solution depth | Rule results with each condition, approval matching on five checks, incident grouping and updates, change-one-value replay | Live interaction |
| Industry fit | Lender workflows: KYC exports, collection agent access, privileged logins, auditor and registry normal cases | Live interaction |
| Compliance fit | Wording "DPDP-aligned readiness and controls". Alerts may suggest a compliance review, never state a legal breach. Regulatory items "needs official verification". Review history with who, what, when | Test result (AT-RESP-01, wording checks) |
| Technical architecture | Architecture and deployment status table in [README.md](README.md). Offline smoke tests, repository contract tests | Proposed deployment diagram, plus test result (T4.9) |
| Threat detection and accuracy | Test matrix results, blind tests BT-P1, BT-P2, BT-P3, correct alerts, false alarms, missed cases, time to alert | Test result (not yet measured) |
| AI innovation | AI answer with evidence IDs, citation check, rejection of unknown IDs, labelled live or fallback | Live interaction, plus test result (AT-AI-01, citation accuracy not yet measured) |
| Prototype accuracy | Approved and unapproved export pair, boundary cases (100 vs 101, 600 vs 601), duplicate and replay determinism | Live interaction, plus test result (AT-P1-*, AT-CORE-01) |
| Business viability | Investigation time with raw logs versus dashboard | Measured business result when T4.7 is done. Until then "proposed, not measured". Deployment path shown as a proposed deployment diagram |

## 7. Sign-off

| Step | Owner | Status |
|---|---|---|
| Integration tests (T2.15, T3.11, T4.9) | 05 Platform and integration | not yet run |
| Blind test run (T4.3) | 05 Platform and integration | not yet run |
| Final acceptance sheet for every AT-* ID (T4.10) | 04 Dashboard and workflow | not yet run |
| Walkthrough rehearsal (T4.11) | 03 AI and controls | not yet run |
