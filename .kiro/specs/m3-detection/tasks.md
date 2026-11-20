# Tasks: M3 Detection pipeline

P0 carries the mandatory demo, P1 the other scenarios and judging points, P2 depth. Do not start P1 until P0 passes its checkpoint.

## P0

- [ ] P0.1 `normalizer`: CloudTrail, sign-in, STS, logging change, GuardDuty, Config mapping with idempotency and raw archive
- [ ] P0.2 `detection`: atomic counters, S1 to S8, E1 to E3, severity from config, conditional upsert, `Alert Raised` on severity increase
- [ ] P0.3 pytest: SC-01 (96 CRITICAL) and SC-01b (81 CRITICAL), then logged-only scenarios

## P1

- [ ] P1.1 S9 consent mismatch, S10 abnormal disbursement, S11 misconfiguration
- [ ] P1.2 `baseline` Lambda with hourly schedule, on-demand run, team fallback for users under 14 days
- [ ] P1.3 All 10 scenarios plus SC-01b match expected score and level

## P2

- [ ] P2.1 Late events re-score their window
- [ ] P2.2 Per-device counters across accounts
