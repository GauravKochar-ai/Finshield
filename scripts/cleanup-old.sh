#!/usr/bin/env bash
# scripts/cleanup-old.sh - remove the OLD FinShield buckets/tables so only the brief's stack (finshield-dev) remains.
#
#   bash scripts/cleanup-old.sh            # LIST ONLY - shows exactly what would be deleted, changes nothing
#   bash scripts/cleanup-old.sh --delete   # deletes it, after you type DELETE
#
# Deletes (only what exists):
#   - stack fs-infra: 5 buckets (fs-raw-logs, fs-evidence, fs-kyc-aadhaar/pan/voter), 3 tables (fs-events,
#     fs-cases, fs-kyc-documents) plus its KMS key (7-day wait), SNS fs-alerts, /aws/lambda/fs-* log groups, alarms
#   - stack finshield-demo (boilerplate test), incl. its retained evidence bucket
#   - other fs-* buckets/tables that belong to no stack
#   - finshield-dev-* buckets/tables ONLY when the finshield-dev stack does not exist or is a failed first deploy
# Never touches: a working finshield-dev stack, the SAM deploy bucket (aws-sam-cli-managed-*), anything else.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AWS_PAGER=""
REGION="${REGION:-ap-south-1}"; export AWS_DEFAULT_REGION="$REGION" AWS_REGION="$REGION"
OLD_STACKS="fs-infra finshield-demo"
TEAM_STACK="finshield-dev"
MODE="list"; [ "${1:-}" = "--delete" ] && MODE="delete"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

step(){ echo; echo "==== $*"; }
die(){ echo; echo "STOPPED: $*"; exit 1; }
lines(){ tr '\t' '\n' | grep -v '^None$' | grep -v '^$'; }
stack_status(){ aws cloudformation describe-stacks --stack-name "$1" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo NONE; }
stack_res(){ aws cloudformation list-stack-resources --stack-name "$1" \
  --query "StackResourceSummaries[?ResourceType=='$2' && ResourceStatus!='DELETE_COMPLETE'].PhysicalResourceId" --output text 2>/dev/null | lines; }
bucket_exists(){ aws s3api head-bucket --bucket "$1" >/dev/null 2>&1; }
lock_mode(){ local m; m=$(aws s3api get-object-lock-configuration --bucket "$1" \
  --query 'ObjectLockConfiguration.Rule.DefaultRetention.Mode' --output text 2>/dev/null) || { echo none; return; }
  [ "$m" = "None" ] && m="ON"; echo "$m"; }
