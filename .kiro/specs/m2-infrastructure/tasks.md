# Tasks: M2 Infrastructure (SAM)

P0 carries the mandatory demo, P1 the other scenarios and judging points, P2 depth. Do not start P1 until P0 passes its checkpoint.

## P0

- [x] P0.1 Layer, bus, 13 tables, 5 buckets, SSM parameters, SNS topic, HTTP API, state machine and stub Lambdas defined; `sam validate --lint` passes (not yet deployed)
- [ ] P0.2 Write `scripts/sandbox-check.sh` (bedrock converse, cloudtrail put-event-selectors, s3 object lock, config recorders, guardduty, iam put-role-policy, cognito, route53resolver, cloudfront) printing ALLOWED/DENIED
- [ ] P0.3 Run `make deploy` from a clean account and fix real deploy failures that lint cannot see (bucket name clashes, Guardrail PII types, Object Lock)
- [ ] P0.4 Demo principals and CloudTrail trail with data events on the KYC bucket only; show a real GetObject reaching the normalizer logs

## P1

- [x] P1.1 Cognito pool, client, five groups; `make seed` creates one demo user per group
- [x] P1.2 CloudFront with OAC, KMS key, Bedrock Guardrail resource defined
- [ ] P1.3 Config rules (3) and recorder, GuardDuty detector behind their parameters; confirm against what the account already has
- [ ] P1.4 CloudWatch dashboard and alarm; have `detection` emit `TimeToDetectMs`

## P2

- [ ] P2.1 DNS Firewall (needs `VpcId`) behind `EnableDnsFirewall`
- [ ] P2.2 Knowledge Base id written to SSM when a vector store is allowed
