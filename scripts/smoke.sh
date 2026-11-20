#!/usr/bin/env bash
# End-to-end smoke: deploy check, SC-01, poll for one CRITICAL alert scoring 96 (90 s), verify evidence.
cd "$(dirname "$0")/.."
source scripts/_common.sh
set +e
fail=0
step() { if [ "$2" = 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; fail=1; fi; }

API="$(output ApiUrl)"; POOL="$(output UserPoolId)"; CLIENT="$(output UserPoolClientId)"
[ -n "$API" ] && [ "$API" != None ]; step "stack outputs present ($STACK)" $?

PASSWORD="${DEMO_PASSWORD:-FinShield#Demo2026}"
TOKEN="$(aws cognito-idp initiate-auth --client-id "$CLIENT" --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=admin@finshield.example,PASSWORD="$PASSWORD" --query AuthenticationResult.IdToken --output text 2>/dev/null)"
[ -n "$TOKEN" ] && [ "$TOKEN" != None ]; step "sign in as admin (run make seed first)" $?
api() { curl -s -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' "$@"; }

./scripts/scenario.sh SC-01 >/dev/null; step "SC-01 sent" $?

ALERT=""; end=$((SECONDS+90))
while [ $SECONDS -lt $end ]; do
  ALERT="$(api "$API/alerts?severity=CRITICAL" | python3 -c '
import json,sys
d=json.load(sys.stdin)["data"] or []
m=[a["alert_id"] for a in d if a["score"]==96 and a["scenario_id"]=="SC-01"]
print(m[0] if len(m)==1 else "")' 2>/dev/null)"
  [ -n "$ALERT" ] && break; sleep 3
done
[ -n "$ALERT" ]; step "exactly one CRITICAL alert, score 96 within 90 s${ALERT:+ ($ALERT)}" $?

if [ -n "$ALERT" ]; then
  api -X POST "$API/alerts/$ALERT/evidence/verify" | python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin)["data"]["valid"] else 1)'
  step "evidence chain verifies" $?
fi
[ $fail = 0 ] && echo "SMOKE PASS" || echo "SMOKE FAIL"
exit $fail
