#!/usr/bin/env bash
# scripts/sandbox-check.sh - what does the AWS sandbox allow? (FinShield AI, AI FORGE 2026)
#
# Prints ALLOWED or DENIED for every service the stack needs, then a short info block.
# Anything it creates (test bucket, test IAM role, test Cognito pool) is deleted again,
# even if the script fails half-way. Nothing else in the account is changed.
#
# Usage:   bash scripts/sandbox-check.sh [MODEL_ID]
#          bash scripts/sandbox-check.sh global.anthropic.claude-haiku-5-5 | tee sandbox-check.txt
# Region:  AWS_REGION / AWS_DEFAULT_REGION, default ap-south-1
set -uo pipefail
export AWS_PAGER=""

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-south-1}}"
MODEL_ID="${1:-${MODEL_ID:-global.anthropic.claude-haiku-5-5}}"

if ! ACCOUNT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)"; then
  echo "Not logged in to AWS. Run 'aws configure' (or 'aws sso login') and try again."
  exit 1
fi
CALLER="$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)"

SUFFIX="$(date +%s)-${RANDOM}"
TEST_BUCKET="fs-sandbox-check-${ACCOUNT}-${SUFFIX}"
TEST_ROLE="fs-sandbox-check-${SUFFIX}"
TEST_POOL="fs-sandbox-check-${SUFFIX}"
POOL_ID=""
ROLE_CREATED=0
BUCKET_CREATED=0
N_ALLOWED=0
N_DENIED=0
SUMMARY=""

# ---------------------------------------------------------------- helpers
short() {   # one line, AWS error message only, max 150 chars
  tr '\n' ' ' <<<"$1" | sed -E 's/.*(An error occurred)/\1/' | cut -c1-150
}

denied_text() {
  grep -qiE "AccessDenied|UnauthorizedOperation|not authorized|AuthorizationError|explicit deny|UnrecognizedClient|InvalidClientTokenId" <<<"$1"
}

record() {  # record <check name> <ALLOWED|DENIED> <detail>
  local line
  line="$(printf "%-8s %-46s %s" "$2" "$1" "$3")"
  echo "$line"
  SUMMARY+="${line}"$'\n'
  if [[ "$2" == "ALLOWED" ]]; then N_ALLOWED=$((N_ALLOWED + 1)); else N_DENIED=$((N_DENIED + 1)); fi
}

fail() {    # fail <check name> <aws output>
  if denied_text "$2"; then
    record "$1" "DENIED" "$(short "$2")"
  else
    record "$1" "DENIED" "(not a permission error, check it) $(short "$2")"
  fi
}

cleanup() {
  if [[ -n "$POOL_ID" ]]; then
    aws cognito-idp delete-user-pool --region "$REGION" --user-pool-id "$POOL_ID" >/dev/null 2>&1
  fi
  if [[ "$ROLE_CREATED" == 1 ]]; then
    aws iam delete-role-policy --role-name "$TEST_ROLE" --policy-name fs-sandbox-check >/dev/null 2>&1
    aws iam delete-role --role-name "$TEST_ROLE" >/dev/null 2>&1
  fi
  if [[ "$BUCKET_CREATED" == 1 ]]; then
    aws s3api delete-bucket --region "$REGION" --bucket "$TEST_BUCKET" >/dev/null 2>&1
  fi
}
trap cleanup EXIT

echo "FinShield sandbox check  |  account ${ACCOUNT}  |  region ${REGION}"
echo "caller: ${CALLER}"
echo "-----------------------------------------------------------------------------------------"

# 1. Bedrock Converse ---------------------------------------------------------------------
if out="$(aws bedrock-runtime converse --region "$REGION" --model-id "$MODEL_ID" \
      --messages '[{"role":"user","content":[{"text":"Reply with the single word OK"}]}]' \
      --inference-config '{"maxTokens":10,"temperature":0}' \
      --query 'output.message.content[0].text' --output text 2>&1)"; then
  record "bedrock-runtime converse" "ALLOWED" "model ${MODEL_ID} replied: $(short "$out")"
else
  fail "bedrock-runtime converse (${MODEL_ID})" "$out"
fi

# 2. CloudTrail put-event-selectors (probe on a trail that does not exist: nothing changes) -
if out="$(aws cloudtrail put-event-selectors --region "$REGION" --trail-name fs-sandbox-check-no-such-trail \
      --event-selectors '[{"ReadWriteType":"All","IncludeManagementEvents":true}]' 2>&1)"; then
  record "cloudtrail put-event-selectors" "ALLOWED" "permission OK"
elif grep -q "TrailNotFound" <<<"$out"; then
  record "cloudtrail put-event-selectors" "ALLOWED" "permission OK (probed a non-existent trail, nothing changed)"
else
  fail "cloudtrail put-event-selectors" "$out"
fi

# 3. S3 bucket with Object Lock (created, then deleted) -----------------------------------
if [[ "$REGION" == "us-east-1" ]]; then
  out="$(aws s3api create-bucket --region "$REGION" --bucket "$TEST_BUCKET" --object-lock-enabled-for-bucket 2>&1)"
else
  out="$(aws s3api create-bucket --region "$REGION" --bucket "$TEST_BUCKET" \
        --create-bucket-configuration LocationConstraint="$REGION" --object-lock-enabled-for-bucket 2>&1)"
