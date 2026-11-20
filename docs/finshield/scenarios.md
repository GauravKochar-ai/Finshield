# Scenarios: rules, numbers and expected results

This file is the primary home for scenario rules. Payload field names are in [contracts.md](contracts.md). Requirement IDs refer to [requirements.md](../../.kiro/specs/finshield-ai/requirements.md). Acceptance test IDs (AT-P1-01 and so on) match the traceability table there and are run as described in [demo-and-evaluation.md](demo-and-evaluation.md).

All data is synthetic. Every number marked **demo setting** is a configurable default chosen for the demo. It is not a measured or recommended production value. Any other figure not measured is "proposed, not measured".

The first release delivers exactly three priority scenarios: P1, P2, P3 (R1.1). Everything else in this file is either an accuracy test (R1.4, R12) or backlog (R21).

## Rules of interpretation

- **More than N** means N + 1 or higher. **At least N** means N or higher (R5.8).
- Boundary examples: with a limit of "more than 100", 100 does not trigger and 101 does. With "at least 5 times an upper end of 10", 49 does not qualify and 50 does.
- The P3 time gap is 0 to 600 seconds inclusive: 600 triggers, 601 does not.
- A rolling window of length W ending at time T covers events with time greater than T minus W and up to and including T. A five-minute window ending at 10:04 includes an event at 10:00 and excludes one at 09:59:59. The window ending at 10:05 excludes the 10:00 event.
- Windows use event time, never arrival time or the system clock (R5.3).
- The same event ID in the same run is counted once (R2.4, R5.5).
- A condition that cannot be checked because data is missing is `not_evaluated` and is never counted as a pass (R5.7). Missing evidence is not proof of wrongdoing (R17.6).
- Alerts may suggest a compliance review under the wording "DPDP-aligned readiness and controls". They never state that a legal breach or violation has happened (R18.4).

---

## P1: unusual bulk KYC export by a privileged account

### Business story

A privileged admin account normally exports 5 to 10 KYC documents in a five-minute period. At 10:00, 10:02 and 10:04 the same account exports 80, 90 and 130 documents. No approved ticket covers this work. The security analyst needs one Critical incident that grows as more exports arrive, with a clear reason and evidence, before the data can leave the lender.

### Data needed

| Data | Detail |
|---|---|
| Events | Export events with actor, operation, destination, device, time, and a list of document records (document ID plus customer ID each) |
| Business records | Account directory (privileged flag), baseline (personal, else role-level), approvals source (with record scope), device history |
| Normal activity | Admin generates 5 to 10 documents in every five-minute period of a baseline period of at least 7 days, at least 30 samples (demo setting, proposed, not measured) |

Illustrative IDs used below: run `run-7f3a9c21`, actor `acct-admin-07`, destination `dest-int-archive`, events `evt-001`, `evt-002`, `evt-003`, baseline `bl-001`.

### Exact rule

For each export event E by actor A, let S be the sum of documents exported by A in the rolling window ending at E (window default 5 minutes, demo setting). Raise **Critical** when all four hold (R6.1):

1. S is **more than 100** (document limit, demo setting).
2. S is **at least 5 times** the upper end of A's normal range (multiplier 5, demo setting). With upper end 10 this means at least 50.
3. A is a privileged account.
4. No valid approval covers the export.

Window length, document limit, multiplier and the privileged condition are configurable without code changes and apply to export events received after the change (R6.2).

### Severity

| Situation | Severity |
|---|---|
| All four conditions pass | Critical |
| Volume and privileged pass, approvals source unavailable (approval condition `not_evaluated`) | High, "approvals source" listed as missing evidence (R6.9) |
| Volume and privileged pass, no personal or role-level baseline (multiplier `not_evaluated`) | High, "baseline" listed as missing evidence (R6.8) |
| Approvals source later answers "no match" for a High incident opened above | Same incident raised to Critical, "approvals source" removed from missing evidence (R6.10) |
| A valid approval covers the export | No alert. Recorded as approved activity (R7.3) |
| Volume fails, or multiplier fails | No alert |

### Analyst-visible reason text

