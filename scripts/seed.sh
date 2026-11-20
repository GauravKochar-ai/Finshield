#!/usr/bin/env bash
# 1) Cognito demo users, one per group (synthetic, known demo password).  2) seed data (M7 generator).
cd "$(dirname "$0")/.."
source scripts/_common.sh
POOL="$(output UserPoolId)"
PASSWORD="${DEMO_PASSWORD:-FinShield#Demo2026}"
for pair in analyst:Analyst securityhead:SecurityHead compliancehead:ComplianceHead auditor:Auditor admin:Admin; do
  name="${pair%%:*}"; group="${pair##*:}"; email="$name@finshield.example"
  aws cognito-idp admin-create-user --user-pool-id "$POOL" --username "$email" --message-action SUPPRESS \
    --user-attributes Name=email,Value="$email" Name=email_verified,Value=true >/dev/null 2>&1 || echo "user $email exists"
  aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username "$email" --password "$PASSWORD" --permanent
  aws cognito-idp admin-add-user-to-group --user-pool-id "$POOL" --username "$email" --group-name "$group"
  echo "demo user $email -> $group"
done
if [ -f simulator/seed/generate.py ]; then
  python3 simulator/seed/generate.py --load
else
  echo "STUB: simulator/seed/generate.py not written yet (M7). Cognito users only."
fi
