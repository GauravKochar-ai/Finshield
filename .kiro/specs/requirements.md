# Requirements Document

## Introduction

FinShield AI, built by Team Global Nodes for the AI FORGE 2026 enterprise GenAI hackathon, helps the security team of a fictional Indian digital lender investigate unusual access to customer identity documents, loan records, and privileged accounts. The official demo shows a privileged account exporting an unusual volume of KYC documents, a critical alert, and an evidence trail.

This release delivers exactly three priority detection scenarios end to end: **P1**, **P2**, **P3**. Approved business activities (for example a scheduled registry upload) are accuracy tests, counted separately from the three scenarios. A judge must be able to change one input, replay, and see the result change for an understandable reason.

This document is planning only. No application code is part of this deliverable.

**Users**
- **Primary user:** the lender's security analyst, who triages alerts and investigates incidents.
- **Secondary reviewer:** the security lead, who approves simulated response actions and checks the evidence.

**Source tags.** Each requirement carries one tag so the team can see what is mandatory.
- `[BRIEF]`: required by the hackathon brief or the official demo.
- `[TEAM]`: a decision made by Team Global Nodes. It can be changed through `decisions.md`.
- `[DECK]`: an optional idea from the pitch deck. It is not a release gate.
- `[PROPOSED]`: a value or approach that is not yet measured or verified. Treat it as a starting point. Any timeout, range, or sample size carrying this tag is a demo or proposed setting, not a measured figure.

**Where facts live.** To keep one primary home for each fact, this file states *what the system must do*. Details live elsewhere:
- Scenario data, numbers, scoring and severity rules: [scenarios.md](../../../docs/finshield/scenarios.md)
- API and event payloads, versioning: [contracts.md](../../../docs/finshield/contracts.md)
- Demo script and acceptance tests: [demo-and-evaluation.md](../../../docs/finshield/demo-and-evaluation.md)
- Decision log: [decisions.md](../../../docs/finshield/decisions.md)
- Team overview and role guides: [README.md](../../../docs/finshield/README.md), [roles/](../../../docs/finshield/roles/)

These handoff files are written in a later phase. Links will resolve once they exist.

## Glossary

- **KYC (Know Your Customer)**: The identity checks a lender must do before giving a loan. KYC documents are the files collected for this, such as ID cards, address proof, and photos. They are highly sensitive.
- **NBFC (Non-Banking Financial Company)**: A regulated Indian lender that is not a bank. The fictional lender in this project is a digital NBFC.
- **Baseline**: What is normal for one account (or one role) over time, for example "this admin exports 5 to 10 documents in a five-minute period". A baseline is calculated only from normal activity.
- **Incident**: One tracked case in FinShield AI. It groups related events, has a severity (Critical, High, Medium), and is updated as new events arrive instead of creating duplicates.
- **Evidence trail**: The ordered list of events, rule results, approval lookups, and actions that explain why an incident exists. Every item has an ID so a reader can trace any claim back to its source.
- **FinShield_System**: The whole FinShield AI product.
- **Intake_Service**: The part that receives and validates events.
- **Replay_Engine**: The part that feeds stored synthetic events through detection in event-time order, inside a Replay_Run.
- **Detection_Engine**: The part that applies the documented rules and decides whether an alert is raised and at what severity. It is deterministic. It contains no AI.
- **Incident_Manager**: The part that opens, updates, and groups incidents.
- **AI_Investigator**: The part that uses Amazon Bedrock to explain an incident from masked facts and evidence IDs.
- **Response_Controller**: The part that proposes, approves, and records simulated response actions.
- **Evidence_Store**: The storage for events, incidents, evidence trails, and the action history.
- **Dashboard**: The React web interface used by the analyst and security lead.
- **Event**: One recorded action, such as a document export, a record access, or a login attempt. Each has a unique event ID and an event time.
- **Event time**: When the action happened in the data, not when FinShield AI received it.
- **Replay_Run**: One isolated execution of a stored event set, identified by a run ID. Data from different runs never mix.
- **Rolling window**: A time span that moves with each new event. A five-minute rolling window at time T covers events after T minus five minutes up to and including T.
- **Privileged account**: An account with administrative rights over customer data or systems.
- **Approval**: A record that a specific activity was authorised. To count, it must cover actor, operation, records, time window, and destination.
- **Observed export**: An event shows documents were exported from the system.
- **Attempted upload**: An event shows an upload request was made to a destination, with no proof it completed.
- **Confirmed transfer**: An event or receipt shows the destination received the data.
- **Successful empty result**: A lookup or check ran correctly and found nothing.
- **Missing evidence**: Data needed for a conclusion was not available, for example a source was down.
- **Invalid input**: An event or request that fails the contract.
- **Masked incident facts**: Incident data with names and customer identifiers replaced by placeholders before leaving the system for Bedrock.
- **Fallback summary**: A plain, template-based summary shown when Bedrock is unavailable. It is always labelled as such.
- **Contract**: The documented, versioned shape of an event or API payload.
- **DPDP-aligned readiness and controls**: The project's wording for supporting readiness under India's Digital Personal Data Protection Act. It does not claim compliance or a legal finding.

## Requirements

### Requirement 1: Users, scope, and release boundary

**User Story:** As a team member, I want a clear scope, so that we build exactly three priority scenarios and do not drift.

#### Acceptance Criteria

