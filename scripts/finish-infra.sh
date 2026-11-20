#!/usr/bin/env bash
# scripts/finish-infra.sh - finish the git sync and deploy the team stack (finshield-dev) safely.
#   1. finish the paused rebase (keeps the team's deletion of README_AWS.md)
#   2. apply boilerplate-additions.patch (demo user sts:AssumeRole, emergency tag, outputs)
#   3. push to GitHub
#   4. set up .venv with SAM (needs Python 3.12)
#   5. sandbox check + bucket-name check
#   6. make validate, then make deploy (asks before deploying)
#   7. make env + make seed
# fs-infra is never touched. Stops at the first problem and tells you what to send.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AWS_PAGER=""
REGION="${REGION:-ap-south-1}"
EMAIL="${ALERT_EMAIL:-ajay.jha@globalnodes.ai}"
MODEL="${MODEL_ID:-global.anthropic.claude-haiku-5-5}"
STACK="finshield-dev"

step() { echo; echo "==== $*"; }
die()  { echo; echo "STOPPED: $*"; exit 1; }

# ------------------------------------------------------------------ 1. git rebase
step "1/7 Finish the paused git rebase"
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  if git status --porcelain | grep -qE '^(DU|UD|AU|UA|UU) README_AWS.md'; then
    git rm -q README_AWS.md && echo "kept the team's deletion of README_AWS.md"
  fi
  left="$(git diff --name-only --diff-filter=U)"
  [ -n "$left" ] && die "other conflicts left: $left (send this to Claude; undo with: git rebase --abort)"
  GIT_EDITOR=true git rebase --continue || die "git rebase --continue failed (undo with: git rebase --abort)"
else
  echo "no rebase in progress"
fi

# ------------------------------------------------------------------ 2. patch
step "2/7 Apply boilerplate additions"
if grep -q "Resource: !GetAtt DemoOpsAdminRole.Arn }" infra/template.yaml && grep -q "DemoKycUserName:" infra/template.yaml; then
  echo "already applied"
  rm -f boilerplate-additions.patch
elif [ -f boilerplate-additions.patch ]; then
  if git am boilerplate-additions.patch; then
    rm -f boilerplate-additions.patch
  else
    git am --abort
    die "patch did not apply to the newest team template (send this to Claude)"
  fi
else
  die "boilerplate-additions.patch not found"
fi

# ------------------------------------------------------------------ 3. push
step "3/7 Push to GitHub"
if [ "${SKIP_PUSH:-0}" = "1" ]; then
  echo "SKIP_PUSH=1 -> not pushing. Push later with: git push origin main"
elif ! git push origin main; then
  echo "push rejected - pulling the newest team commits once and retrying"
  git pull --rebase origin main || die "pull failed (conflict?) - undo with: git rebase --abort"
  git push origin main || die "push failed (check your GitHub login / collaborator access)"
fi
git log --oneline -4

# ------------------------------------------------------------------ 4. tools
step "4/7 Python 3.12 + SAM in .venv"
pyver() { "$1" -c 'import sys;print("%d.%d" % sys.version_info[:2])' 2>/dev/null; }
venv_ok() { [ -x .venv/bin/python ] && [ "$(pyver .venv/bin/python)" = "3.12" ]; }
UV="$(command -v uv 2>/dev/null || true)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
if ! venv_ok; then
  rm -rf .venv
  if [ "$(pyver python3)" = "3.12" ]; then
    python3 -m venv .venv || die "could not create .venv"
  elif command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m venv .venv || die "could not create .venv (try: sudo apt install -y python3.12-venv)"
  elif [ -n "$UV" ]; then
    echo "using uv to get Python 3.12 (no apt needed)"
    "$UV" python install 3.12 || die "uv could not download Python 3.12"
    "$UV" venv --seed --python 3.12 .venv || die "uv could not create .venv"
  else
    die "Python 3.12 not found. Pick ONE, then run this script again:
   (a) sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt update && sudo apt install -y python3.12 python3.12-venv
   (b) curl -LsSf https://astral.sh/uv/install.sh | sh      (no sudo, no apt)"
  fi
fi
venv_ok || die "could not create a Python 3.12 .venv"
if [ ! -x .venv/bin/sam ]; then
  .venv/bin/python -m pip install -q --upgrade pip aws-sam-cli || die "could not install SAM CLI"
fi
export PATH="$PWD/.venv/bin:$PATH"     # so 'sam build' finds python3.12
.venv/bin/sam --version

# ------------------------------------------------------------------ 5. checks
step "5/7 AWS login, sandbox check, bucket names"
aws sts get-caller-identity --query Arn --output text || die "not logged in to AWS (run aws configure)"
[ "$(aws configure get region)" = "$REGION" ] || echo "note: your CLI region is not $REGION; the Makefile uses $REGION"
bash scripts/sandbox-check.sh "$MODEL" | tee sandbox-check.txt

status="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo NONE)"
echo "stack $STACK: $status"
case "$status" in
  ROLLBACK_COMPLETE|ROLLBACK_FAILED|DELETE_FAILED)
    die "stack is in $status. Delete it first: aws cloudformation delete-stack --stack-name $STACK --region $REGION ; then run this script again" ;;
  *_IN_PROGRESS) die "stack is busy ($status). Wait a minute and run again" ;;
esac

TAKEN=0
for b in kyc-docs raw-events rules evidence web external-sim; do
  name="finshield-dev-$b"
  out="$(aws s3api head-bucket --bucket "$name" 2>&1)"; rc=$?
  if [ $rc -eq 0 ]; then
    if [ "$status" = "NONE" ]; then
      echo "$name: exists in THIS account but no stack -> left over from a failed deploy"
      echo "   delete it if empty: aws s3 rb s3://$name"; TAKEN=1
    else echo "$name: ours (stack exists)"; fi
  elif grep -qE "404|Not Found" <<<"$out"; then echo "$name: free"
  else echo "$name: TAKEN by another AWS account"; TAKEN=1
  fi
done
[ "$TAKEN" = 1 ] && die "fix the bucket names above first (taken names: tell Keshav before renaming)"

# ------------------------------------------------------------------ 6. validate + deploy
step "6/7 make validate + make deploy"
make validate || die "make validate failed (send the error to Claude)"
echo
echo "Ready to deploy stack $STACK in $REGION (MODE=DRY_RUN, MODEL_ID=$MODEL, ALERT_EMAIL=$EMAIL)."
echo "This only CREATES new finshield-dev resources. fs-infra is not touched."
echo "Note: finshield-dev-evidence uses Object Lock COMPLIANCE 365 days (intended) - never put test files in it."
read -r -p "Deploy now? [y/N] " ans
[ "$ans" = "y" ] || [ "$ans" = "Y" ] || die "deploy skipped by you"
if ! make deploy ALERT_EMAIL="$EMAIL" MODE=DRY_RUN MODEL_ID="$MODEL"; then
  echo
  echo "First failure:"
  aws cloudformation describe-stack-events --stack-name "$STACK" --region "$REGION" \
    --query "StackEvents[?ResourceStatus=='CREATE_FAILED']|[-1].[LogicalResourceId,ResourceStatusReason]" --output text
  die "deploy failed - send the line above to Claude"
fi

# ------------------------------------------------------------------ 7. after deploy
step "7/7 Outputs, env, seed"
aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table
make env  || echo "make env failed - run it again later"
make seed || echo "make seed failed - run it again later"
echo
echo "DONE. Now: 1) confirm the SNS email  2) DM web/.env.local values to Gaurav (never commit it)"
echo "      3) smoke test: see the put-events command in the brief, then: make logs FN=normalizer"
