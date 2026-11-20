# Requirements: M6 Frontend (Next.js admin portal)

Owner: M6. Needs from: Contract fixtures, then the M7 API. Gives to: Dashboard and demo buttons.

Steering: `.kiro/steering/*`. Contract: `contract/` (config.json, schemas, openapi.yaml, fixtures). Playbook: `docs/playbook.md`. Contract changes go to `contract/CHANGES.md`, never silently.

## User story

As the frontend owner, I want the admin portal to run on mocks first and then on the live API, so the demo can be clicked through end to end.

## Requirements

### R1. Client and hosting

1.1. THE SYSTEM SHALL read data only through `web/lib/api.ts`, which follows `contract/openapi.yaml`.
1.2. WHERE `NEXT_PUBLIC_USE_MOCKS=true` THE SYSTEM SHALL serve `contract/fixtures` and need no backend.
1.3. THE SYSTEM SHALL build as a static export (`output: 'export'`) with no API routes, middleware or server actions.

### R2. Overview and alert detail

2.1. THE SYSTEM SHALL show posture score, alerts by severity, active alerts, compliance and privacy tiles and live regulator deadline countdowns.
2.2. THE SYSTEM SHALL show the alert score bar split by signal with points and facts, the event timeline, the AI card (labelled FALLBACK when so), containment status, approve and reject, and the evidence chain with Verify.
2.3. WHILE an alert status is not CLOSED THE SYSTEM SHALL poll it every 3 s.

### R3. Sign-in and roles

3.1. THE SYSTEM SHALL sign in with Cognito and show decision and release buttons only to groups allowed by `x-groups` in the API spec.

### R4. Demo panels

4.1. THE SYSTEM SHALL provide a Simulator panel (one button per scenario, GuardDuty sample, reset), an Accuracy panel, report tabs, Release and Tamper demo.

### R5. Wording and colours

5.1. THE SYSTEM SHALL show only "DPDP-aligned readiness" wording and the term "consent ledger"; severity colours SHALL be CRITICAL red, HIGH orange, MEDIUM amber.

## Done when

The full SC-01 story can be clicked through on live data with no console errors.
