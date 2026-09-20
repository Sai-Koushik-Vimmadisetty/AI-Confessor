#!/usr/bin/env bash
# AI Confessor — EC2 + docker-compose deployment.
#
# *** NOT TESTED — prepared without AWS credentials. Review before running. ***
#
# Provisions a single EC2 instance, installs Docker, copies this project over,
# and starts it with docker compose. Good for demos and small-scale use.
# For production scale-out, prefer ECS Fargate / an ALB in front of N instances.
#
# Prerequisites: AWS CLI configured (aws configure), an EC2 key pair, and a
# .env file with OPENAI_API_KEY set (or intentionally left empty for MOCK mode).
#
# Usage:
#   ./aws/deploy-ec2.sh --key-name my-key --key-path ~/.ssh/my-key.pem [--region us-east-1] [--instance-type t3.medium]

set -euo pipefail

REGION="us-east-1"
INSTANCE_TYPE="t3.medium"
KEY_NAME=""
KEY_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --key-name) KEY_NAME="$2"; shift 2 ;;
    --key-path) KEY_PATH="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --instance-type) INSTANCE_TYPE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

[[ -z "$KEY_NAME" || -z "$KEY_PATH" ]] && {
  echo "ERROR: --key-name and --key-path are required."; exit 1; }
[[ -f .env ]] || { echo "ERROR: .env not found at project root."; exit 1; }

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SG_NAME="ai-confessor-sg"

echo "==> Creating security group..."
SG_ID=$(aws ec2 create-security-group \
  --group-name "$SG_NAME" --description "AI Confessor" \
  --region "$REGION" --query 'GroupId' --output text 2>/dev/null \
  || aws ec2 describe-security-groups --group-names "$SG_NAME" \
       --region "$REGION" --query 'SecurityGroups[0].GroupId' --output text)

for port in 22 3000 8000; do
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --protocol tcp --port "$port" --cidr 0.0.0.0/0 --region "$REGION" 2>/dev/null || true
done

echo "==> Finding Ubuntu 24.04 AMI..."
AMI=$(aws ec2 describe-images --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --region "$REGION" --output text)

echo "==> Launching $INSTANCE_TYPE..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI" --instance-type "$INSTANCE_TYPE" --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30}}]' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ai-confessor}]" \
  --region "$REGION" --query 'Instances[0].InstanceId' --output text)

aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --region "$REGION" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "==> Instance $INSTANCE_ID running at $PUBLIC_IP"

echo "==> Installing Docker (waiting for SSH)..."
sleep 20
ssh -o StrictHostKeyChecking=no -i "$KEY_PATH" "ubuntu@$PUBLIC_IP" <<'EOF'
set -e
sudo apt-get update -qq
sudo apt-get install -y -qq docker.io docker-compose-plugin
sudo usermod -aG docker ubuntu
EOF

echo "==> Copying project..."
scp -o StrictHostKeyChecking=no -i "$KEY_PATH" -r \
  "$PROJECT_DIR/backend" "$PROJECT_DIR/frontend" \
  "$PROJECT_DIR/docker-compose.yml" "$PROJECT_DIR/.env" \
  "ubuntu@$PUBLIC_IP:~/ai-confessor/"

echo "==> Starting services..."
ssh -o StrictHostKeyChecking=no -i "$KEY_PATH" "ubuntu@$PUBLIC_IP" \
  "cd ~/ai-confessor && sudo docker compose up -d --build"

echo ""
echo "Done. App should be live shortly at: http://$PUBLIC_IP:3000"
echo "Tear down with: aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION"
