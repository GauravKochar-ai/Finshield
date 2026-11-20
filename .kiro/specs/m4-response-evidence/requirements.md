# Requirements: M4 Response workflow and evidence

Owner: M4. Needs from: M3 alerts, M5 AI Lambdas. Gives to: Incident workflow and evidence chain.

Steering: `.kiro/steering/*`. Contract: `contract/` (config.json, schemas, openapi.yaml, fixtures). Playbook: `docs/playbook.md`. Contract changes go to `contract/CHANGES.md`, never silently.

## User story

As the response owner, I want an incident workflow that contains the threat before AI finishes, asks for approval and seals every step into a tamper-evident chain, so the demo shows controlled, reversible response.

## Requirements

### R1. Workflow

1.1. WHEN an `Alert Raised` event arrives THE SYSTEM SHALL start `finshield-dev-incident` with execution name `<alert_id>-<severity>`.
1.2. THE SYSTEM SHALL write evidence `ALERT_RAISED`, set deadlines (RBI +6 h, CERT-In +6 h, DPB +72 h from `detected_at`, read from config), then branch on severity.
1.3. WHERE severity is CRITICAL THE SYSTEM SHALL run containment and AI explanation in parallel, never making containment wait for AI, and invoke AI reports asynchronously.
1.4. THE SYSTEM SHALL wait for approval with `waitForTaskToken` for 30 minutes, escalate to ComplianceHead on timeout, then wait again.

### R2. Containment

2.1. THE SYSTEM SHALL provide revoke sessions (inline deny on `aws:TokenIssueTime`), deactivate keys, bucket deny (Sid `FinShieldDeny<user>`) and DNS block, each taking `{alert_id, principal_arn, mode}` and returning `{action, mode, result, detail}`.
2.2. WHERE `containment_mode` is DRY_RUN THE SYSTEM SHALL write the exact IAM or S3 call it would make into evidence instead of calling it.
2.3. THE SYSTEM SHALL make every containment reversible through `release`.

### R3. Evidence

3.1. THE SYSTEM SHALL write evidence only through `finshield.evidence.append` (conditional put on `seq`).
3.2. WHEN verify runs on a modified chain THE SYSTEM SHALL return `{valid:false, broken_at_seq}` with the first bad seq.
3.3. THE SYSTEM SHALL export the chain to the Object Lock bucket at the end of the workflow.

### R4. Decision and release

4.1. WHEN a SecurityHead or ComplianceHead posts APPROVE THE SYSTEM SHALL quarantine the principal and set status LOCKED; WHEN REJECT, it SHALL record the reason and keep containment.
4.2. WHEN a SecurityHead posts release THE SYSTEM SHALL remove every deny and the demo principal SHALL read the bucket again.
4.3. WHEN an Admin runs tamper-demo THE SYSTEM SHALL verify an edited copy and leave the stored chain untouched.

## Done when

The SC-01 alert runs the full workflow, containment is visible in IAM (or DRY_RUN evidence), and release fully restores access.