1. THE FinShield_System SHALL deliver exactly three priority detection scenarios in the first release, identified as P1, P2, and P3, and SHALL NOT include a fourth priority detection scenario in the first-release build. `[BRIEF]`
2. THE FinShield_System SHALL give the security analyst access to alerts, alert details, and analyst actions (triage, investigation, and requests for response actions), and SHALL give the security lead access to the same views plus the ability to approve or reject simulated response actions as defined in Requirement 14. `[BRIEF]`
3. WHEN the official demo is run, THE FinShield_System SHALL present P1 as the first scenario and SHALL complete the P1 end-to-end flow, from input event to displayed detection result, before the demo ends. `[BRIEF]`
4. THE FinShield_System SHALL count approved business activities and the Requirement 12 edge cases as accuracy tests, excluded from the count of three priority scenarios. `[TEAM]`
5. IF a dataset contains a record not marked synthetic, THEN THE Intake_Service SHALL reject that record, exclude it from processing, and indicate the rejection to the user, so that only synthetic customer data is used. `[BRIEF]`
6. THE FinShield_System SHALL keep the Requirement 21 detections outside the critical path, so that P1, P2, P3, and the demo run with all Requirement 21 detections disabled or absent. `[TEAM]`
7. WHEN P1, P2, and P3 are each run live or replayed, THE FinShield_System SHALL produce a detection result for each, satisfying the minimum of three scenarios. `[BRIEF]`

### Requirement 2: Event intake and validation

**User Story:** As a security analyst, I want events accepted in one agreed format, so that every detection works from the same data.

#### Acceptance Criteria

1. WHEN an event is submitted, THE Intake_Service SHALL validate it against the current Contract version and return a validation result within 500 ms for events up to 1 MB. `[TEAM]` `[PROPOSED]`
2. WHEN an event passes validation, THE Intake_Service SHALL store it in the Evidence_Store with its event ID, event time, actor, operation, and Replay_Run ID, and return an acceptance result. `[TEAM]`
3. IF an event fails validation, THEN THE Intake_Service SHALL reject it, return the names of all failing fields (up to 50), and store no part of the event. `[TEAM]` `[PROPOSED]`
4. IF an event is submitted with an event ID already stored in the same Replay_Run, THEN THE Intake_Service SHALL keep the first copy, discard the duplicate, exclude it from every count, and return a result indicating a duplicate. `[TEAM]`
5. THE Intake_Service SHALL accept the same event format from the local path and the proposed AWS path and return the same validation result through either path. `[TEAM]`
6. WHEN an event carries document records, THE Intake_Service SHALL require a document ID and a customer ID for each record, so that total files and distinct customer IDs can be calculated. `[TEAM]`
7. IF any document record lacks a document ID or a customer ID, THEN THE Intake_Service SHALL reject the event and return the position of the record and the name of the missing field. `[PROPOSED]`
8. IF the reported record count differs from the number of listed document IDs, THEN THE Intake_Service SHALL reject the event as invalid input, return a count mismatch error with both numbers, and store nothing. `[PROPOSED]`

### Requirement 3: Synthetic data and baseline

**User Story:** As a judge, I want normal behaviour generated and learned from synthetic data, so that I can see detection is not hard-coded to the demo.

#### Acceptance Criteria

1. WHEN a demo run is initialised, THE FinShield_System SHALL generate normal activity for each account used in P1, P2, and P3, covering at least 7 consecutive days per account and at least 30 samples per metric per account. `[TEAM]` `[PROPOSED]`
2. THE FinShield_System SHALL calculate one baseline per metric per account from the generated normal activity only. `[TEAM]`
3. THE FinShield_System SHALL exclude every injected suspicious event from baseline calculation, so that the stored sample size equals the count of generated normal samples only. `[TEAM]`
4. WHEN a baseline is calculated, THE FinShield_System SHALL store the account, the metric, the normal range (lower end less than or equal to upper end), the sample size (30 or more), and the period (start and end timestamps). `[TEAM]` `[PROPOSED]`
5. THE FinShield_System SHALL generate the P1 admin baseline as 5 to 10 documents per five-minute period, inclusive, in every five-minute period of the baseline period. `[BRIEF]`
6. IF fewer than 30 normal samples exist for an account and metric, THEN THE FinShield_System SHALL not store a baseline, SHALL report an error naming the account and the metric, and SHALL retain the samples. `[TEAM]` `[PROPOSED]`
7. WHERE the baseline method is changed, THE FinShield_System SHALL record the previous method, the new method, and the reason in decisions.md before the new method is used in the demo. `[TEAM]`

### Requirement 4: Replay

**User Story:** As a judge, I want to change an input and replay, so that I can see why the result changed.

#### Acceptance Criteria

1. WHEN a judge starts a replay, THE Replay_Engine SHALL create a new Replay_Run with a unique run ID and return it within 2 seconds. `[TEAM]` `[PROPOSED]`
2. THE Replay_Engine SHALL process events in ascending event-time order regardless of arrival order, breaking ties by ascending event ID. `[TEAM]`
3. THE Replay_Engine SHALL keep the events, configuration, incidents, and counts of each Replay_Run isolated from every other run. `[TEAM]`
4. WHEN the same event set and the same configuration are replayed again, THE Replay_Engine SHALL produce identical incidents, severities, and counts in 100% of repeated runs. `[TEAM]`
5. WHEN a judge changes exactly one input value or configuration value and replays, THE Dashboard SHALL show the changed incidents, severities, and counts next to the previous result, with the rule condition that caused each change, within 10 seconds of the replay finishing. `[BRIEF]`
6. WHEN a replay is repeated for a run ID that already exists, THE Replay_Engine SHALL keep the number of incidents per grouped activity at one and leave the run's incident count unchanged. `[TEAM]`
7. THE Replay_Engine SHALL replay P1 from a stored file of synthetic events with no connection to any live system. `[BRIEF]`
8. IF the stored event file is missing, unreadable, or unparseable, THEN THE Replay_Engine SHALL not start the run, keep existing runs unchanged, and show a file error. `[TEAM]`
9. IF a changed input or configuration value is outside its allowed range or type, THEN THE Replay_Engine SHALL reject the replay, keep the previous result displayed, and show which value is invalid. `[TEAM]`

