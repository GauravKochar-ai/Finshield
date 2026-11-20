# FinShield AI: contracts

**Contract version: 1.0** (MAJOR.MINOR)

This file is the primary home for every event and API payload. Other documents link here and do not copy field definitions. Requirement: [R19](../../.kiro/specs/finshield-ai/requirements.md). Design context: [design.md](../../.kiro/specs/finshield-ai/design.md). Scenario rules and numbers: [scenarios.md](scenarios.md). Decisions: [decisions.md](decisions.md).

All data is synthetic. All counts, customer numbers and timings in the examples are illustrative. Numbers not measured are marked "demo setting" or "proposed, not measured".

## Contents

1. [Conventions](#conventions)
2. [Change process](#change-process)
3. [Field tables](#field-tables)
4. [API operations](#api-operations)
5. [Worked example: one P1 KYC incident](#worked-example-one-p1-kyc-incident)
6. [Result states](#result-states)
7. [Gaps filled here](#gaps-filled-here)

## Conventions

| Topic | Rule |
|---|---|
| Version field | Every event carries `contract_version`, for example `"1.0"`. Format is `MAJOR.MINOR`. |
| Timestamps | UTC, ISO 8601, ending in `Z`. Event times use second precision, for example `2026-03-12T10:02:00Z`. System-stamped times (incident update, AI request) use milliseconds, for example `2026-03-12T10:02:00.412Z`. Approval and reviewer-action times use second precision. |
| Event IDs | Stable and chosen by the data author, for example `evt-001`. An event ID is unique inside a run. The same ID in two runs is allowed. |
| Run ID | `run-` plus 8 lowercase hex characters, for example `run-7f3a9c21`. Created by the system, never by the caller. |
| Other IDs | Lower case, hyphen separated. Incident `inc-p1-evt-002`. Rule result `rr-evt-002-p1`. Approval lookup `al-evt-002`. Baseline `bl-001`. Action `act-inc-p1-evt-002-1`. Evidence IDs never contain a run ID, actor name or customer ID. |
| Synthetic IDs | Actors `acct-...`, `svc-...`. Customers `cust-00017`. Documents `doc-0001`. Devices `dev-known-03`. Destinations `dest-int-archive`. Approvals `appr-001` or ticket `tkt-audit-114`. None refer to a real person or system. |
| Synthetic marker | Every event and reference record carries `synthetic: true`. Anything else is rejected (R1.5). |
| Provenance | Events carry `provenance`: `normal` or `injected`. Only the baseline builder reads it. Detection ignores it. |
| Counts | `total_files` and `distinct_customers` are always separate fields. Neither is derived from the other. |
| Unknown fields | Intake ignores unknown optional fields in the same MAJOR version and keeps them unmodified. Unknown required values (for example an unknown `operation`) are rejected. |
| JSON | UTF-8, field names in `snake_case`. |
| Dates in examples | The demo date `2026-03-12` is used throughout. Times are shown in UTC. |

## Change process

Any change to a payload goes through these steps. They apply to this file only. Role notes may propose a change but never hold the agreed version.

1. **Propose** the change in a role note (see [README.md](README.md#how-to-add-your-own-notes)). State the field, the reason and the roles affected.
2. **Log it** as a contract change entry in [decisions.md](decisions.md#template-contract-change), with the old and new version.
3. **Bump the version** in this file:
   - MINOR (1.0 to 1.1): additive and optional only, for example a new optional field. Existing senders and readers keep working.
   - MAJOR (1.x to 2.0): any removal, rename, change of meaning, change of type, or a field becoming required.
4. **Notify** every affected role: 01 Data and replay, 02 Detection and backend, 03 AI and controls, 04 Dashboard and workflow, 05 Platform and integration. A role is affected if it reads or writes the changed field.
5. **Merge** only after the affected roles have acknowledged.

Intake rejects any event whose `contract_version` is missing, malformed or unsupported. The error lists every supported version (R19.3). Supported versions for this release: `1.0`.

Version history:

| Version | Date | Change |
|---|---|---|
| 1.0 | Draft for sign-off at task T1.2 | First version. |

## Field tables

Type words: `string`, `integer`, `boolean`, `timestamp` (UTC ISO 8601 with `Z`), `object`, `list`. "Required" means required in version 1.0 unless noted. A trailing `?` means optional.

### Event

One activity record sent to intake. Intake: [R2](../../.kiro/specs/finshield-ai/requirements.md).

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `contract_version` | string | yes | Contract version, `"1.0"`. |
| `event_id` | string | yes | Stable event ID, unique inside the run. |
| `event_time` | timestamp | yes | When the activity happened. Windows use this, never arrival time. |
| `actor_id` | string | yes | Synthetic account that did the activity. |
| `operation` | string | yes | One of `export`, `upload`, `record_access`, `login`. |
| `outcome` | string | yes | `success` or `failure`. Exports and logins use both. |
| `destination_id` | string | no | Where data went, for `export` and `upload`, for example `dest-int-archive`. |
| `device_id` | string | no | Device used, for `login` and exports. |
| `customer_id` | string | no | Single customer touched, for `record_access`. |
| `documents` | list of document record | no | For `export` and `upload`. Each record has `document_id` (required) and `customer_id` (required). |
| `document_count` | integer | with `documents` | Reported number of documents. Must equal the number of listed `document_id` values, otherwise intake rejects and returns both numbers (R2.8). |
| `receipt` | object | no | For `upload` only: `{ "destination_received": true }` when the destination reports receipt. Needed for "confirmed transfer". |
| `provenance` | string | yes | `normal` or `injected`. |
| `synthetic` | boolean | yes | Must be `true`. |

Intake result (returned by the intake step, not a separate API operation in the minimum set): `status` is `accepted` or `duplicate`. A duplicate is not stored again and is not counted.

### Role and device history

Reference data copied into each run. Directory entry and device history.

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `actor_id` | string | yes | Account the record is about. |
| `role` | string | yes | For example `privileged_admin`, `collection_agent`, `credit_team`, `auditor`, `system_account`. |
| `privileged` | boolean | yes | `true` for a privileged account (P1 and P3 condition). |
| `known_devices` | list of string | yes | Device IDs in the account's history, for example `["dev-known-03", "dev-known-04"]`. Empty list means the lookup worked and found nothing. |
| `history_source_state` | string | no | `available` (default) or `unavailable`. `unavailable` is how the local path demos missing device history. |
| `synthetic` | boolean | yes | Must be `true`. |

### Assignment or delegation

Used by P2 ([R9](../../.kiro/specs/finshield-ai/requirements.md)).

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `record_kind` | string | yes | `assignment` or `delegation`. |
| `record_id` | string | yes | For example `asg-0001`, `dlg-0001`. |
| `actor_id` | string | yes | Agent or officer who is assigned or delegated to. |
| `customer_id` | string | yes | Customer covered. |
| `valid_from` | timestamp | yes | Start, inclusive. |
| `valid_to` | timestamp | no | Expiry. Not valid at or after this time. Absent means no expiry (assignments only). Required for a delegation. |
| `approved` | boolean | delegation only | A delegation counts only when `true`. |
| `synthetic` | boolean | yes | Must be `true`. |

Lookup outcome in the rule result: `found`, `empty` or `unavailable` (see [Result states](#result-states)).

### Export approval

Used by P1 approval matching ([R7](../../.kiro/specs/finshield-ai/requirements.md), [scenarios.md](scenarios.md)). An approval covers an export only if actor, operation, record scope, time and destination all match.

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `approval_id` | string | yes | For example `appr-001`. |
| `ticket_id` | string | no | Ticket reference, for example `tkt-audit-114`. |
| `actor_id` | string | yes | Who may do the work. |
| `operation` | string | yes | `export` or `upload`. |
| `record_scope` | object | yes | Exactly one scope, see below. |
| `valid_from` | timestamp | yes | Export at or after this time. |
| `valid_to` | timestamp | yes | Export before this time. Expiry time itself is not covered. |
| `destination_id` | string | yes | Approved destination. |
| `synthetic` | boolean | yes | Must be `true`. |

Record scope, exactly one `scope_type`:

| `scope_type` | Other fields | Meaning |
|---|---|---|
| `customer_ids` | `customer_ids`: list of string, 1 to 1,000 entries (proposed, not measured) | Covers documents of the listed customers. |
| `document_type_segment` | `document_type` string, `customer_segment` string | Covers one document type for one customer segment, for example `address_proof` and `segment-small-business`. |
| `registry_batch` | `registry_batch_id` string | Covers one named registry batch, for example `batch-2026-03-12-daily`. |

A scope with no type, two types, or fields from the wrong type is invalid input.

### Incident

Returned by the incident operations. Fields marked "derived" are computed by the system.

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `incident_id` | string | yes | Derived from content, for example `inc-p1-evt-002`. |
| `run_id` | string | yes | Run the incident belongs to. |
| `scenario` | string | yes | `P1`, `P2` or `P3`. |
| `actor_id` | string | yes | Account the incident is about. |
| `severity` | string | yes | `Critical`, `High` or `Medium`. First release raises no Medium alerts. |
| `severity_history` | list | yes | Each entry: `old_severity` (null for the first), `new_severity`, `rule_id`, `changed_at` (timestamp, ms), `trigger_event_id`. Only grows. |
| `event_count` | integer | yes | Events attached. The triggering event counts as 1 (D-09). |
| `event_ids` | list of string | yes | Attached event IDs. |
| `total_files` | integer | P1 | Sum of exported documents in the window. |
| `distinct_customers` | integer | P1, P2 | Count of distinct customer IDs. Separate from `total_files`. |
| `counts_note` | string | no | Free text, for example "customer counts are illustrative". |
| `conditions` | list of condition result | yes | `name`, `value_seen`, `limit`, `state` (`pass`, `fail`, `not_evaluated`), `missing_source` (when `not_evaluated`). |
| `approvals_lookup` | string | P1 | `found`, `empty` or `unavailable`. Dashboard text: "returned a match", "returned no match", "unavailable". |
| `baseline_scope` | string | P1 | `personal`, `role-level` or `missing`. |
| `missing_evidence` | list of string | yes | Source names. Empty list means none missing. The dashboard shows up to 20 and a count of the rest (R17.3). |
| `evidence_ids` | list of string | yes | IDs of evidence items in order. |
| `proposed_actions` | list of reviewer action | yes | 1 to 10 simulated actions. |
| `explanation` | AI explanation | no | Latest explanation, if requested. |
| `created_at` | timestamp | yes | Millisecond precision. |
| `updated_at` | timestamp | yes | Millisecond precision. |
| `update_event_ids` | list of string | yes | Events that caused the latest update. |
| `synthetic` | boolean | yes | Must be `true`. |

### Evidence item

Append-only. There is no update or delete operation (R15.6).

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `evidence_id` | string | yes | For example `evt-002`, `rr-evt-002-p1`, `al-evt-002`, `bl-001`. |
| `run_id` | string | yes | Owning run. |
| `type` | string | yes | `event`, `rule_result`, `approval_lookup`, `severity_change`, `ai_explanation`, `response_action`, `approved_activity`, `baseline`. |
| `timestamp` | timestamp | yes | When the item was recorded or when the source event happened. |
| `sequence` | integer | yes | Per-run order number. Ties on timestamp are ordered by sequence. |
| `source_ref` | string | yes | Where the item came from, for example `event:evt-002`. |
| `summary` | string | yes | One-line masked description, safe to send to the AI. |
| `source_available` | boolean | no | `false` when the original source cannot be retrieved. The item stays visible (R15.4). |

### AI explanation

Created only after a person asks. The AI never changes severity or alert state (R13.10).

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `explanation_id` | string | yes | Evidence ID, for example `ai-inc-p1-evt-002-1`. |
| `incident_id` | string | yes | Incident explained. |
| `requested_at` | timestamp | yes | Millisecond precision. |
| `source` | string | yes | `live` (Bedrock answered and passed checks) or `fallback` (fixed template). |
| `fallback_reason` | string | when `source` is `fallback` | `local_path_default`, `model_timeout`, `model_error` or `answer_rejected`. |
| `label` | string | yes | Text the dashboard must show, for example "Fallback summary - live model unavailable". |
| `what_happened` | string | yes | Part 1. Cites evidence IDs. |
| `supporting_evidence` | list of object | yes | Part 2. Each: `evidence_id`, `shows` (one sentence). |
| `what_remains_unknown` | string | yes | Part 3. "None identified" only when `missing_evidence` is empty. |
| `next_check` | string | yes | Part 4. One action, at most 300 characters (proposed). |
| `citation_check` | object | yes | `result` (`accepted` or `rejected`), `failed_checks` (list from: `shape`, `evidence_ids`, `customer_counts`, `legal_findings`, `approval_status`, `unmasked_identifiers`), `rejection_reason?`. For `fallback` summaries the check also runs and must show `accepted`. |

### Reviewer action

Only two action types exist, both simulated (D-14).

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `action_id` | string | yes | For example `act-inc-p1-evt-002-1`. |
| `incident_id` | string | yes | Incident the action belongs to. |
| `action_type` | string | yes | `suspend_account` (simulated) or `request_verification`. No other value is accepted. |
| `status` | string | yes | `pending_approval`, `approved` or `rejected`. After an approved action is simulated, `simulated` is set to `true`. |
| `simulated` | boolean | yes | `true` once the simulation is recorded. The dashboard says "simulated", never "executed". |
| `proposed_at` | timestamp | yes | Second precision. |
| `reviewer_id` | string | when decided | Demo user who decided, for example `user-security-lead`. Demo sign-in, not authentication (D-07). |
| `decided_at` | timestamp | when decided | Second precision, UTC. |
| `decision_note` | string | no | Free text, up to 200 characters. |
| `recipient_id` | string | `request_verification` | Account owner who is asked to verify, for example `owner-of-acct-admin-07`. |

Decision request body for `POST` reviewer action: `action_id`, `decision` (`approve` or `reject`), `reviewer_id`, `decision_note?`.

### Error and field error

Used by every operation.

| Field | Type | Required? | Meaning |
|---|---|---|---|
| `error.code` | string | yes | `invalid_input`, `unsupported_contract_version`, `not_found`, `not_authorised`, `conflict`, `masking_failed`, `ai_unavailable`, `internal`. |
| `error.message` | string | yes | Plain English. No stack traces. |
| `error.field_errors` | list | for `invalid_input` | Each: `field`, `rule`, `value_seen?`. Up to 50 entries (R2.3). |
| `error.supported_versions` | list of string | for version errors | Every supported contract version. |

## API operations

Minimum set for version 1.0. Paths start with `/v1`. Both the local server and API Gateway expose the same paths and bodies (R20.5). Every response carries `contract_version`.

| # | Operation | Method and path | Success | Used by |
|---|---|---|---|---|
| 1 | Start replay | `POST /v1/replays` | 201 | Dashboard replay controls, demo script |
| 2 | List incidents | `GET /v1/runs/{run_id}/incidents` | 200 | Incident list |
| 3 | Get incident with evidence | `GET /v1/runs/{run_id}/incidents/{incident_id}` | 200 | Incident detail |
| 4 | Request AI explanation | `POST /v1/runs/{run_id}/incidents/{incident_id}/explanations` | 200 | Investigate button |
| 5 | Reviewer action | `POST /v1/runs/{run_id}/actions/{action_id}/decision` | 200 | Approve or reject |

Query parameters for operation 2: `severity` (optional filter, `Critical`, `High` or `Medium`), `limit` (default 100, maximum 100, as in R16.1). Results are sorted by `updated_at`, newest first.

Event intake is called inside the replay. Direct intake (`POST /v1/runs/{run_id}/events`) is allowed for tests and uses the Event table above. It returns `status` `accepted` or `duplicate`.

## Worked example: one P1 KYC incident

All IDs below are the same in every call. Run `run-7f3a9c21`, actor `acct-admin-07`, events `evt-001` (80 files, 10:00), `evt-002` (90 files, 10:02), `evt-003` (130 files, 10:04), incident `inc-p1-evt-002`. The incident opens at 170 files (Critical) on `evt-002` and updates to 300 on `evt-003`. Customer counts of 105 and 180 are illustrative.

### Sample event (`evt-002`)

The real event lists all 90 document records. Only three are shown here to keep the page readable. `document_count` is 90.

```json
{
  "contract_version": "1.0",
  "event_id": "evt-002",
  "event_time": "2026-03-12T10:02:00Z",
  "actor_id": "acct-admin-07",
  "operation": "export",
  "outcome": "success",
  "destination_id": "dest-int-archive",
  "device_id": "dev-known-03",
  "document_count": 90,
  "documents": [
    { "document_id": "doc-0081", "customer_id": "cust-00041" },
    { "document_id": "doc-0082", "customer_id": "cust-00041" },
    { "document_id": "doc-0083", "customer_id": "cust-00042" }
  ],
  "provenance": "injected",
  "synthetic": true
}
```

### 1. Start replay

Request:

```http
POST /v1/replays
Content-Type: application/json
```

```json
{
  "contract_version": "1.0",
  "scenario": "P1",
  "event_file": "p1-bulk-kyc-export.json",
  "config_overrides": {}
}
```

Response, `201 Created`:

```json
{
  "contract_version": "1.0",
  "run_id": "run-7f3a9c21",
  "scenario": "P1",
  "status": "completed",
  "created_at": "2026-03-12T10:30:00.120Z",
  "events": { "accepted": 3, "duplicate": 0, "rejected": 0 },
  "incident_ids": ["inc-p1-evt-002"],
  "config": {
    "p1_volume_limit": 100,
    "p1_window_minutes": 5,
    "p1_multiplier": 5,
    "grouping_window_minutes": 15
  },
  "config_note": "demo settings, proposed, not measured"
}
```

To change one value and replay, send the same request with `"config_overrides": { "p1_volume_limit": 170 }`. The response has a new `run_id` (for example `run-b2c4d8e0`) and the first run is untouched. An invalid override returns 422 (see [Result states](#result-states)).

### 2. List incidents

```http
GET /v1/runs/run-7f3a9c21/incidents
```

Response, `200 OK`, after all three events:

```json
{
  "contract_version": "1.0",
  "run_id": "run-7f3a9c21",
  "total": 1,
  "incidents": [
    {
      "incident_id": "inc-p1-evt-002",
      "scenario": "P1",
      "actor_id": "acct-admin-07",
      "severity": "Critical",
      "event_count": 2,
      "total_files": 300,
      "distinct_customers": 180,
      "counts_note": "customer counts are illustrative",
      "missing_evidence": [],
      "updated_at": "2026-03-12T10:04:00.087Z"
    }
  ]
}
```

### 3. Get incident with evidence

```http
GET /v1/runs/run-7f3a9c21/incidents/inc-p1-evt-002
```

Response, `200 OK`. This is the state right after `evt-003` (300 files). The state right after `evt-002` is the same record with `event_count` 1, `total_files` 170, `distinct_customers` 105, `event_ids` `["evt-002"]`, and the condition values shown in the screen mock in [design.md](../../.kiro/specs/finshield-ai/design.md).

```json
{
  "contract_version": "1.0",
  "run_id": "run-7f3a9c21",
  "incident": {
    "incident_id": "inc-p1-evt-002",
    "scenario": "P1",
    "actor_id": "acct-admin-07",
    "severity": "Critical",
    "severity_history": [
      {
        "old_severity": null,
        "new_severity": "Critical",
        "rule_id": "P1",
        "changed_at": "2026-03-12T10:02:00.412Z",
        "trigger_event_id": "evt-002"
      }
    ],
    "event_count": 2,
    "event_ids": ["evt-002", "evt-003"],
    "total_files": 300,
    "distinct_customers": 180,
    "counts_note": "customer counts are illustrative",
    "conditions": [
      { "name": "volume_in_window", "value_seen": 300, "limit": "more than 100", "state": "pass" },
      { "name": "multiple_of_normal", "value_seen": 300, "limit": "at least 50 (5 x upper end 10)", "state": "pass" },
      { "name": "privileged_account", "value_seen": true, "limit": true, "state": "pass" },
      { "name": "no_covering_approval", "value_seen": "returned no match", "limit": "no approval covers the export", "state": "pass" }
    ],
    "approvals_lookup": "empty",
    "baseline_scope": "personal",
    "missing_evidence": [],
    "evidence_ids": ["evt-001", "evt-002", "bl-001", "al-evt-002", "rr-evt-002-p1", "evt-003", "rr-evt-003-p1"],
    "proposed_actions": [
      {
        "action_id": "act-inc-p1-evt-002-1",
        "incident_id": "inc-p1-evt-002",
        "action_type": "suspend_account",
        "status": "pending_approval",
        "simulated": false,
        "proposed_at": "2026-03-12T10:02:00Z"
      },
      {
        "action_id": "act-inc-p1-evt-002-2",
        "incident_id": "inc-p1-evt-002",
        "action_type": "request_verification",
        "status": "pending_approval",
        "simulated": false,
        "proposed_at": "2026-03-12T10:02:00Z",
        "recipient_id": "owner-of-acct-admin-07"
      }
    ],
    "explanation": null,
    "created_at": "2026-03-12T10:02:00.412Z",
    "updated_at": "2026-03-12T10:04:00.087Z",
    "update_event_ids": ["evt-003"],
    "synthetic": true
  },
  "evidence": [
    { "evidence_id": "evt-001", "type": "event", "timestamp": "2026-03-12T10:00:00Z", "sequence": 1, "source_ref": "event:evt-001", "summary": "Export of 80 documents by ACTOR-1 to an internal destination.", "source_available": true },
    { "evidence_id": "bl-001", "type": "baseline", "timestamp": "2026-03-12T10:00:00Z", "sequence": 2, "source_ref": "baseline:bl-001", "summary": "Normal range 5 to 10 documents per 5 minutes, personal baseline.", "source_available": true },
    { "evidence_id": "evt-002", "type": "event", "timestamp": "2026-03-12T10:02:00Z", "sequence": 3, "source_ref": "event:evt-002", "summary": "Export of 90 documents by ACTOR-1 to an internal destination.", "source_available": true },
    { "evidence_id": "al-evt-002", "type": "approval_lookup", "timestamp": "2026-03-12T10:02:00Z", "sequence": 4, "source_ref": "approvals:lookup", "summary": "Approvals lookup returned no match.", "source_available": true },
    { "evidence_id": "rr-evt-002-p1", "type": "rule_result", "timestamp": "2026-03-12T10:02:00Z", "sequence": 5, "source_ref": "rule:P1", "summary": "170 files in 5 minutes. All four P1 conditions passed. Critical.", "source_available": true },
    { "evidence_id": "evt-003", "type": "event", "timestamp": "2026-03-12T10:04:00Z", "sequence": 6, "source_ref": "event:evt-003", "summary": "Export of 130 documents by ACTOR-1 to an internal destination.", "source_available": true },
    { "evidence_id": "rr-evt-003-p1", "type": "rule_result", "timestamp": "2026-03-12T10:04:00Z", "sequence": 7, "source_ref": "rule:P1", "summary": "300 files in 5 minutes. All four P1 conditions passed. Critical.", "source_available": true }
  ],
  "evidence_note": "Evidence for evt-001 is stored with a rule result rr-evt-001-p1 (80 files, volume check failed, no alert). It is listed in the full export and omitted here for length."
}
```

### 4. Request AI explanation

```http
POST /v1/runs/run-7f3a9c21/incidents/inc-p1-evt-002/explanations
Content-Type: application/json
```

```json
{
  "contract_version": "1.0",
  "question": "explain_incident"
}
```

`question` is `explain_incident` or `approvals_covered` ("Was this export covered by a valid audit approval?").

Response, `200 OK`, live answer accepted:

```json
{
  "contract_version": "1.0",
  "explanation": {
    "explanation_id": "ai-inc-p1-evt-002-1",
    "incident_id": "inc-p1-evt-002",
    "requested_at": "2026-03-12T10:31:05.220Z",
    "source": "live",
    "label": "Live explanation",
    "what_happened": "ACTOR-1, a privileged account, exported 300 files for 180 customers in 5 minutes (evt-002, evt-003). The normal range is 5 to 10 files (bl-001).",
    "supporting_evidence": [
      { "evidence_id": "rr-evt-003-p1", "shows": "All four P1 conditions passed at 300 files." },
      { "evidence_id": "al-evt-002", "shows": "The approvals lookup returned no match." },
      { "evidence_id": "bl-001", "shows": "Normal range is 5 to 10 documents per 5 minutes." }
    ],
    "what_remains_unknown": "No matching approval was found (al-evt-002). Whether the work was authorised outside the approvals source is not known.",
    "next_check": "Ask the account owner to confirm the export purpose.",
    "citation_check": { "result": "accepted", "failed_checks": [] }
  },
  "incident_unchanged": true
}
```

Response, `200 OK`, fallback (local path default, Bedrock timeout, error, or rejected answer):

```json
{
  "contract_version": "1.0",
  "explanation": {
    "explanation_id": "ai-inc-p1-evt-002-2",
    "incident_id": "inc-p1-evt-002",
    "requested_at": "2026-03-12T10:31:20.004Z",
    "source": "fallback",
    "fallback_reason": "model_timeout",
    "label": "Fallback summary - live model unavailable",
    "what_happened": "ACTOR-1, a privileged account, exported 300 files for 180 customers in 5 minutes (evt-002, evt-003).",
    "supporting_evidence": [
      { "evidence_id": "rr-evt-003-p1", "shows": "All four P1 conditions passed at 300 files." },
      { "evidence_id": "al-evt-002", "shows": "The approvals lookup returned no match." }
    ],
    "what_remains_unknown": "No matching approval was found (al-evt-002).",
    "next_check": "Ask the account owner to confirm the export purpose.",
    "citation_check": { "result": "accepted", "failed_checks": [] }
  },
  "incident_unchanged": true
}
```

If masking fails, no model is called and the response is `422` with `error.code` `masking_failed` and the message "AI request blocked because masking failed".

### 5. Reviewer action

```http
POST /v1/runs/run-7f3a9c21/actions/act-inc-p1-evt-002-1/decision
Content-Type: application/json
```

```json
{
  "contract_version": "1.0",
  "decision": "approve",
  "reviewer_id": "user-security-lead",
  "decision_note": "Unusual volume, no approval found."
}
```

Response, `200 OK`:

```json
{
  "contract_version": "1.0",
  "action": {
    "action_id": "act-inc-p1-evt-002-1",
    "incident_id": "inc-p1-evt-002",
    "action_type": "suspend_account",
    "status": "approved",
    "simulated": true,
    "proposed_at": "2026-03-12T10:02:00Z",
    "reviewer_id": "user-security-lead",
    "decided_at": "2026-03-12T10:32:10Z",
    "decision_note": "Unusual volume, no approval found."
  },
  "evidence_id": "act-inc-p1-evt-002-1-decision",
  "display_label": "Suspend account - approved - simulated"
}
```

Other outcomes: `reject` sets `status` to `rejected` and `simulated` stays `false`. An unauthorised reviewer gets `403` with `error.code` `not_authorised`. An action that is no longer pending gets `409` with `error.code` `conflict`. In both cases the status is unchanged (R14.8). A failed write keeps the status `pending_approval` and returns `500` with `error.code` `internal` (R14.7).

## Result states

Every check ends in exactly one of these states (R17). The state is carried in the result body, and the HTTP status follows the table. D-10 adds a fifth neutral label, `completed_findings_shown`, for a check that found something.

| State | HTTP status | Body signal |
|---|---|---|
| Successful empty result | `200` | Empty list or `state: "checked_nothing_found"` |
| Findings | `200` | `state: "completed_findings_shown"` |
| Missing evidence | `200` | `missing_evidence` has entries |
| Invalid input | `422` (contract or field rules), `400` (body is not parseable JSON) | `error.field_errors` |
| Unavailable AI service | `200` with `source: "fallback"` | `fallback_reason`, labelled fallback summary |

Unknown run or incident ID returns `404` with `error.code` `not_found`.

### Successful empty result

Chosen status: `200` with an empty list. "Nothing found" is an answer, not an error.

```http
GET /v1/runs/run-7f3a9c21/incidents?severity=High
```

```json
{
  "contract_version": "1.0",
  "run_id": "run-7f3a9c21",
  "total": 0,
  "incidents": [],
  "state": "checked_nothing_found",
  "checked_at": "2026-03-12T10:35:00Z",
  "message": "Checked, nothing found."
}
```

The same state applies to P1 at `evt-001` (80 files, volume check failed). A lookup that works but returns no record (for example no assignment for a customer, approvals `empty`) is also a successful empty result and is treated as a real answer.

### Missing evidence

Chosen status: `200`. Missing evidence is not an error and is not proof of wrongdoing (R17.6, R17.7). Example: approvals source unavailable, P1 opens High.

```json
{
  "contract_version": "1.0",
  "run_id": "run-3d51e9aa",
  "incident": {
    "incident_id": "inc-p1-evt-002",
    "severity": "High",
    "approvals_lookup": "unavailable",
    "conditions": [
      { "name": "volume_in_window", "value_seen": 170, "limit": "more than 100", "state": "pass" },
      { "name": "no_covering_approval", "value_seen": "unavailable", "limit": "no approval covers the export", "state": "not_evaluated", "missing_source": "approvals source" }
    ],
    "missing_evidence": ["approvals source"]
  },
  "missing_evidence_note": "Approval status is unknown because the approvals source was unavailable. This is missing evidence, not proof of wrongdoing."
}
```

The run ID above is a second illustrative run where the approvals source switch was set to unavailable. IDs are content-derived, so the incident ID is the same as in the main example. The dashboard shows up to 20 source names and a count of the rest.

### Invalid input

Chosen status: `422` when the JSON parses but breaks contract or field rules. `400` only when the body cannot be parsed. Stored data is unchanged.

Count mismatch (R2.8):

```json
{
  "contract_version": "1.0",
  "error": {
    "code": "invalid_input",
    "message": "Event evt-002 was rejected. Nothing was stored.",
    "field_errors": [
      { "field": "document_count", "rule": "must equal the number of listed document_id values", "value_seen": "reported 90, listed 89" }
    ]
  }
}
```

Document record missing a customer (R2.6, R2.7):

```json
{
  "contract_version": "1.0",
  "error": {
    "code": "invalid_input",
    "message": "Event evt-002 was rejected. Nothing was stored.",
    "field_errors": [
      { "field": "documents[12].customer_id", "rule": "required" }
    ]
  }
}
```

Unsupported version (R19.3):

```json
{
  "contract_version": "1.0",
  "error": {
    "code": "unsupported_contract_version",
    "message": "Contract version 0.9 is not supported.",
    "supported_versions": ["1.0"]
  }
}
```

Bad override on replay:

```json
{
  "contract_version": "1.0",
  "error": {
    "code": "invalid_input",
    "message": "Replay not started. Previous result is unchanged.",
    "field_errors": [
      { "field": "config_overrides.p1_volume_limit", "rule": "must be a whole number from 1 to 10000 (demo setting)", "value_seen": "-5" }
    ]
  }
}
```

### Unavailable AI service

Chosen behaviour: **`200` with `source: "fallback"`**, not `503`. This matches [design.md](../../.kiro/specs/finshield-ai/design.md): when Bedrock times out (10 seconds, proposed, not measured), errors, or fails the citation check, the dashboard shows the labelled fallback summary and "live model unavailable" (R13.6, R17.5). The caller always gets a usable explanation. The fallback record is stored as evidence with `fallback_reason`. See operation 4 for the example body.

`503` is not used for the AI service in version 1.0. It is reserved for the whole API being down (for example the Lambda or the local server is not reachable), where no body is guaranteed.

## Gaps filled here

Where [design.md](../../.kiro/specs/finshield-ai/design.md) did not fix a detail, this file defines it once:

| Topic | Definition |
|---|---|
| Path names and the `/v1` prefix | As in the API table above. |
| Replay request fields | `scenario`, `event_file`, `config_overrides`. Override keys are `p1_volume_limit`, `p1_window_minutes`, `p1_multiplier`, `grouping_window_minutes`, plus the P2 and P3 thresholds named in [scenarios.md](scenarios.md). Ranges are demo settings. |
| Allowed `operation` values | `export`, `upload`, `record_access`, `login`. |
| Evidence ID for a decision | Action ID plus `-decision`. |
| AI question types | `explain_incident` and `approvals_covered`. |
| HTTP status for invalid input | 422 for contract and field errors, 400 for unparseable JSON. |
| Reviewer IDs | `user-analyst` and `user-security-lead` (D-07). |
| Sort order and size of incident list | Newest `updated_at` first, at most 100. |
