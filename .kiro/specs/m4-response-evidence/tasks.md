# Tasks: M4 Response workflow and evidence

P0 carries the mandatory demo, P1 the other scenarios and judging points, P2 depth. Do not start P1 until P0 passes its checkpoint.

## P0

- [x] P0.1 Evidence hash chain, append and verify with unit tests (done in `backend/tests/test_evidence.py`)
- [ ] P0.2 Finish `incident.asl.json` against the Step Functions section of contract.md and test it with `alert_raised_critical.json`
- [ ] P0.3 `contain_revoke_sessions`, `contain_deactivate_keys`, `contain_bucket_deny` for LIVE and DRY_RUN, each writing evidence
- [ ] P0.4 `set_deadlines` from config; SNS notification; evidence export to the Object Lock bucket

## P1

- [ ] P1.1 `decision` handler with task token storage and POST /decision
- [ ] P1.2 30-minute escalation to ComplianceHead
- [ ] P1.3 `quarantine` after APPROVE and `release` that restores access
- [ ] P1.4 `tamper_demo` reporting the right broken seq

## P2

- [ ] P2.1 `contain_dns_block` with DNS Firewall
- [ ] P2.2 High branch step-up MFA flag