### Requirement 5: Deterministic detection core

**User Story:** As a security analyst, I want alerts produced by documented rules, so that I can trust and test them.

#### Acceptance Criteria

1. THE Detection_Engine SHALL decide alert creation and severity only from documented rules and configuration values, never from AI output. `[TEAM]`
2. THE Detection_Engine SHALL keep every rule threshold configurable, with demo values as defaults. `[BRIEF]`
3. THE Detection_Engine SHALL calculate rolling windows from event time, not from arrival time or the system clock. `[TEAM]`
4. WHEN an event arrives late with an event time inside an already evaluated window, THE Detection_Engine SHALL re-evaluate that window and update every affected incident within 5 seconds of the arrival. `[TEAM]` `[PROPOSED]`
5. WHEN an event ID has already been counted in the same Replay_Run, THE Detection_Engine SHALL ignore the duplicate for all counts and leave rule results and incidents unchanged. `[TEAM]`
6. WHEN the Detection_Engine evaluates a rule, THE Detection_Engine SHALL store each condition, the value seen, the limit, and the pass or fail result. `[TEAM]`
7. IF a condition cannot be evaluated because evidence is missing, THEN THE Detection_Engine SHALL record that condition as "not evaluated: missing evidence", name the missing source, and not count the condition as a pass. `[TEAM]`
8. THE Detection_Engine SHALL define "more than N" as N plus one or higher and "at least N" as N or higher. `[TEAM]`
9. IF a configured threshold is missing, non-numeric, or negative, THEN THE Detection_Engine SHALL reject it, keep the previous valid value (or the demo default if none exists), and report an error naming the rule and the threshold. `[TEAM]`

*Example:* with the document limit set to 100, exactly 100 documents does not trigger and 101 does. With "at least five times an upper end of 10", 50 qualifies and 49 does not.

### Requirement 6: P1 unusual bulk KYC export by a privileged account

**User Story:** As a security analyst, I want a critical alert when a privileged account exports an unusual volume of KYC documents without approval, so that I can act before data leaves the lender.

#### Acceptance Criteria

1. WHEN an export event is received and, for the same account, the sum of documents exported in the five-minute rolling window ending at that event exceeds 100, that sum is at least five times the upper end of the account's normal range, the account is privileged, and no valid approval covers the export, THE Detection_Engine SHALL raise a Critical alert. `[BRIEF]`
2. THE Detection_Engine SHALL keep the window length (minutes), document limit, multiplier, and privileged-access condition configurable without code changes, and SHALL apply a changed value to export events received after the change. `[BRIEF]`
3. WHEN the P1 events are replayed (80 documents at 10:00, 90 at 10:02, 130 at 10:04, same account), THE Detection_Engine SHALL raise no alert on the first event, because 80 is not above 100. `[BRIEF]`
4. WHEN the second P1 event arrives, THE Incident_Manager SHALL open exactly one Critical incident, because the total of 170 is above 100 and at least 50. `[BRIEF]`
5. WHEN the third P1 event arrives, THE Incident_Manager SHALL update the same incident, without opening a second incident, to a total of 300 documents and attach the third event. `[BRIEF]`
6. THE P1 test data SHALL use an export time within normal office hours, a device already known for the account, and an internal destination, so that the export volume alone proves Critical severity. `[TEAM]`
7. IF the account's personal history has fewer samples than the minimum sample size or is unavailable, THEN THE Detection_Engine SHALL use the role-level baseline of comparable privileged accounts and label the incident "baseline: role-level". `[PROPOSED]`
8. IF neither a personal nor a role-level baseline is available, THEN THE Detection_Engine SHALL record the multiplier condition as not evaluated, open the incident as High, and list "baseline" as missing evidence. `[PROPOSED]`
9. IF the approvals lookup is unavailable, THEN THE Detection_Engine SHALL record the approval condition as not evaluated, open the incident as High, list "approvals source" as missing evidence, and retain the export event and every other evaluated condition. The export is treated as "not confirmed covered", which is not proof of wrongdoing. `[PROPOSED]`
10. WHEN the approvals lookup later succeeds and finds no covering approval for an incident opened under criterion 9, THE Incident_Manager SHALL raise the same incident to Critical without opening a new incident and SHALL remove "approvals source" from the missing evidence. `[PROPOSED]`
11. WHEN an incident is opened or updated, THE Detection_Engine SHALL calculate and show total files (the sum of exported documents) and affected customers (the count of distinct customer IDs) as two separate figures. `[BRIEF]`

*Example:* the three exports contain 300 files across 180 distinct customer IDs, because some customers have several files. The Dashboard shows "300 files, 180 customers", never one figure for both. The counts are illustrative.

### Requirement 7: P1 approval matching

**User Story:** As a security analyst, I want exports checked against approvals, so that authorised work is recorded without noise and unauthorised work is not hidden.

#### Acceptance Criteria