fi
if [[ $? -eq 0 ]]; then
  BUCKET_CREATED=1
  if aws s3api delete-bucket --region "$REGION" --bucket "$TEST_BUCKET" >/dev/null 2>&1; then
    BUCKET_CREATED=0
    record "s3api create-bucket --object-lock-enabled" "ALLOWED" "test bucket created and deleted"
  else
    record "s3api create-bucket --object-lock-enabled" "ALLOWED" "created; delete will be retried on exit (${TEST_BUCKET})"
  fi
else
  fail "s3api create-bucket --object-lock-enabled" "$out"
fi

# 4. AWS Config recorders -----------------------------------------------------------------
CONFIG_RECORDERS="?"
if out="$(aws configservice describe-configuration-recorders --region "$REGION" \
      --query 'length(ConfigurationRecorders)' --output text 2>&1)"; then
  CONFIG_RECORDERS="$out"
  rec_on="$(aws configservice describe-configuration-recorder-status --region "$REGION" \
            --query 'ConfigurationRecordersStatus[0].recording' --output text 2>/dev/null || echo "?")"
  record "configservice describe-configuration-recorders" "ALLOWED" "recorders: ${out}, recording: ${rec_on}"
else
  fail "configservice describe-configuration-recorders" "$out"
fi

# 5. GuardDuty detectors ------------------------------------------------------------------
GD_DETECTORS="?"
if out="$(aws guardduty list-detectors --region "$REGION" --query 'length(DetectorIds)' --output text 2>&1)"; then
  GD_DETECTORS="$out"
  record "guardduty list-detectors" "ALLOWED" "detectors: ${out}"
else
  fail "guardduty list-detectors" "$out"
fi

# 6. IAM create-role + put-role-policy on a test role (both deleted) ----------------------
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Action":"s3:GetObject","Resource":"*"}]}'
if out="$(aws iam create-role --role-name "$TEST_ROLE" --assume-role-policy-document "$TRUST" \
      --tags Key=project,Value=finshield-ai Key=purpose,Value=sandbox-check 2>&1)"; then
  ROLE_CREATED=1
  record "iam create-role (test role)" "ALLOWED" "${TEST_ROLE}"
  if out="$(aws iam put-role-policy --role-name "$TEST_ROLE" --policy-name fs-sandbox-check \
        --policy-document "$POLICY" 2>&1)"; then
    record "iam put-role-policy (test role)" "ALLOWED" "inline policy attached (removed on exit)"
  else
    fail "iam put-role-policy (test role)" "$out"
  fi
else
  fail "iam create-role (test role)" "$out"
  record "iam put-role-policy (test role)" "DENIED" "skipped: could not create the test role"
fi

# 7. Cognito create-user-pool (created, then deleted) -------------------------------------
if out="$(aws cognito-idp create-user-pool --region "$REGION" --pool-name "$TEST_POOL" \
      --query 'UserPool.Id' --output text 2>&1)"; then
  POOL_ID="$out"
  if aws cognito-idp delete-user-pool --region "$REGION" --user-pool-id "$POOL_ID" >/dev/null 2>&1; then
    record "cognito-idp create-user-pool" "ALLOWED" "test pool ${POOL_ID} created and deleted"
    POOL_ID=""
  else
    record "cognito-idp create-user-pool" "ALLOWED" "created ${POOL_ID}; delete will be retried on exit"
  fi
else
  fail "cognito-idp create-user-pool" "$out"
fi

# 8. Route 53 Resolver DNS Firewall ------------------------------------------------------
if out="$(aws route53resolver list-firewall-domain-lists --region "$REGION" --max-results 5 \
      --query 'length(FirewallDomainLists)' --output text 2>&1)"; then
  record "route53resolver list-firewall-domain-lists" "ALLOWED" "domain lists visible: ${out}"
else
  fail "route53resolver list-firewall-domain-lists" "$out"
fi

# 9. CloudFront -------------------------------------------------------------------------
if out="$(aws cloudfront list-distributions --query 'DistributionList.Quantity' --output text 2>&1)"; then
  record "cloudfront list-distributions" "ALLOWED" "distributions: ${out}"
else
  fail "cloudfront list-distributions" "$out"
fi

# ---------------------------------------------------------------- info for the team
LAMBDA_LIMIT="$(aws lambda get-account-settings --region "$REGION" \
                --query 'AccountLimit.ConcurrentExecutions' --output text 2>/dev/null || echo "?")"
DEFAULT_VPC="$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true \
               --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "?")"

echo "-----------------------------------------------------------------------------------------"
echo "RESULT: ${N_ALLOWED} ALLOWED, ${N_DENIED} DENIED"
echo
echo "INFO"
echo "  Bedrock model ID to use : ${MODEL_ID}"
echo "  Lambda concurrency limit: ${LAMBDA_LIMIT}   (if 10: reserved concurrency in the template will fail)"
echo "  Default VPC (P2 DNS FW) : ${DEFAULT_VPC}"
if [[ "$CONFIG_RECORDERS" == "0" ]]; then
  echo "  AWS Config              : no recorder -> deploy with CreateConfigRecorder=true EnableConfigRules=true"
elif [[ "$CONFIG_RECORDERS" != "?" ]]; then
  echo "  AWS Config              : recorder exists -> deploy with EnableConfigRules=true only"
fi
if [[ "$GD_DETECTORS" == "0" ]]; then
  echo "  GuardDuty               : no detector -> deploy with CreateGuardDutyDetector=true"
elif [[ "$GD_DETECTORS" != "?" ]]; then
  echo "  GuardDuty               : detector exists -> do not create another one"
fi
echo
echo "Cleanup: test bucket, test IAM role and test Cognito pool are deleted automatically."
