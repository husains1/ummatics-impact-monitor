#!/bin/bash

################################################################################
# Ummatics Impact Monitor - AWS Deployment Script
#
# This script automates the deployment of the Ummatics Impact Monitor
# to an AWS EC2 instance from WSL/Ubuntu console.
#
# Usage: ./deploy-to-aws.sh [EC2_IP_ADDRESS]
#
# Prerequisites:
# - AWS CLI configured with credentials
# - SSH key pair created (ummatics-monitor-key.pem)
# - EC2 instance running with Docker installed
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="ummatics-impact-monitor"
SSH_KEY="$HOME/.ssh/ummatics-monitor-key.pem"
REMOTE_USER="ubuntu"
REMOTE_DIR="/home/ubuntu/$PROJECT_NAME"

# Functions
print_header() {
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

# Check if IP address provided
if [ -z "$1" ]; then
    print_error "Error: EC2 IP address not provided"
    echo "Usage: $0 <EC2_IP_ADDRESS>"
    echo "Example: $0 54.123.45.67"
    exit 1
fi

EC2_IP="$1"

print_header "Ummatics Impact Monitor - AWS Deployment"
echo ""
print_info "Target EC2 Instance: $EC2_IP"
print_info "Remote Directory: $REMOTE_DIR"
echo ""

# Validate SSH key exists
print_info "Checking SSH key..."
if [ ! -f "$SSH_KEY" ]; then
    print_error "SSH key not found at $SSH_KEY"
    print_info "Create one with: aws ec2 create-key-pair --key-name ummatics-monitor-key"
    exit 1
fi
print_success "SSH key found"

# Test SSH connection
print_info "Testing SSH connection..."
if ! ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
    "$REMOTE_USER@$EC2_IP" "echo 'Connection successful'" &> /dev/null; then
    print_error "Cannot connect to EC2 instance"
    print_info "Make sure the instance is running and security group allows SSH from your IP"
    exit 1
fi
print_success "SSH connection successful"

# Check if Docker is installed on remote
print_info "Checking Docker installation on EC2..."
if ! ssh -i "$SSH_KEY" "$REMOTE_USER@$EC2_IP" "docker --version" &> /dev/null; then
    print_warning "Docker not found on EC2 instance"
    print_info "Installing Docker..."

    ssh -i "$SSH_KEY" "$REMOTE_USER@$EC2_IP" << 'EOF'
        sudo apt update
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        rm get-docker.sh
EOF

    print_success "Docker installed"
    print_warning "You may need to logout and login to EC2 for docker group changes to take effect"
else
    print_success "Docker already installed"
fi

# Create remote directory structure
print_info "Creating directory structure on EC2..."
ssh -i "$SSH_KEY" "$REMOTE_USER@$EC2_IP" << EOF
    mkdir -p $REMOTE_DIR/backend
    mkdir -p $REMOTE_DIR/frontend/src
    mkdir -p $REMOTE_DIR/credentials
EOF
print_success "Directory structure created"

# Transfer files to EC2
print_header "Transferring Files to EC2"

print_info "Transferring backend files..."
scp -i "$SSH_KEY" -r \
    backend/api.py \
    backend/ingestion.py \
    backend/scheduler.py \
    backend/requirements.txt \
    backend/Dockerfile \
    "$REMOTE_USER@$EC2_IP:$REMOTE_DIR/backend/" &> /dev/null
print_success "Backend files transferred"

print_info "Transferring frontend files..."
scp -i "$SSH_KEY" -r \
    frontend/src/ \
    frontend/package.json \
    frontend/vite.config.js \
    frontend/tailwind.config.js \
    frontend/postcss.config.js \
    frontend/index.html \
    frontend/Dockerfile \
    "$REMOTE_USER@$EC2_IP:$REMOTE_DIR/frontend/" &> /dev/null
print_success "Frontend files transferred"

print_info "Transferring configuration files..."
scp -i "$SSH_KEY" \
    docker-compose.yml \
    schema.sql \
    "$REMOTE_USER@$EC2_IP:$REMOTE_DIR/" &> /dev/null
print_success "Configuration files transferred"

print_info "Transferring credentials README..."
scp -i "$SSH_KEY" \
    credentials/README.md \
    "$REMOTE_USER@$EC2_IP:$REMOTE_DIR/credentials/" &> /dev/null
print_success "Credentials README transferred"

# Check if .env file exists locally and transfer
if [ -f ".env" ]; then
    print_info "Transferring .env file..."
    scp -i "$SSH_KEY" .env "$REMOTE_USER@$EC2_IP:$REMOTE_DIR/" &> /dev/null
    print_success ".env file transferred"
else
    print_warning ".env file not found locally - you'll need to create it on EC2"
fi

# Check if google credentials exist and transfer
if [ -f "credentials/google-credentials.json" ]; then
    print_info "Transferring Google credentials..."
    scp -i "$SSH_KEY" \
        credentials/google-credentials.json \
        "$REMOTE_USER@$EC2_IP:$REMOTE_DIR/credentials/" &> /dev/null
    print_success "Google credentials transferred"
else
    print_warning "Google credentials not found - you'll need to upload them manually"
fi

# Build and start Docker containers
print_header "Building and Starting Application"

ssh -i "$SSH_KEY" "$REMOTE_USER@$EC2_IP" << EOF
    cd $REMOTE_DIR

    echo "Stopping existing containers..."
    docker-compose down -v 2>/dev/null || true

    echo "Building Docker images..."
    docker-compose build

    echo "Starting containers..."
    docker-compose up -d

    echo "Waiting for services to be healthy..."
    sleep 30

    echo "Checking container status..."
    docker-compose ps
EOF

print_success "Application deployed and started"

# Run initial data ingestion
print_header "Initial Data Collection"

print_info "Running initial data ingestion..."
ssh -i "$SSH_KEY" "$REMOTE_USER@$EC2_IP" << EOF
    cd $REMOTE_DIR
    docker-compose exec -T api python ingestion.py || true
EOF

# Display deployment summary
print_header "Deployment Complete!"

echo ""
print_success "Application successfully deployed to AWS EC2"
echo ""
print_info "Access Points:"
echo "   Dashboard: http://$EC2_IP:3000"
echo "   API Health: http://$EC2_IP:5000/api/health"
echo ""
print_info "Useful Commands:"
echo "   SSH: ssh -i $SSH_KEY $REMOTE_USER@$EC2_IP"
echo "   View Logs: docker-compose logs -f"
echo "   Restart: docker-compose restart"
echo "   Stop: docker-compose down"
echo ""
print_info "Next Steps:"
echo "   1. Access dashboard: http://$EC2_IP:3000 (and http://$EC2_IP:5000/api/health)"
echo "   2. Migrate local data (if available): ./scripts/migrate_local_to_ec2_db.sh $EC2_IP $SSH_KEY"
echo "   3. Upload Google credentials if not already done"
echo "   4. Check logs: ssh -i $SSH_KEY $REMOTE_USER@$EC2_IP 'cd $REMOTE_DIR && docker-compose logs -f scheduler'"
echo "   5. For production: set up HTTPS with Let's Encrypt"
echo ""
print_warning "Security Reminder:"
echo "   - Change default passwords in .env file (DB_PASSWORD, DASHBOARD_PASSWORD)"
echo "   - Update security group rules to restrict access to your IP only (optional)"
echo "   - Consider setting API port (5000) to accessible only from your IP if not using frontend"
echo "   - Set up HTTPS with Let's Encrypt for production use"
echo "   - Monitor AWS Free Tier usage and costs"
echo ""

# Save deployment info
cat > deployment-info.txt << EOF
Deployment Information
======================
Date: $(date)
EC2 IP: $EC2_IP
Dashboard URL: http://$EC2_IP:3000
API Health URL: http://$EC2_IP:5000/api/health

SSH Command:
ssh -i $SSH_KEY $REMOTE_USER@$EC2_IP

Useful Commands on EC2:
cd $REMOTE_DIR
docker-compose ps              # Check status
docker-compose logs -f         # View logs
docker-compose restart         # Restart all services
docker-compose down            # Stop all services
docker-compose up -d --build   # Rebuild and start
docker-compose exec api python ingestion.py  # Manual data collection
EOF

print_success "Deployment info saved to deployment-info.txt"
echo ""
