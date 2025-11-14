#!/bin/bash

################################################################################
# Ummatics Impact Monitor - Complete AWS Setup Script
#
# This script automates the COMPLETE AWS infrastructure setup and deployment:
# 1. Creates EC2 key pair
# 2. Creates security group with proper rules
# 3. Launches EC2 instance (t2.micro - Free Tier)
# 4. Allocates and associates Elastic IP
# 5. Waits for instance to be ready
# 6. Installs Docker on EC2
# 7. Deploys application
#
# Usage: ./aws-setup-complete.sh
#
# Prerequisites:
# - AWS CLI v2 installed and configured (aws configure)
# - Active AWS account
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
KEY_NAME="ummatics-monitor-key"
KEY_PATH="$HOME/.ssh/${KEY_NAME}.pem"
SG_NAME="ummatics-monitor-sg"
INSTANCE_NAME="ummatics-monitor"
# You may override the instance type by setting the environment variable AWS_INSTANCE_TYPE
# If not set, the script will try to pick a Free Tier eligible instance in the region.
INSTANCE_TYPE="${AWS_INSTANCE_TYPE:-}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Main script
print_header "Ummatics Impact Monitor - AWS Complete Setup"
echo ""
print_info "This script will create all AWS resources and deploy the application"
print_info "Region: $REGION"
if [ -n "$INSTANCE_TYPE" ]; then
    print_info "Instance Type (requested): $INSTANCE_TYPE"
else
    print_info "Instance Type: not set (attempting to auto-detect a Free Tier eligible type)"
fi
echo ""

# Confirm to proceed
read -p "Do you want to proceed? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    print_warning "Setup cancelled by user"
    exit 0
fi

# Check AWS CLI
print_header "Step 1: Verifying Prerequisites"

print_info "Checking AWS CLI..."
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Please install it first."
    exit 1
fi
print_success "AWS CLI found: $(aws --version)"

print_info "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured. Run 'aws configure' first."
    exit 1
fi
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
print_success "AWS credentials valid (Account: $AWS_ACCOUNT_ID)"

# Step 2: Create Key Pair
print_header "Step 2: Creating SSH Key Pair"

if [ -f "$KEY_PATH" ]; then
    print_warning "Key pair already exists at $KEY_PATH"
    read -p "Do you want to use the existing key? (yes/no): " USE_EXISTING
    if [ "$USE_EXISTING" != "yes" ]; then
        print_error "Please remove or rename the existing key first"
        exit 1
    fi
    print_success "Using existing key pair"
else
    print_info "Creating new key pair: $KEY_NAME"
    aws ec2 create-key-pair \
        --key-name "$KEY_NAME" \
        --query 'KeyMaterial' \
        --output text > "$KEY_PATH"

    chmod 400 "$KEY_PATH"
    print_success "Key pair created: $KEY_PATH"
fi

# Step 3: Create Security Group
print_header "Step 3: Creating Security Group"

print_info "Getting default VPC..."
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text)

if [ "$VPC_ID" == "None" ] || [ -z "$VPC_ID" ]; then
    print_error "No default VPC found. Please create one first."
    exit 1
fi
print_success "Default VPC: $VPC_ID"

print_info "Checking if security group exists..."
EXISTING_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SG_NAME" \
    --query "SecurityGroups[0].GroupId" \
    --output text 2>/dev/null || echo "None")

if [ "$EXISTING_SG" != "None" ] && [ -n "$EXISTING_SG" ]; then
    print_warning "Security group already exists: $EXISTING_SG"
    SECURITY_GROUP_ID="$EXISTING_SG"
    print_success "Using existing security group"
