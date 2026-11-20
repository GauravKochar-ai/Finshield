# Tasks: M7 Data, simulator, API and accuracy

P0 carries the mandatory demo, P1 the other scenarios and judging points, P2 depth. Do not start P1 until P0 passes its checkpoint.

## P0

- [ ] P0.1 `simulator/seed/generate.py` and `scripts/seed.sh` for all 13 tables plus 200 sample KYC files
- [ ] P0.2 Scenario files SC-01 to SC-10 and SC-01b from the playbook table
- [ ] P0.3 `simulator` Lambda: scenario replay and reset
- [ ] P0.4 Read API handlers for every GET endpoint, responses validated against openapi.yaml

## P1

- [ ] P1.1 `test_runner` and Accuracy endpoints with 7 normal days
- [ ] P1.2 `scripts/real_mode.py`

## P2

- [ ] P2.1 GuardDuty `create-sample-findings` button