1. THE Detection_Engine SHALL treat an approval as covering an export only IF the approval actor equals the export actor, the approval operation equals the export operation, every exported record is within the approved record scope, the export time is at or after the approval start and before the approval expiry, and the export destination equals the approved destination. `[BRIEF]`
2. THE FinShield_System SHALL represent record scope in the fake approval data as exactly one scope type plus values: a list of 1 to 1,000 customer IDs, a document type with a customer segment, or a registry batch ID. `[TEAM]` `[PROPOSED]`
3. WHEN a valid scoped approval covers an export, THE Incident_Manager SHALL record the activity as "approved activity" and SHALL NOT raise a Critical alert. `[BRIEF]`
4. IF the export time is at or after the approval expiry, THEN THE Detection_Engine SHALL treat the approval as not covering the export, keep the incident open, and show the expiry time and the export time. `[BRIEF]`
5. IF the approval references an unrelated ticket, or its actor, operation, or record scope differs from the export, THEN THE Detection_Engine SHALL treat the approval as not covering the export, keep the incident open, and show which of ticket, actor, operation, or record scope did not match. `[BRIEF]`
6. IF the export destination differs from the approved destination, THEN THE Detection_Engine SHALL keep the incident open and show the approved destination and the export destination. `[BRIEF]`
7. IF an approval covers fewer than all exported records, THEN THE Detection_Engine SHALL keep the incident open and show the integer count of uncovered records. `[PROPOSED]`
8. WHEN an approval lookup completes, or fails to complete within 5 seconds, THE Dashboard SHALL state exactly one of: returned a match, returned no match, or unavailable. `[TEAM]` `[PROPOSED]`
9. IF the approvals lookup is unavailable, THEN THE Detection_Engine SHALL treat the export as "not confirmed covered" and apply Requirement 6, criterion 9 (open as High, list "approvals source" as missing evidence), and SHALL NOT treat the unavailable lookup as proof of wrongdoing. `[PROPOSED]`

*Example:* an approval for 100 documents to the audit share does not cover 130 documents, and it does not cover an export to a different share.

### Requirement 8: P1 external upload variation

**User Story:** As a security analyst, I want external upload evidence added to a P1 incident, so that I can judge how far the data may have travelled.

#### Acceptance Criteria

1. WHEN an upload event to an external destination is received for an account with an open P1 incident that contains at least one export event, and the upload timestamp is later than the earliest export timestamp, THE Incident_Manager SHALL attach the upload to the existing incident as additional evidence within 5 seconds and SHALL NOT open a new incident. `[BRIEF]` `[PROPOSED]`
2. THE FinShield_System SHALL label each transfer-related fact with exactly one of "observed export", "attempted upload", or "confirmed transfer". `[TEAM]`
3. WHEN an upload event reports only that the upload was requested or started, THE FinShield_System SHALL label it "attempted upload". `[TEAM]`
4. WHEN an event or receipt states that the external destination received the data, THE Dashboard SHALL show "confirmed transfer". `[TEAM]`
5. IF no such event or receipt exists, THEN THE Dashboard SHALL NOT show "confirmed transfer" for any upload fact. `[TEAM]`
6. WHEN an upload is attached, THE Detection_Engine SHALL keep the incident severity at Critical, identical to the severity without the upload. `[TEAM]`
7. IF an upload cannot be attached (for example the incident is closed or a failure occurs), THEN THE Incident_Manager SHALL leave the evidence unchanged and show the analyst an error. `[TEAM]`

*Example:* an event "upload requested to external-host-7" is an attempted upload. It does not prove the data arrived.

### Requirement 9: P2 collection agent or loan officer accessing unassigned customers

**User Story:** As a security analyst, I want to see when staff open customer records they are not assigned to, so that I can find misuse by collection partners and loan officers.

#### Acceptance Criteria

1. WHEN a collection agent or loan officer makes a record access, THE Detection_Engine SHALL compare it with the assignments and delegations valid at the access event time and classify it as exactly one of: assigned, delegated, unassigned, or unverified. `[BRIEF]`
2. THE Detection_Engine SHALL count only successful accesses classified as unassigned, and SHALL NOT count failed accesses. `[TEAM]`
3. THE Detection_Engine SHALL keep a count of distinct unassigned customer IDs per actor per rolling window. `[BRIEF]`
4. WHEN the distinct unassigned count for one actor in the window reaches the threshold, THE Incident_Manager SHALL open exactly one High incident for that actor at the access that reaches it. `[PROPOSED]`
5. THE Detection_Engine SHALL default the P2 threshold to 5 distinct unassigned customers in a 30-minute rolling window, with both values configurable (threshold: integer 1 to 1,000; window: 1 to 1,440 minutes). `[PROPOSED]`
6. WHEN a later unassigned access by the same actor occurs while the incident is open, THE Incident_Manager SHALL update the same incident with the new distinct count and attach the event, without opening a second incident. `[TEAM]`
7. WHEN the same customer is accessed more than once in the window, THE Detection_Engine SHALL count that customer once. `[TEAM]`
8. WHEN an access is covered by a valid assignment, THE Detection_Engine SHALL record it as normal and not count it. `[BRIEF]`
9. WHEN an access is covered by an approved, unexpired delegation, THE Detection_Engine SHALL record it as delegated and not count it. `[BRIEF]`
10. IF a delegation expired before the access, THEN THE Detection_Engine SHALL classify the access as unassigned and count it. `[BRIEF]`
11. IF the assignment source returns an error or does not respond within 5 seconds, THEN THE Detection_Engine SHALL mark the access "unverified: assignment data missing", list the source as missing evidence, and not count the access. `[BRIEF]` `[PROPOSED]`
12. IF an assignment lookup succeeds and returns no record for the customer, THEN THE Detection_Engine SHALL classify the access as unassigned and count it. `[TEAM]`
13. THE Detection_Engine SHALL process the P2 dataset in which one collection partner opens 120 distinct unassigned customer records, and SHALL open one High incident with a distinct unassigned count of 120 after all records are processed. `[DECK]`

