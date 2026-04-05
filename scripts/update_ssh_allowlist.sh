#!/usr/bin/env bash
set -euo pipefail

# Update EC2 security group SSH allowlist to include this machine's current public IP.
# Usage:
#   ./scripts/update_ssh_allowlist.sh
#   ./scripts/update_ssh_allowlist.sh --region us-east-1 --sg sg-xxxxxxxx --desc my-laptop
#   ./scripts/update_ssh_allowlist.sh --dry-run

REGION="us-east-1"
SECURITY_GROUP_ID="sg-0dc23ab5f639bc67d"
DESCRIPTION="tahir-current-ip"
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      REGION="$2"
      shift 2
      ;;
    --sg|--security-group)
      SECURITY_GROUP_ID="$2"
      shift 2
      ;;
    --desc|--description)
      DESCRIPTION="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    -h|--help)
      sed -n '1,18p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required but not found." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but not found." >&2
  exit 1
fi

CURRENT_IP="$(curl -s --max-time 8 https://checkip.amazonaws.com | tr -d '\n')"
if [[ -z "$CURRENT_IP" ]]; then
  echo "Failed to detect current public IP." >&2
  exit 1
fi

CURRENT_CIDR="${CURRENT_IP}/32"

echo "Region: $REGION"
echo "Security Group: $SECURITY_GROUP_ID"
echo "Current IP: $CURRENT_CIDR"

EXISTS="$({
  aws ec2 describe-security-groups \
    --region "$REGION" \
    --group-ids "$SECURITY_GROUP_ID" \
    --output json;
} | python3 -c '
import json
import sys

cidr = sys.argv[1]
data = json.load(sys.stdin)
for sg in data.get("SecurityGroups", []):
  for perm in sg.get("IpPermissions", []):
    if perm.get("IpProtocol") != "tcp":
      continue
    if perm.get("FromPort") != 22 or perm.get("ToPort") != 22:
      continue
    for rng in perm.get("IpRanges", []):
      if rng.get("CidrIp") == cidr:
        print("yes")
        raise SystemExit(0)
print("no")
' "$CURRENT_CIDR"
)"

if [[ "$EXISTS" == "yes" ]]; then
  echo "SSH rule already exists for $CURRENT_CIDR. No changes needed."
  exit 0
fi

echo "SSH rule for $CURRENT_CIDR is missing."
if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry run enabled. Would add ingress rule to $SECURITY_GROUP_ID (port 22)."
  exit 0
fi

aws ec2 authorize-security-group-ingress \
  --region "$REGION" \
  --group-id "$SECURITY_GROUP_ID" \
  --ip-permissions "[{\"IpProtocol\":\"tcp\",\"FromPort\":22,\"ToPort\":22,\"IpRanges\":[{\"CidrIp\":\"$CURRENT_CIDR\",\"Description\":\"$DESCRIPTION\"}]}]" \
  >/dev/null

echo "Added SSH ingress rule for $CURRENT_CIDR to $SECURITY_GROUP_ID."