else
    print_info "Creating security group..."
    SECURITY_GROUP_ID=$(aws ec2 create-security-group \
        --group-name "$SG_NAME" \
        --description "Security group for Ummatics Impact Monitor" \
        --vpc-id "$VPC_ID" \
        --query 'GroupId' \
        --output text)
    print_success "Security group created: $SECURITY_GROUP_ID"

    # Get current public IP
    print_info "Getting your public IP..."
    MY_IP=$(curl -s ifconfig.me)
    print_success "Your IP: $MY_IP"

    print_info "Configuring security group rules..."

    # SSH from your IP
    aws ec2 authorize-security-group-ingress \
        --group-id "$SECURITY_GROUP_ID" \
        --protocol tcp \
        --port 22 \
        --cidr "${MY_IP}/32" || true

    # HTTP from anywhere
    aws ec2 authorize-security-group-ingress \
        --group-id "$SECURITY_GROUP_ID" \
        --protocol tcp \
        --port 80 \
        --cidr 0.0.0.0/0 || true

    # Frontend (port 3000) from anywhere
    aws ec2 authorize-security-group-ingress \
        --group-id "$SECURITY_GROUP_ID" \
        --protocol tcp \
        --port 3000 \
        --cidr 0.0.0.0/0 || true

    # API (port 5000) from anywhere (needed for frontend to access)
    aws ec2 authorize-security-group-ingress \
        --group-id "$SECURITY_GROUP_ID" \
        --protocol tcp \
        --port 5000 \
        --cidr 0.0.0.0/0 || true

    print_success "Security group rules configured"
fi

# Step 4: Launch EC2 Instance
print_header "Step 4: Launching EC2 Instance"

print_info "Getting latest Ubuntu 22.04 AMI..."
AMI_ID=$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    --query "sort_by(Images, &CreationDate)[-1].ImageId" \
    --output text)
print_success "AMI ID: $AMI_ID"
    
# Determine instance type: prefer AWS_INSTANCE_TYPE, else try to detect a free-tier-eligible one,
# otherwise fall back to a sensible default.
DEFAULT_FALLBACK="t3.micro"
if [ -z "$INSTANCE_TYPE" ]; then
    print_info "Detecting a Free Tier eligible instance type for region $REGION..."
    # Query instance types that are marked free-tier-eligible and pick the first one.
    RAW_DETECTED=$(aws ec2 describe-instance-types \
        --filters Name=free-tier-eligible,Values=true \
        --query 'InstanceTypes[].InstanceType' \
        --output text 2>/dev/null || echo "")

    # Normalize whitespace (tabs/newlines) and pick the first non-empty token
    DETECTED=$(echo "$RAW_DETECTED" | tr -s '[:space:]' '\n' | grep -v '^$' | head -n1 || echo "")

    if [ -n "$DETECTED" ] && [ "$DETECTED" != "None" ]; then
        INSTANCE_TYPE="$DETECTED"
        print_success "Selected free-tier-eligible instance type: $INSTANCE_TYPE"
    else
        print_warning "Could not detect a free-tier-eligible instance type in this region/account."
        print_warning "Falling back to default instance type: $DEFAULT_FALLBACK"
        INSTANCE_TYPE="$DEFAULT_FALLBACK"
    fi
else
    print_info "Using requested instance type: $INSTANCE_TYPE"
fi

print_info "Launching EC2 instance ($INSTANCE_TYPE)..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SECURITY_GROUP_ID" \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

print_success "Instance launched: $INSTANCE_ID"
print_info "Waiting for instance to be running..."

aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
print_success "Instance is running"

# Step 5: Allocate and Associate Elastic IP
print_header "Step 5: Allocating Elastic IP"

print_info "Allocating Elastic IP..."
ALLOCATION_ID=$(aws ec2 allocate-address \
    --domain vpc \
    --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$INSTANCE_NAME-eip}]" \
    --query 'AllocationId' \
    --output text)
print_success "Elastic IP allocated: $ALLOCATION_ID"

print_info "Associating Elastic IP with instance..."
aws ec2 associate-address \
    --instance-id "$INSTANCE_ID" \
    --allocation-id "$ALLOCATION_ID" \
    > /dev/null

ELASTIC_IP=$(aws ec2 describe-addresses \
    --allocation-ids "$ALLOCATION_ID" \
    --query 'Addresses[0].PublicIp' \
    --output text)
print_success "Elastic IP associated: $ELASTIC_IP"

# Step 6: Wait for instance to be ready
print_header "Step 6: Waiting for Instance to be Ready"