*Example:* the assignment feed returning "no record for customer C-17" is a successful empty result, so the access counts. The feed timing out is missing evidence, so the access does not count and the Dashboard says why.

### Requirement 10: P3 possible privileged account takeover

**User Story:** As a security analyst, I want to see failed logins followed by a login from a new device on the same admin account, so that I can check for takeover quickly.

#### Acceptance Criteria

1. WHEN a successful login occurs on a privileged account from a device not in that account's device history, and the same account has 5 or more distinct failed login events, and the success occurs 0 to 600 seconds (inclusive) after the fifth failure, THE Incident_Manager SHALL open exactly one High incident labelled "possible account takeover". `[BRIEF]`
2. THE Detection_Engine SHALL count failed logins per account identifier only and SHALL NOT combine failures across accounts. `[BRIEF]`
3. WHEN the incident is opened, THE Incident_Manager SHALL display the login sequence in chronological order (timestamp, outcome, device), the full device history of the account, and the event IDs of every failed and successful login used. `[BRIEF]`
4. WHEN a successful login follows 5 or more failed logins from a device already in the account's device history, THE Detection_Engine SHALL NOT open an incident. `[BRIEF]`
5. WHEN a reviewer requests account-owner verification, THE Response_Controller SHALL record one verification request with the reviewer identity, the account owner as recipient, and a timestamp. `[BRIEF]`
6. IF the device history is unavailable, THEN THE Detection_Engine SHALL NOT open an incident as "possible account takeover", SHALL record "not evaluated: missing evidence" with "device history" named as the missing source, and THE Dashboard SHALL show that missing source as a visible non-incident item. `[TEAM]`
7. THE Detection_Engine SHALL keep the failed-login count (default 5, range 1 to 100), the window (default 600 seconds, range 60 to 86,400 seconds), and the device-history rule configurable, and SHALL apply changes to evaluations made after the change is saved. `[TEAM]` `[PROPOSED]`
8. IF a configuration value is outside its range, THEN THE Detection_Engine SHALL reject it, keep the previous value, and return an error naming the invalid value. `[TEAM]`

*Example:* four failures then a new device does not trigger. Five failures spread over three accounts does not trigger either. Five failures on one account then a new-device success 601 seconds after the fifth failure does not trigger.

### Requirement 11: Incident updates and grouping

**User Story:** As a security analyst, I want related events grouped into one incident, so that I am not flooded with duplicates.

#### Acceptance Criteria

1. WHEN an event arrives, THE Incident_Manager SHALL assign it to an existing open incident if the scenario, the actor, and the Replay_Run are the same and the event timestamp is within 15 minutes of the incident's most recent event timestamp. The 15-minute grouping window is a proposed demo setting; the P1 rule uses its own 5-minute window and the P3 rule its own 10-minute window. `[TEAM]` `[PROPOSED]`
2. IF no open incident matches, THEN THE Incident_Manager SHALL create a new incident with an event count of 1. `[TEAM]`
3. WHEN a new matching event arrives, THE Incident_Manager SHALL increase the incident's event count by 1 and append the event to the evidence trail, without creating a new incident. `[BRIEF]`
4. WHEN an incident is updated, THE Incident_Manager SHALL record the update time (UTC, millisecond precision) and the IDs of the events that caused the update. `[TEAM]` `[PROPOSED]`
5. THE Incident_Manager SHALL set severity to the value defined by the matched documented rule. `[TEAM]`
6. IF new evidence changes the severity, THEN THE Incident_Manager SHALL record the old severity, the new severity, the rule ID, and the change time, and SHALL retain previous history entries. `[TEAM]`
7. IF an event ID is already in the incident's evidence trail, THEN THE Incident_Manager SHALL leave the event count, evidence trail, and severity unchanged. `[TEAM]`
8. THE Incident_Manager SHALL keep incidents of different Replay_Runs separate. `[TEAM]`

### Requirement 12: Approved activities and edge cases

**User Story:** As a judge, I want to see normal activity stay quiet and borderline activity explained, so that I can trust the accuracy.

#### Acceptance Criteria

1. WHEN a scheduled daily KYC registry upload by an approved system account goes to an approved destination, THE FinShield_System SHALL record it as approved activity with zero alerts and show it on the Dashboard within 5 seconds. `[TEAM]` `[PROPOSED]`
2. WHEN an auditor exports records under a ticket that is valid at export time and covers the records, the time, and the destination, THE FinShield_System SHALL record it as approved activity with zero alerts and show it on the Dashboard within 5 seconds. `[TEAM]` `[PROPOSED]`
3. IF the auditor ticket has expired, or its scope does not cover the records, time, or destination, THEN THE FinShield_System SHALL NOT record the export as approved activity, SHALL evaluate it under the standard alert rules, and SHALL show which check failed. `[TEAM]`
4. WHEN a credit team member downloads 15 files between 22:00 and 05:59 local time (the "late at night" hours, a configurable demo setting), THE Dashboard SHALL show that person's normal daily download volume, the 15 files observed, and the rule applied within 5 seconds. `[TEAM]` `[PROPOSED]`
5. IF the evidence is insufficient for a Medium alert, THEN THE Dashboard SHALL display the actual result (no alert or a lower severity) with a reason of up to 200 characters naming the criterion not met, and SHALL NOT show a Medium alert. `[TEAM]` `[PROPOSED]`
6. THE FinShield_System SHALL count criteria 1 to 5 as accuracy tests, reported separately and scored pass or fail against the expected result. `[TEAM]`
7. THE FinShield_System SHALL define in scenarios.md, for each case, the input events, the expected outcome (alert or none, and severity), and the expected Dashboard content. The expected result for criteria 4 and 5 is derived from the documented rule in scenarios.md. `[TEAM]`

