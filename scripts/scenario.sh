#!/usr/bin/env bash
# Replay one scenario through the simulator Lambda: scripts/scenario.sh SC-01
cd "$(dirname "$0")/.."
source scripts/_common.sh
SC="${1:?usage: scenario.sh SC-01}"
[ -f "simulator/scenarios/$SC.json" ] || echo "note: simulator/scenarios/$SC.json missing (M7 writes it); simulator is still called"
aws lambda invoke --function-name "finshield-$STAGE-simulator" --cli-binary-format raw-in-base64-out \
  --payload "{\"scenario_id\":\"$SC\"}" /tmp/finshield-scenario.out >/dev/null
cat /tmp/finshield-scenario.out; echo