Critical: "Privileged account acct-admin-07 exported 170 documents in 5 minutes. Limit is more than 100, and normal for this account is 5 to 10 (50 or more needed). No approval covers this export."

High with missing approvals source: "Volume and privileged checks passed. Approval status is unknown because the approvals source was unavailable. This is missing evidence, not proof of wrongdoing."

### Worked sequence (the official demo)

| Event | Time | Documents | Window sum | Result |
|---|---|---|---|---|
| `evt-001` | 10:00 | 80 | 80 | 80 is not more than 100. No alert (AT-P1-01) |
| `evt-002` | 10:02 | 90 | 170 | 170 is more than 100 and at least 50. Opens ONE Critical incident `inc-p1-evt-002` (AT-P1-02) |
| `evt-003` | 10:04 | 130 | 300 | Same incident updated to 300 files, event 3 attached, no second incident (AT-P1-03) |

The demo data uses normal office hours, a known device (`dev-known-03`) and an internal destination, so volume alone is what proves Critical (R6.6). Time of day, device and destination are not conditions of the P1 rule. The illustrative counts at the second export are 170 files for 105 distinct customers. At the third they are 300 files for 180 distinct customers (illustrative).

Incident event count follows D-09: the event that triggers the incident counts as 1, so the incident has 1 event after `evt-002` and 2 after `evt-003`. Earlier window events are referenced by the rule result.

### Examples

| Kind | Example | Result |
|---|---|---|
| Suspicious | 80 then 90 then 130 documents, no approval | One Critical incident as above |
| Legitimate | Same 170 documents, approval `appr-001` for `acct-admin-07`, operation export, scope covers all records, valid 09:30 to 12:00, destination `dest-int-archive` | No Critical. Recorded as approved activity (AT-P1-06) |
| Tricky edge | Exactly 100 documents in the window | No alert (100 is not more than 100). 101 would pass the volume check |
| Tricky edge | Approval covers 100 documents but the export is 130 | Not fully covered. Incident stays open and shows 30 uncovered records (R7.7) |

### Evidence shown

Event IDs (`evt-001`, `evt-002`), rule result `rr-evt-002-p1` with each condition (value seen, limit, pass or fail), approval lookup `al-evt-002` ("returned no match"), baseline `bl-001`, total files and affected customers as two separate figures, missing evidence ("none" or a list), baseline scope ("personal" or "role-level").

### Next action

Analyst opens the evidence trail, clicks Investigate for an AI explanation, and the security lead approves or rejects the proposed simulated actions (suspend account, request verification). Alerts may suggest a compliance review. They do not state a legal finding.

### Approval matching

An approval covers an export only if **all five** match (R7.1):

| Check | Matches when |
|---|---|
| Actor | Approval actor equals export actor |
| Operation | Approval operation equals export operation |
| Records | Every exported record is inside the approved record scope |
| Time window | Export time is at or after the approval start and before the approval expiry |
| Destination | Export destination equals approved destination |

Cases that do **not** clear the incident (AT-P1-07):

| Case | What the analyst sees |
|---|---|
| Expired approval (export at or after expiry) | Expiry time and export time (R7.4) |
| Unrelated ticket, or actor, operation or record scope differs | Which of ticket, actor, operation or record scope did not match (R7.5) |
| Destination mismatch | Approved destination and export destination (R7.6) |
| Approval covers fewer than all records | Count of uncovered records (R7.7) |

Short example: an approval for 100 documents to the audit share does not cover 130 documents. It also does not cover an export to a different share.

### Record scope in the fake data

Record scope is exactly one scope type plus values (R7.2). The three allowed types:

```json
{ "scope_type": "customer_ids", "customer_ids": ["cust-00017", "cust-00018"] }
```

```json
{ "scope_type": "document_type_segment", "document_type": "address_proof", "customer_segment": "segment-small-business" }
```

```json
{ "scope_type": "registry_batch", "registry_batch_id": "batch-2026-03-12-daily" }
```