### Requirement 13: AI investigation

**User Story:** As a security analyst, I want a clear AI explanation of an incident that cites real evidence, so that I can investigate faster without being misled.

#### Acceptance Criteria

1. WHEN an analyst requests an investigation, THE AI_Investigator SHALL send Amazon Bedrock only masked incident facts and evidence IDs, with no unmasked customer identifier. `[BRIEF]`
2. THE AI_Investigator SHALL present exactly four labelled parts: what happened, supporting evidence, what remains unknown, and one next check (a single action of at most 300 characters). `[TEAM]` `[PROPOSED]`
3. THE AI_Investigator SHALL cite only evidence IDs that exist in the incident's evidence trail. `[TEAM]`
4. WHEN a Bedrock answer is received, THE AI_Investigator SHALL validate it within 2 seconds and reject it if it cites an unknown evidence ID, states a customer count that differs from the incident's evidence, or states a legal finding. `[TEAM]` `[PROPOSED]`
5. IF the answer is rejected, THEN THE AI_Investigator SHALL discard it, display a fallback summary labelled as a fallback, and record the rejection and its reason. `[TEAM]`
6. IF Bedrock gives no response within 10 seconds or returns an error, THEN THE AI_Investigator SHALL show the detection results with a labelled fallback summary and indicate that the live model is unavailable. The 10-second limit is a proposed demo setting, shared with Requirement 17, criterion 5. `[TEAM]` `[PROPOSED]`
7. THE Evidence_Store SHALL record whether each explanation came from the live model or the fallback, linked to the incident and the request time. `[TEAM]`
8. WHEN asked "Was this export covered by a valid audit approval?" and the approvals lookup succeeded with zero matches, THE AI_Investigator SHALL answer that no matching approval was found. `[TEAM]`
9. WHEN asked the same question and the approvals source was unavailable, THE AI_Investigator SHALL answer that approval status is unknown and name the source, without stating that an approval exists or does not exist. `[TEAM]`
10. THE AI_Investigator SHALL NOT modify the severity or alert state of any incident, which SHALL be identical before and after an explanation. `[TEAM]`

### Requirement 14: Controlled response

**User Story:** As a security lead, I want response actions proposed and approved by a person, so that nothing runs without review.

#### Acceptance Criteria

1. WHEN an incident is opened, THE Response_Controller SHALL propose at least 1 and at most 10 simulated actions, each of a supported type (suspend account or request verification) and each with the status "pending approval". `[BRIEF]` `[PROPOSED]`
2. THE Response_Controller SHALL simulate every action and SHALL make no change to any real system, account, or service. `[TEAM]`
3. WHEN a reviewer approves an action, THE Response_Controller SHALL record the reviewer identity, the action, the incident, and the approval timestamp (UTC, second precision) within 2 seconds, and set the status to "approved". `[BRIEF]` `[PROPOSED]`
4. WHILE an action is "pending approval" or "rejected", THE Response_Controller SHALL NOT simulate it. `[TEAM]`
5. IF a reviewer rejects an action, THEN THE Response_Controller SHALL record the reviewer, the action, the incident, and the timestamp, set the status to "rejected", and not simulate the action. `[TEAM]`
6. WHEN an approved action is simulated, THE Dashboard SHALL label it "simulated" wherever it is displayed and SHALL NOT display it as executed on a real system. `[TEAM]`
7. IF recording an approval fails, THEN THE Response_Controller SHALL keep the status "pending approval", not simulate the action, and show an error. `[TEAM]`
8. IF the reviewer is unauthorised, or the action is no longer pending, THEN THE Response_Controller SHALL refuse the request, leave the status unchanged, and show the reason. `[TEAM]`

### Requirement 15: Evidence history

**User Story:** As a security lead, I want a complete, traceable history, so that I can review how a conclusion was reached.

#### Acceptance Criteria

1. THE Evidence_Store SHALL record each event, rule result, approval lookup, severity change, AI explanation, and response action as an evidence item with a timestamp, and SHALL return items in ascending timestamp order. `[BRIEF]`
2. WHEN items have identical timestamps, THE Evidence_Store SHALL order them by the order in which they were recorded. `[TEAM]`
3. WHEN a reader selects an evidence item, THE Dashboard SHALL show its source event or record within 2 seconds. `[BRIEF]` `[PROPOSED]`
4. IF the source cannot be retrieved, THEN THE Dashboard SHALL show an error that the source is unavailable, keep the item displayed, and show the item ID. `[TEAM]`
5. THE Evidence_Store SHALL give each evidence item a unique ID, and corresponding items across replays of the same input SHALL have the same ID. `[TEAM]`
6. IF a request attempts to modify or delete evidence in a Replay_Run, THEN THE Evidence_Store SHALL reject it, leave the evidence unchanged, and return an error that evidence is immutable. `[TEAM]`
7. WHEN an analyst requests an export of an evidence trail, THE FinShield_System SHALL produce a file containing every item in timestamp order, each with its ID, type, timestamp, and source reference, within 30 seconds for up to 10,000 items. `[PROPOSED]`
8. IF the export fails, THEN THE FinShield_System SHALL show an error and leave the evidence unchanged. `[PROPOSED]`

