#!/usr/bin/env bash
# Write web/.env.local from CloudFormation stack outputs.
cd "$(dirname "$0")/.."
source scripts/_common.sh
OUT=web/.env.local
cat > "$OUT" <<ENV
NEXT_PUBLIC_API_URL=$(output ApiUrl)
NEXT_PUBLIC_REGION=$(output Region)
NEXT_PUBLIC_USER_POOL_ID=$(output UserPoolId)
NEXT_PUBLIC_USER_POOL_CLIENT_ID=$(output UserPoolClientId)
NEXT_PUBLIC_USE_MOCKS=false
ENV
echo "wrote $OUT"; sed 's/^/  /' "$OUT"