print_info "Waiting for SSH to be available (this may take 2-3 minutes)..."
ATTEMPTS=0
MAX_ATTEMPTS=30
until ssh -i "$KEY_PATH" -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
    ubuntu@$ELASTIC_IP "echo 'SSH Ready'" &> /dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ $ATTEMPTS -ge $MAX_ATTEMPTS ]; then
        print_error "SSH connection timeout after $MAX_ATTEMPTS attempts"
        exit 1
    fi
    echo -n "."
    sleep 10
done
echo ""
print_success "SSH connection established"

# Step 7: Install Docker
print_header "Step 7: Installing Docker on EC2"

print_info "Installing Docker and Docker Compose..."
ssh -i "$KEY_PATH" ubuntu@$ELASTIC_IP << 'EOF'
    # Update system
    sudo apt update

    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu

    # Install Docker Compose
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

    # Cleanup
    rm get-docker.sh

    # Verify
    docker --version
    docker-compose --version
EOF

print_success "Docker and Docker Compose installed"

# Step 8: Deploy Application
print_header "Step 8: Deploying Application"

if [ ! -f "./deploy-to-aws.sh" ]; then
    print_error "deploy-to-aws.sh not found in current directory"
    print_warning "Please run this script from the ummatics-impact-monitor directory"
    exit 1
fi

print_info "Running deployment script..."
./deploy-to-aws.sh "$ELASTIC_IP"

# Summary
print_header "Setup Complete! 🎉"

echo ""
print_success "AWS infrastructure created and application deployed successfully!"
echo ""
print_info "Infrastructure Details:"
echo "   EC2 Instance ID: $INSTANCE_ID"
echo "   Instance Type: $INSTANCE_TYPE"
echo "   Elastic IP: $ELASTIC_IP"
echo "   Security Group: $SECURITY_GROUP_ID"
echo "   SSH Key: $KEY_PATH"
echo ""
print_info "Access Points:"
echo "   Dashboard: http://$ELASTIC_IP:3000"
echo "   API Health: http://$ELASTIC_IP:5000/api/health"
echo ""
print_info "SSH Access:"
echo "   ssh -i $KEY_PATH ubuntu@$ELASTIC_IP"
echo ""
print_warning "Important Next Steps:"
echo "   1. Access dashboard: http://$ELASTIC_IP:3000"
echo "   2. Migrate local data: ./scripts/migrate_local_to_ec2_db.sh $ELASTIC_IP $KEY_PATH"
echo "   3. Check scheduler logs: ssh -i $KEY_PATH ubuntu@$ELASTIC_IP 'cd ~/ummatics-impact-monitor && docker-compose logs -f scheduler'"
echo "   4. Upload Google credentials if needed: scp -i $KEY_PATH /path/to/credentials.json ubuntu@$ELASTIC_IP:~/ummatics-impact-monitor/credentials/"
echo "   5. SSH access: ssh -i $KEY_PATH ubuntu@$ELASTIC_IP"
echo ""
print_warning "Security Reminders:"
echo "   - Change default passwords in .env"
echo "   - Keep SSH key secure"
echo "   - Consider setting up HTTPS with Let's Encrypt"
echo "   - Monitor AWS Free Tier usage"
echo ""

# Save setup info
cat > aws-setup-info.txt << EOF
AWS Setup Information
=====================
Created: $(date)
Region: $REGION

Resources Created:
- EC2 Instance ID: $INSTANCE_ID
- Instance Type: $INSTANCE_TYPE
- Elastic IP: $ELASTIC_IP
- Allocation ID: $ALLOCATION_ID
- Security Group: $SECURITY_GROUP_ID
- SSH Key: $KEY_PATH

Access:
- Dashboard: http://$ELASTIC_IP:3000
- API Health: http://$ELASTIC_IP:5000/api/health
- SSH: ssh -i $KEY_PATH ubuntu@$ELASTIC_IP

Cleanup Commands (to remove all resources):
aws ec2 terminate-instances --instance-ids $INSTANCE_ID
aws ec2 release-address --allocation-id $ALLOCATION_ID
aws ec2 delete-security-group --group-id $SECURITY_GROUP_ID
aws ec2 delete-key-pair --key-name $KEY_NAME
rm $KEY_PATH

Monthly Cost: \$0.00 (Free Tier)
EOF

print_success "Setup info saved to aws-setup-info.txt"
print_success "Deployment info saved to deployment-info.txt"
echo ""