bucket_count(){ aws s3api list-object-versions --bucket "$1" --output json 2>/dev/null | python3 -c '
import sys, json
try: d = json.load(sys.stdin)
except Exception: print("?"); sys.exit()
print(len(d.get("Versions") or []) + len(d.get("DeleteMarkers") or []))'; }
table_count(){ aws dynamodb describe-table --table-name "$1" --query 'Table.ItemCount' --output text 2>/dev/null || echo "?"; }
show_bucket(){ echo "   bucket  $1   (objects incl. old versions: $(bucket_count "$1"), object lock: $(lock_mode "$1"))"; }
show_table(){ echo "   table   $1   (items: $(table_count "$1"))"; }

empty_bucket(){   # deletes every object version and delete marker in bucket $1
  local b="$1" bypass="" res i
  [ "$(lock_mode "$b")" != "none" ] && bypass="--bypass-governance-retention"
  for i in $(seq 1 500); do
    aws s3api list-object-versions --bucket "$b" --max-items 1000 --output json 2>/dev/null | python3 -c '
import sys, json
try: d = json.load(sys.stdin)
except Exception: d = {}
o = [{"Key": x["Key"], "VersionId": x["VersionId"]} for x in (d.get("Versions") or []) + (d.get("DeleteMarkers") or [])]
print(json.dumps({"Objects": o[:1000], "Quiet": True}) if o else "")' > "$TMP/batch.json"
    [ -s "$TMP/batch.json" ] && [ "$(head -c 1 "$TMP/batch.json")" = "{" ] || return 0
    res=$(aws s3api delete-objects --bucket "$b" --delete "file://$TMP/batch.json" $bypass --output json 2>&1) \
      || { echo "   delete-objects failed on $b: $(echo "$res" | head -c 300)"; return 1; }
    if echo "$res" | grep -q '"Errors"'; then
      echo "   some objects in $b cannot be deleted (Object Lock COMPLIANCE or legal hold?):"; echo "$res" | head -c 400; echo
      return 1
    fi
  done
  echo "   $b: still not empty after 500 batches"; return 1
}
delete_bucket(){ bucket_exists "$1" || return 0
  echo " - emptying + deleting bucket $1"
  empty_bucket "$1" && aws s3api delete-bucket --bucket "$1" && echo "   deleted $1" || { echo "   FAILED: $1"; FAILS=$((FAILS+1)); }; }
delete_table(){ echo " - deleting table $1"
  if [ "$(aws dynamodb describe-table --table-name "$1" --query Table.DeletionProtectionEnabled --output text 2>/dev/null)" = "True" ]; then
    aws dynamodb update-table --table-name "$1" --no-deletion-protection-enabled >/dev/null; fi
  aws dynamodb delete-table --table-name "$1" >/dev/null && aws dynamodb wait table-not-exists --table-name "$1" \
    && echo "   deleted $1" || { echo "   FAILED: $1"; FAILS=$((FAILS+1)); }; }

# ---------------------------------------------------------------------------------------------
step "1/3 What exists now ($MODE mode)"
ACCT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || die "AWS CLI is not logged in"
echo "account $ACCT | region $REGION"

DEL_STACKS=""; STACK_BUCKETS=""; TRAILS=""; EXTRA_BUCKETS=""; EXTRA_TABLES=""
for S in $OLD_STACKS; do
  ST=$(stack_status "$S")
  [ "$ST" = "NONE" ] && { echo; echo "stack $S: not found (nothing to do)"; continue; }
  case "$ST" in *_IN_PROGRESS) die "stack $S is busy ($ST). Wait for it to finish, then re-run.";; esac
  echo; echo "stack $S: $ST  -> WILL BE DELETED with everything in it:"
  DEL_STACKS="$DEL_STACKS $S"
  for b in $(stack_res "$S" AWS::S3::Bucket); do show_bucket "$b"; STACK_BUCKETS="$STACK_BUCKETS $b"; done
  for t in $(stack_res "$S" AWS::DynamoDB::Table); do show_table "$t"; done
  TRAILS="$TRAILS $(stack_res "$S" AWS::CloudTrail::Trail | tr '\n' ' ')"
  echo "   plus:"; aws cloudformation list-stack-resources --stack-name "$S" \
    --query "StackResourceSummaries[?ResourceType!='AWS::S3::Bucket' && ResourceType!='AWS::DynamoDB::Table'].ResourceType" \
    --output text 2>/dev/null | lines | sort | uniq -c | sed 's/^/     /'
done

TST=$(stack_status "$TEAM_STACK")
case "$TST" in
  NONE|ROLLBACK_COMPLETE|ROLLBACK_FAILED|DELETE_FAILED) PREFIXES="fs- finshield-dev-"
    [ "$TST" != "NONE" ] && { echo; echo "stack $TEAM_STACK: $TST (failed first deploy, holds nothing) -> WILL BE DELETED"; DEL_STACKS="$DEL_STACKS $TEAM_STACK"; } ;;
  *_IN_PROGRESS) die "stack $TEAM_STACK is busy ($TST). Wait, then re-run." ;;
  *) PREFIXES="fs-"; echo; echo "stack $TEAM_STACK: $TST -> KEPT (this is the brief's stack; its finshield-dev-* resources are not touched)" ;;
esac

ALL_BUCKETS=$(aws s3api list-buckets --query 'Buckets[].Name' --output text 2>/dev/null | lines)
ALL_TABLES=$(aws dynamodb list-tables --query 'TableNames' --output text 2>/dev/null | lines)
owner_of(){ local o; o=$(aws cloudformation describe-stack-resources --physical-resource-id "$1" \
  --query 'StackResources[0].StackName' --output text 2>/dev/null) || o=""; [ "$o" = "None" ] && o=""; echo "$o"; }
in_list(){ case " $2 " in *" $1 "*) return 0;; esac; return 1; }
KEPT=""
for P in $PREFIXES; do
  for b in $(echo "$ALL_BUCKETS" | grep "^$P" || true); do
    in_list "$b" "$STACK_BUCKETS" && continue          # goes with its stack
    o=$(owner_of "$b")
    if [ -z "$o" ] || in_list "$o" "$DEL_STACKS"; then EXTRA_BUCKETS="$EXTRA_BUCKETS $b"; else KEPT="$KEPT\n   bucket  $b  (belongs to stack $o)"; fi
  done
  for t in $(echo "$ALL_TABLES" | grep "^$P" || true); do
    o=$(owner_of "$t")
    if [ -z "$o" ]; then EXTRA_TABLES="$EXTRA_TABLES $t"
    elif ! in_list "$o" "$DEL_STACKS"; then KEPT="$KEPT\n   table   $t  (belongs to stack $o)"; fi
  done
