#!/usr/bin/env bash
# Upload the synthetic KYC images to the KYC bucket and tag each one sample=true.
#   python3 simulator/seed/make_kyc_docs.py      # makes simulator/seed/kyc-docs/ (200 PNGs + manifest.csv)
#   ./scripts/upload-kyc-docs.sh                  # uploads them
#   ./scripts/upload-kyc-docs.sh --dryrun         # shows what would be uploaded
# Keys land at kyc/<customer_id>/KYC-<DOC>-<customer_id>.png (the backend parses this).
# Env: KYC_BUCKET (default finshield-dev-kyc-docs), AWS_DEFAULT_REGION (default ap-south-1).
set -euo pipefail
cd "$(dirname "$0")/.."

BUCKET="${KYC_BUCKET:-finshield-dev-kyc-docs}"
REGION="${AWS_DEFAULT_REGION:-ap-south-1}"
SRC="simulator/seed/kyc-docs"
MANIFEST="$SRC/manifest.csv"
DRYRUN="${1:-}"

[ -f "$MANIFEST" ] || { echo "No $MANIFEST. Run: python3 simulator/seed/make_kyc_docs.py"; exit 1; }
count=$(find "$SRC" -name 'KYC-*.png' | wc -l | tr -d ' ')
echo "Uploading $count images from $SRC to s3://$BUCKET/kyc/ ($REGION)"

aws s3 sync "$SRC/" "s3://$BUCKET/kyc/" --region "$REGION" \
  --exclude "*" --include "C-*/KYC-*.png" --content-type image/png ${DRYRUN:+--dryrun}

if [ "$DRYRUN" = "--dryrun" ]; then
  echo "Dry run: no tags written."
  exit 0
fi

# aws s3 sync cannot set tags, so tag every key listed in the manifest (column 4 = s3_key).
tagged=0
while IFS=, read -r _file_id _cust _doc s3_key _rest; do
  aws s3api put-object-tagging --bucket "$BUCKET" --key "$s3_key" --region "$REGION" \
    --tagging 'TagSet=[{Key=sample,Value=true},{Key=project,Value=finshield}]'
  tagged=$((tagged + 1))
  if [ $((tagged % 50)) -eq 0 ]; then echo "  tagged $tagged"; fi
done < <(tail -n +2 "$MANIFEST" | tr -d '\r')

echo "Done: $tagged objects tagged sample=true in s3://$BUCKET/kyc/"