A customer ID list holds 1 to 1,000 IDs (proposed, not measured). Field names are fixed in [contracts.md](contracts.md#export-approval).

### Missing evidence handling

| Situation | Behaviour |
|---|---|
| Personal history unavailable or fewer than 30 samples | Use the role-level baseline of comparable privileged accounts. Label the incident "baseline: role-level" (R6.7) |
| Neither baseline available | Multiplier condition is `not_evaluated`, incident opens as High, "baseline" is listed as missing (R6.8) |
| Approvals lookup unavailable | Export is "not confirmed covered". High, "approvals source" missing (R6.9, R7.9). The dashboard says "unavailable" (AT-P1-04, AT-P1-09) |
| Approvals lookup succeeded, nothing found | "Returned no match". This is a successful empty result, and the Critical rule can fire |

### External upload variation

Definitions (R8.2):

- **Observed export**: an event shows documents were exported from the system.
- **Attempted upload**: an event shows an upload request was made to a destination, with no proof it completed.
- **Confirmed transfer**: an event or receipt shows the destination received the data.

An upload to an external destination attaches to the existing open P1 incident for the same actor if the incident has at least one export and the upload is later than the earliest export. It is attached as extra evidence, no new incident opens, and severity stays Critical (R8.1, R8.6). Each transfer fact carries exactly one label.

Example: `evt-004` at 10:05, "upload requested to dest-ext-host-7", is an **attempted upload**. It does not prove the data arrived. Only a receipt event such as "dest-ext-host-7 reports data received" allows "confirmed transfer". If no such event exists, the dashboard never shows "confirmed transfer" (R8.5). If the upload cannot be attached (for example a closed fixture incident, D-12), the evidence stays unchanged and the analyst sees an error (R8.7). Test: AT-P1-08.

### Total files versus distinct customers

Both are calculated from the document records and shown as two separate figures (R6.11, AT-P1-05). One customer can have several files.

Illustrative example: an export lists 5 document records: `doc-0001` and `doc-0002` for `cust-00017`, `doc-0003` and `doc-0004` for `cust-00018`, `doc-0005` for `cust-00019`. Total files is 5. Affected customers is 3. The dashboard shows "5 files, 3 customers".

### Configurable demo assumptions

| Value | Default | Label |
|---|---|---|
| Window length | 5 minutes | demo setting |
| Document limit (more than) | 100 | demo setting |
| Multiplier on normal upper end (at least) | 5 | demo setting |
| Admin normal range | 5 to 10 documents per 5 minutes | demo setting |
| Minimum baseline samples | 30 | demo setting, proposed, not measured |
| Approvals lookup limit | 5 seconds | demo setting, proposed, not measured |
| Grouping gap for incidents | 15 minutes | demo setting, proposed, not measured |

### Acceptance tests

| Test | Pass when |
|---|---|
| AT-P1-01 | Replay of the three events gives no alert and no incident at `evt-001` (80 documents) |
| AT-P1-02 | At `evt-002` exactly one incident exists, severity Critical, window sum 170 |
| AT-P1-03 | After `evt-003` the same incident ID shows 300 files, event 3 attached, incident count still 1 |
| AT-P1-04 | Approvals source unavailable gives High with "approvals source" missing. No personal or role baseline gives High with "baseline" missing. Later "no match" raises the same incident to Critical |
| AT-P1-05 | Dashboard shows files and customers as two separate numbers (300 and 180 in the illustrative data) |
| AT-P1-06 | A valid scoped approval gives approved activity and no Critical alert |
| AT-P1-07 | Expired approval, unrelated ticket, destination mismatch and partial scope each keep the incident open and name what differed |
| AT-P1-08 | An external upload attaches to the open incident, is labelled correctly, creates no new incident, and severity stays Critical |
| AT-P1-09 | Dashboard states exactly one of "returned a match", "returned no match", "unavailable" for the approvals lookup |

---

## P2: collection agent or loan officer opens customers not assigned to them

### Business story

A collection partner agent normally works only on customers assigned to them. In one half hour the agent opens many customer records outside that list. The analyst needs one High incident that opens as soon as the pattern is clear and keeps growing as the agent opens more records.

### Data needed

| Data | Detail |
|---|---|
| Events | Record access events with actor, role (collection agent or loan officer), customer ID, outcome (success or failure), time |
| Business records | Assignments (actor to customer, with validity period), delegations (approved, with start and expiry) |

### Exact rule

Classify each access at its event time as exactly one of: **assigned**, **delegated**, **unassigned**, **unverified** (R9.1). Count only **successful** accesses classified unassigned (R9.2). The count is the number of **distinct customer IDs** in that class for one actor in a rolling window (R9.3, R9.7). When the count **reaches** the threshold, open one High incident at the access that reaches it (R9.4). Later unassigned accesses by the same actor update the same incident with the new distinct count and attach the event (R9.6).

### Severity

High.

### Analyst-visible reason text

"acct-collect-12 opened 5 distinct customers not assigned to them within 30 minutes. Threshold is 5 (demo setting)."

### Classification rules

| Assignment lookup | Delegation | Class | Counted |
|---|---|---|---|
| Found, covers the customer | n/a | assigned | No |
| Found nothing for the customer | None valid at access time | unassigned | Yes |
| Found nothing | Approved and unexpired at access time | delegated | No |
| Found nothing | Expired before the access | unassigned | Yes |
| Unavailable (error or no answer within 5 seconds) | n/a | unverified: assignment data missing | No. Source listed as missing evidence |

An assignment feed that returns "no record for customer cust-00017" is a successful empty result, so the access counts. A feed that times out is missing evidence, so the access does not count and the dashboard says why. Missing evidence is not guilt (R17.6).

### Worked example

Actor `acct-collect-12`. Accesses (illustrative IDs): `evt-101` to `evt-105`, five different customers, none assigned, all successful, all within 30 minutes. The fifth access `evt-105` reaches the threshold and opens `inc-p2-evt-105` as High with distinct count 5. A sixth access to a new customer updates the same incident to 6. A second access to a customer already counted leaves the count at 6.

Deck dataset (R9.13, AT-P2-04): one collection partner opens 120 distinct unassigned customer records. The generator places all 120 accesses inside one 30-minute window, for example one every 10 seconds (20 minutes). The incident opens at the fifth access. After all records are processed there is exactly one High incident with distinct unassigned count 120. This dataset is `[DECK]` and is not a release gate.

### Examples

| Kind | Example | Result |
|---|---|---|
| Suspicious | 5 distinct unassigned customers in 30 minutes | One High incident |
| Legitimate | 5 customers all on the agent's assignment list | Recorded as normal, nothing counted (AT-P2-02) |
| Tricky edge | The agent opens one unassigned customer 5 times | Distinct count is 1. No incident |
| Tricky edge | A delegation expired at 14:00 and the access is at 14:00 | Unassigned and counted (expiry means not valid at or after that time, same convention as approvals) |

### Evidence shown

Event IDs of the counted accesses, the classification of each (assigned, delegated, unassigned, unverified), the distinct count against the threshold, the assignment lookup state, and missing evidence.

### Next action

Analyst checks with the agent's manager whether work was reassigned. A reviewer may request verification.

### Variations

| Variation | Result |
|---|---|
| Customer is assigned | Normal, not counted |
| Active delegation | Delegated, not counted |
| Expired delegation | Unassigned, counted (AT-P2-02) |
| Assignment feed unavailable | Unverified, not counted, source named as missing evidence (AT-P2-03) |
| Feed answers "no record" | Unassigned, counted (AT-P2-03) |
| Failed access (permission denied) | Not counted |

### Configurable demo assumptions

| Value | Default | Allowed range | Label |
|---|---|---|---|
| Distinct unassigned threshold | 5 | integer 1 to 1,000 | demo setting |
| Rolling window | 30 minutes | 1 to 1,440 minutes | demo setting |
| Assignment lookup limit | 5 seconds | n/a | demo setting, proposed, not measured |

### Acceptance tests

| Test | Pass when |
|---|---|
| AT-P2-01 | One High incident opens at the fifth distinct unassigned access, later accesses update the same incident |
| AT-P2-02 | Assigned and unexpired-delegation accesses are not counted. Expired delegation access is counted |
| AT-P2-03 | Unavailable feed gives "unverified: assignment data missing" and no count. Empty answer gives unassigned and a count |
| AT-P2-04 | The 120-customer dataset ends with one High incident and distinct count 120 |

---

## P3: possible privileged account takeover

### Business story

Someone fails to log in to an admin account several times, then succeeds from a device that account has never used. This pattern may mean the password was guessed. The analyst needs one High incident that shows the sequence and the device history, and a way to ask the account owner to verify.

### Data needed

| Data | Detail |
|---|---|
| Events | Login events with account, outcome (failure or success), device, time |
| Business records | Device history per account (built from normal login events only), privileged flag |

### Exact rule

Open exactly **one High** incident labelled "possible account takeover" when all hold (R10.1, D-03):

1. A successful login occurs on a privileged account.
2. The device is **not** in that account's device history.
3. The same account has **5 or more** distinct failed login events counted since its last successful login (failed-login count 5 is a demo setting).
4. The success occurs **0 to 600 seconds inclusive** after the latest of those failures (window 600 seconds is a demo setting).

Failures are counted per account only. Failures on different accounts are never combined (R10.2).

### Severity

High.

### Analyst-visible reason text

"5 failed logins on acct-admin-07, then a successful login 4 minutes later from device dev-new-91, which this account has not used before. Possible account takeover."

### Worked example

Account `acct-admin-07`, device history `dev-known-03`, `dev-known-04`. `evt-201` to `evt-205` are failed logins from `dev-new-91` between 03:10:00 and 03:12:00. `evt-206` is a success from `dev-new-91` at 03:16:00, which is 240 seconds after the fifth failure. One High incident `inc-p3-evt-206` opens. It shows the login sequence in time order (time, outcome, device), the full device history, and event IDs `evt-201` to `evt-206` (AT-P3-01). A reviewer requests owner verification and one verification request is recorded with reviewer identity, account owner as recipient and timestamp (AT-P3-03).

### Examples

| Kind | Example | Result |
|---|---|---|
| Suspicious | 5 failures then success from `dev-new-91` after 240 seconds | One High incident |
| Legitimate | 5 failed attempts from a laptop, then success from the same laptop already in device history | No incident (R10.4, AT-P3-02) |
| Tricky edge | 600 seconds after the fifth failure | Triggers |
| Tricky edge | 601 seconds after the fifth failure | Does not trigger |
| Tricky edge | 4 failures, or 5 failures across 3 different accounts | Does not trigger |

Ordinary password mistakes on a familiar device never create an incident.

### Missing evidence

If device history is unavailable, no "possible account takeover" incident opens. The check is recorded "not evaluated: missing evidence", names "device history", and the dashboard shows it as a visible non-incident item (R10.6, AT-P3-04).

### Evidence shown

Login sequence in chronological order, full device history, event IDs of every failed and successful login used.

### Next action

A reviewer can request account-owner verification. This is a simulated action (R10.5).

### Configurable demo assumptions

| Value | Default | Allowed range | Label |
|---|---|---|---|
| Failed-login count | 5 | 1 to 100 | demo setting |
| Window | 600 seconds | 60 to 86,400 seconds | demo setting |
| Device-history rule | Device not in history | n/a | demo setting |

### Acceptance tests

| Test | Pass when |
|---|---|
| AT-P3-01 | Five failures then a new-device success within 600 seconds opens one High incident with sequence, device history and event IDs |
| AT-P3-02 | Failures on different accounts, or a success from a known device, open nothing |
| AT-P3-03 | A reviewer verification request records identity, recipient and timestamp |
| AT-P3-04 | Unavailable device history opens no incident and shows a non-incident missing-evidence item |

---

## Classification of cases

| Class | Cases | Counts as | Test |
|---|---|---|---|
| Priority detections | P1, P2, P3 | The three scenarios (R1.1) | AT-P1-xx, AT-P2-xx, AT-P3-xx |
| Normal comparison cases | Scheduled daily KYC registry upload by an approved system account. Auditor export with a valid ticket | Accuracy tests, not scenarios (R1.4, R12.6) | AT-ACC-01 |
| Edge cases | Credit team member downloads 15 files late at night. Expired or non-covering auditor ticket | Accuracy tests (R12) | AT-ACC-01 |
| Future standalone detections | Possible duplicate loan payout. Sensitive customer data to an unapproved destination | Backlog, outside the critical path (R1.6, R21) | None in first release |

### Normal case: scheduled daily KYC registry upload

Approved system account `svc-kyc-registry` uploads the daily registry batch `batch-2026-03-12-daily` to approved destination `dest-int-registry`. An approval with scope type `registry_batch` covers actor, operation, batch, time and destination. Expected: approved activity, zero alerts, shown on the dashboard within 5 seconds (R12.1, proposed, not measured).

### Normal case: auditor export with a valid ticket

Auditor `acct-auditor-02` exports records under ticket `tkt-audit-114`, valid at export time, covering the records, the time and the destination. Expected: approved activity, zero alerts. If the ticket has expired, or its scope does not cover the records, time or destination, the export is not approved activity. It goes through the standard rules (for example P1 if volume is high) and the dashboard shows which check failed (R12.3).

### Edge case: credit team member downloads 15 files late at night

"Late at night" is 22:00 to 05:59 local time (demo setting).

| Item | Value |
|---|---|
| Actor | `acct-credit-31`, credit team, not privileged |
| Event | 15 files downloaded at 23:40 |
| Person's normal daily download volume | 10 to 20 files per day (illustrative, demo setting) |
| Rule applied | The first release has no Medium rule. P1 needs a privileged account, more than 100 documents in 5 minutes, and no covering approval. P2 and P3 do not apply to downloads |

**Derived result (derived from the documented rules, not a separate alert rule): no alert.** The dashboard shows the person's normal volume (10 to 20 per day), the 15 files observed, and the rule applied, with a reason of up to 200 characters (R12.4, R12.5, R12.7):

"No alert. 15 files is within this person's normal 10 to 20 per day. No first-release rule covers late-night downloads by non-privileged accounts, and P1 needs more than 100 documents in 5 minutes."

A Medium alert is never shown on weak evidence. If the team later wants a late-night Medium rule, it needs a decision in [decisions.md](decisions.md) and a scenario entry here first.

---

## Future backlog (not on the critical path)

These are not built in the first release. P1, P2, P3 and the demo run with them absent (R1.6, R21). Promotion needs all criteria met and a decision recorded in [decisions.md](decisions.md) (R21.6). The promotion numbers below are proposed, not measured.

### Possible duplicate loan payout

- **Description:** Detect a loan paid out more than once. A duplicate is 2 or more **distinct successful transfer IDs** linked to a single loan approval. Two log entries with the same transfer ID count as one transfer (R21.2).
- **Required data:** loan approval ID, transfer ID, transfer outcome (success or failure), amount, time.
- **Promotion criteria (proposed, not measured):** P1, P2, P3 acceptance tests pass in 3 consecutive replays. Synthetic data with loan approvals and transfer logs exists. Expected-result file covers at least one true duplicate and one repeated log entry. Decision logged.
- **Example:** loan approval `loan-0042` with transfers `trf-901` and `trf-902`, both successful: duplicate. Loan `loan-0043` with two log lines for `trf-910`: one transfer, no alert.

### Sensitive customer data sent to an unapproved destination

- **Description:** Detect when a sensitive report is sent to a destination not on the approved list. A reportable event is **1 or more** sensitive reports to an unapproved destination, with no minimum above 1 (R21.4).
- **Required data:** report ID, sensitivity label, destination, approved-destination list, time, sender.
- **First-release limit:** destinations are checked only when validating a P1 approval and for no other purpose (R21.5).
- **Promotion criteria (proposed, not measured):** P1, P2, P3 acceptance tests pass in 3 consecutive replays. Synthetic sensitivity labels and an approved-destination list exist. Expected-result file covers one report to an approved destination (no alert) and one to an unapproved destination (alert). Decision logged.
