# shared helpers (sourced)
set -euo pipefail
STAGE="${STAGE:-dev}"
REGION="${REGION:-ap-south-1}"
STACK="${STACK:-finshield-$STAGE}"
export AWS_DEFAULT_REGION="$REGION"
output() { # output <OutputKey>
  aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text
}