### Requirement 16: Dashboard visibility

**User Story:** As a security analyst, I want one screen showing incidents and why they exist, so that I can triage quickly.

#### Acceptance Criteria

1. THE Dashboard SHALL list up to 100 incidents, most recently updated first, showing severity, scenario, actor, file count, distinct customer count, and last-updated time. `[BRIEF]` `[PROPOSED]`
2. WHEN an analyst opens an incident, THE Dashboard SHALL show each rule condition with the value seen, the limit, and the pass or fail result within 2 seconds. `[BRIEF]` `[PROPOSED]`
3. THE Dashboard SHALL show the file count and the distinct customer count as two separate labelled non-negative integers. `[BRIEF]`
4. THE Dashboard SHALL show the list of missing evidence for each incident, or state that none is missing. `[TEAM]`
5. WHEN a judge selects a scenario, changes one input or configuration value, and replays, THE Dashboard SHALL show the new result beside the previous result and highlight each differing field. `[BRIEF]`
6. IF a replay fails or does not complete within 60 seconds, THEN THE Dashboard SHALL show an error and keep the previous result and the changed input visible. `[TEAM]` `[PROPOSED]`
7. THE Dashboard SHALL show the Replay_Run ID of the displayed result on the same screen. `[TEAM]`
8. WHERE a live-event feed is available, THE Dashboard SHALL display a new incident within 5 seconds without a manual refresh. `[DECK]` `[PROPOSED]`

### Requirement 17: Result states

**User Story:** As a security analyst, I want to tell "nothing found" from "could not check", so that I do not trust a silent failure.

#### Acceptance Criteria

1. THE FinShield_System SHALL assign every check exactly one of four mutually exclusive states: successful empty result, missing evidence, invalid input, or unavailable AI service. `[TEAM]`
2. WHEN a check runs successfully and finds nothing, THE Dashboard SHALL show "checked, nothing found" with the check name and the completion timestamp. `[TEAM]`
3. WHEN evidence is missing, THE Dashboard SHALL show the missing-evidence state and list up to 20 missing source or field names, plus the count of any omitted names. `[TEAM]` `[PROPOSED]`
4. IF input is invalid, THEN THE Intake_Service SHALL reject it, store nothing, and return an error naming each invalid field and the rule violated. `[TEAM]`
5. IF the AI service gives no response within 10 seconds or returns an error, THEN THE Dashboard SHALL show that the explanation is unavailable and display the fallback summary. The 10-second limit is a proposed demo setting, shared with Requirement 13, criterion 6. `[TEAM]` `[PROPOSED]`
6. THE FinShield_System SHALL NOT classify, score, or flag improper behaviour solely because evidence is missing, and THE Dashboard SHALL show the missing-evidence state visibly distinct from "checked, nothing found". `[BRIEF]`
7. IF a check is in any state other than successful empty result, THEN THE Dashboard SHALL NOT show "checked, nothing found" for that check. `[TEAM]`

### Requirement 18: Compliance wording and data safety

**User Story:** As a security lead, I want careful compliance wording, so that the product does not overclaim.

#### Acceptance Criteria

1. THE FinShield_System SHALL describe compliance support as "DPDP-aligned readiness and controls" in every user-visible screen, report, and export that refers to compliance support. `[TEAM]`
2. THE FinShield_System SHALL label any unverified regulatory mapping or deadline "needs official verification" adjacent to it. `[TEAM]`
3. WHEN an alert's risk category maps to a compliance duty, THE Dashboard SHALL display a "Suggest compliance review" action within 2 seconds. `[TEAM]` `[PROPOSED]`
4. THE FinShield_System SHALL NOT state that a legal breach, violation, or non-compliance has occurred. `[TEAM]`
5. THE FinShield_System SHALL use non-conclusive wording such as "potential" or "may require review" for compliance-related text. `[TEAM]`
6. THE FinShield_System SHALL contain synthetic data only, with 0 records derived from real individuals, and SHALL reject non-synthetic records as defined in Requirement 1, criterion 5. `[BRIEF]`
7. THE AI_Investigator SHALL replace every customer identifier and name with a masked placeholder before sending content to Bedrock. `[BRIEF]`
8. IF masking fails or an unmasked identifier is detected, THEN THE AI_Investigator SHALL NOT send the request, SHALL show an error that the AI request was blocked because masking failed, and SHALL leave the original data unchanged. `[BRIEF]`

### Requirement 19: Contracts and change process

**User Story:** As a developer, I want versioned contracts, so that frontend, backend, and data teammates can work in parallel.

#### Acceptance Criteria

1. THE FinShield_System SHALL define every event and API payload in contracts.md, labelled with a MAJOR.MINOR version. `[TEAM]`
2. WHEN a Contract changes, THE team SHALL increment the version, add a decisions.md entry stating the change and the reason, and notify every affected role (data/replay, detection/backend, AI/controls, dashboard, platform) before merge. `[TEAM]`
3. IF the contract version is absent, malformed, or unsupported, THEN THE Intake_Service SHALL reject the event without processing or storing it and return an error listing every supported version. `[TEAM]`
4. WHEN an event uses a supported contract version, THE Intake_Service SHALL accept it for validation. `[TEAM]`
5. THE team SHALL cite at least one requirement ID (for example R6.4) in every task in tasks.md and every automated test. `[TEAM]`