done
if [ -n "$EXTRA_BUCKETS$EXTRA_TABLES" ]; then
  echo; echo "leftovers (old names, in no stack) -> WILL BE DELETED:"
  for b in $EXTRA_BUCKETS; do show_bucket "$b"
    if [ "$(lock_mode "$b")" = "COMPLIANCE" ] && [ "$(bucket_count "$b")" != "0" ]; then
      echo "     ^ COMPLIANCE lock with objects: AWS will refuse to delete it until retention ends. Tell Keshav (the brief needs this name)."; fi
  done
  for t in $EXTRA_TABLES; do show_table "$t"; done
fi
[ -n "$KEPT" ] && { echo; echo "NOT touched (owned by other stacks):"; printf "%b\n" "$KEPT" | grep -v '^$'; }

if [ -z "$DEL_STACKS$EXTRA_BUCKETS$EXTRA_TABLES" ]; then echo; echo "Nothing old left. You're clean."; exit 0; fi

if [ "$MODE" = "list" ]; then
  cat <<EOF

LIST ONLY - nothing was changed.
Check the list above. The fs-kyc-* buckets were made on a teammate's request: make sure nobody still uses them.
To delete all of it:   bash scripts/cleanup-old.sh --delete
EOF
  exit 0
fi

# ---------------------------------------------------------------------------------------------
step "2/3 Delete (PERMANENT)"
echo "Everything listed above will be PERMANENTLY deleted: files in the buckets (all versions) and all table items."
echo "This cannot be undone. fs-infra's KMS key is scheduled for deletion (7 days)."
read -r -p "Type DELETE to continue: " ans
[ "$ans" = "DELETE" ] || die "cancelled (you typed '$ans'). Nothing was deleted."
FAILS=0

for tr in $TRAILS; do echo " - stopping CloudTrail logging on $tr"; aws cloudtrail stop-logging --name "$tr" 2>/dev/null || true; done
for S in $DEL_STACKS; do
  echo; echo "stack $S"
  aws cloudformation update-termination-protection --no-enable-termination-protection --stack-name "$S" >/dev/null 2>&1 || true
  for b in $(stack_res "$S" AWS::S3::Bucket); do bucket_exists "$b" && { echo " - emptying $b"; empty_bucket "$b" || FAILS=$((FAILS+1)); }; done
  echo " - deleting stack $S (1-15 minutes)..."
  aws cloudformation delete-stack --stack-name "$S"
  if aws cloudformation wait stack-delete-complete --stack-name "$S"; then echo "   stack $S deleted"
  else
    echo "   stack $S did NOT delete. Reason:"
    aws cloudformation describe-stack-events --stack-name "$S" \
      --query "StackEvents[?ResourceStatus=='DELETE_FAILED'].[LogicalResourceId,ResourceStatusReason]" --output text | head -5
    FAILS=$((FAILS+1))
  fi
done
for b in $STACK_BUCKETS; do bucket_exists "$b" && delete_bucket "$b"; done   # buckets a stack kept (Retain)
for b in $EXTRA_BUCKETS; do delete_bucket "$b"; done
for t in $EXTRA_TABLES; do delete_table "$t"; done

# ---------------------------------------------------------------------------------------------
step "3/3 Check + back to the team code"
echo "fs-* / finshield-* buckets left:"; aws s3api list-buckets --query 'Buckets[].Name' --output text | lines | grep -E '^(fs-|finshield-)' | sed 's/^/   /' || echo "   none"
echo "fs-* / finshield-* tables left:";  aws dynamodb list-tables --query 'TableNames' --output text | lines | grep -E '^(fs-|finshield-)' | sed 's/^/   /' || echo "   none"

if [ "$(git branch --show-current 2>/dev/null)" = "local/boilerplate" ]; then
  if [ -z "$(git status --porcelain --untracked-files=no)" ]; then
    git switch -q main && git pull -q --ff-only origin main && echo "git: switched back to main ($(git log --oneline -1))"
  else echo "git: you are on local/boilerplate with changes - run: git stash && git switch main && git pull"; fi
fi

if [ "$FAILS" -gt 0 ]; then die "$FAILS item(s) failed - send Claude the FAILED / Reason lines above"; fi
cat <<EOF

DONE - old buckets and tables are gone.
Next, follow the brief (deploys finshield-dev from infra/template.yaml):
   SKIP_PUSH=1 bash scripts/finish-infra.sh
Optional: git branch -D local/boilerplate      (the boilerplate test branch, laptop only)
EOF
