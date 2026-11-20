#!/usr/bin/env bash
# Run all scenarios via the test_runner Lambda.
cd "$(dirname "$0")/.."
source scripts/_common.sh
aws lambda invoke --function-name "finshield-$STAGE-test-runner" --cli-binary-format raw-in-base64-out \
  --payload '{}' /tmp/finshield-accuracy.out >/dev/null
cat /tmp/finshield-accuracy.out; echo