### Requirement 20: Architecture and deployment paths

**User Story:** As a developer, I want one local path and one proposed AWS path with a shared format, so that we can demo reliably and still show a cloud design.

#### Acceptance Criteria

1. WHILE the host has no cloud connectivity, THE FinShield_System SHALL run every demo scenario locally from start to finish with zero outbound cloud requests. `[TEAM]`
2. THE architecture document SHALL describe one proposed AWS path naming API Gateway, Lambda, DynamoDB, and Bedrock, with each service's role and the local component it replaces. `[PROPOSED]`
3. WHERE a documented job requires S3 or EventBridge, THE architecture document SHALL include that service and list the job name and the reason. `[PROPOSED]`
4. THE FinShield_System SHALL build the Dashboard in React and the backend logic in Python. `[TEAM]`
5. THE FinShield_System SHALL define the event format once in a single shared definition used by both paths, with the same field names, types, and required fields. `[TEAM]`
6. IF an event does not conform to the shared definition, THEN THE Intake_Service SHALL reject it, preserve the rejected event unmodified for inspection, and return an error naming the failing field. `[TEAM]`
7. THE FinShield_System SHALL label every unmeasured performance, cost, or capacity figure "proposed, not measured" next to the figure everywhere it appears, until a recorded measurement with its date and method is attached. `[TEAM]`

### Requirement 21: Future detection backlog

**User Story:** As a team member, I want future detections recorded with promotion criteria, so that we can plan without building them now.

#### Acceptance Criteria

1. THE FinShield_System SHALL list "possible duplicate loan payout" as one backlog entry with a description of 1 to 3 sentences, the required data fields, and promotion criteria containing at least one measurable condition. `[TEAM]` `[PROPOSED]`
2. THE backlog entry for duplicate loan payout SHALL define a duplicate as 2 or more distinct successful transfer IDs linked to a single loan approval, and SHALL count multiple log entries sharing a transfer ID as one. `[TEAM]`
3. THE FinShield_System SHALL list "sensitive customer data sent to an unapproved destination" as one backlog entry with a description of 1 to 3 sentences, the required data fields, and promotion criteria containing at least one measurable condition. `[TEAM]` `[PROPOSED]`
4. THE backlog entry for sensitive data transfer SHALL define a reportable event as 1 or more sensitive reports sent to an unapproved destination, with no minimum above 1. `[TEAM]`
5. WHILE the FinShield_System is in the first release, THE FinShield_System SHALL check destinations only when validating a P1 approval and for no other purpose. `[TEAM]`
6. IF all promotion criteria of a backlog item are met and the decision is recorded in decisions.md, THEN THE team MAY promote the item. `[TEAM]`
7. IF the promotion criteria are not all met or the decision is not recorded, THEN THE team SHALL keep the item in the backlog and SHALL NOT start building it. `[TEAM]`

## Traceability

Acceptance test IDs below are defined in [demo-and-evaluation.md](../../../docs/finshield/demo-and-evaluation.md). Scenario data is in [scenarios.md](../../../docs/finshield/scenarios.md). Test IDs are proposed names until those files exist.

| Requirement | Scenario | Acceptance test |
|---|---|---|
| R6.3 First export stays below threshold | P1 | AT-P1-01 |
| R6.4 Second export opens one Critical incident | P1 | AT-P1-02 |
| R6.5 Third export updates incident to 300 | P1 | AT-P1-03 |
| R6.7 to R6.10, R7.9 Missing baseline or approvals source | P1 | AT-P1-04 |
| R6.11 Files and customers counted separately | P1 | AT-P1-05 |
| R7.3 Valid scoped approval, no Critical alert | P1 | AT-P1-06 |
| R7.4 to R7.7 Expired, unrelated, destination mismatch, partial scope | P1 | AT-P1-07 |
| R7.8 Approval lookup state shown | P1 | AT-P1-09 |
| R8.1 to R8.7 External upload variation | P1 | AT-P1-08 |
| R9.4, R9.6 High incident opens and updates | P2 | AT-P2-01 |
| R9.8, R9.9, R9.10 Assigned, delegated, expired delegation | P2 | AT-P2-02 |
| R9.11, R9.12 Missing assignment data vs empty result | P2 | AT-P2-03 |
| R9.13 120 distinct unassigned records, one High incident | P2 | AT-P2-04 |
| R10.1, R10.3 Five failures then new device | P3 | AT-P3-01 |
| R10.2, R10.4 Different accounts, familiar device | P3 | AT-P3-02 |
| R10.5 Verification request | P3 | AT-P3-03 |
| R10.6 Device history unavailable, non-incident item | P3 | AT-P3-04 |
| R4.4, R2.4, R5.4 Replay, duplicates, late events | P1 | AT-CORE-01 |
| R19.5 Tasks and tests cite requirement IDs | None | AT-CORE-02 |
| R13.4, R13.5, R13.6, R13.8, R13.9 AI check and fallback | P1 | AT-AI-01 |
| R14.3 Reviewer approval recorded | P1 | AT-RESP-01 |
| R12.1 to R12.5 Accuracy tests (not scenarios) | None | AT-ACC-01 |
