# AWS Deployment Guide - Ummatics Impact Monitor

## Overview

This guide provides a complete deployment plan for running the Ummatics Impact Monitor on AWS using **Free Tier eligible resources** and automated deployment from WSL/Ubuntu console.

## Architecture on AWS

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS ROUTE 53 (Optional)                       │
│                      DNS Management                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   APPLICATION LOAD BALANCER                      │
│                    (Optional - Not Free Tier)                    │
│                  OR Elastic IP (Free Tier)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EC2 INSTANCE (t2.micro)                     │
│                      Ubuntu 22.04 LTS                            │
│                      750 hours/month FREE                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Docker Engine                                          │  │
│  │  • Docker Compose                                         │  │
│  │  • 4 Containers:                                          │  │
│  │    - PostgreSQL (db)                                      │  │
│  │    - Flask API (backend)                                  │  │
│  │    - React Frontend (frontend)                            │  │
│  │    - APScheduler (scheduler)                              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Security Group:                                                 │
│  • Port 22 (SSH)                                                 │
│  • Port 80 (HTTP)                                                │
│  • Port 443 (HTTPS - optional)                                   │
│  • Port 3000 (Frontend)                                          │
│  • Port 5000 (API - optional, for debugging)                     │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EBS VOLUME (30 GB SSD)                        │
│                    30 GB/month FREE                              │
│  • OS and Application Files                                      │
│  • PostgreSQL Data                                               │
│  • Docker Volumes                                                │
└─────────────────────────────────────────────────────────────────┘
```

## AWS Free Tier Resources Used

| Service | Free Tier Limit | Usage |
|---------|----------------|-------|
| **EC2 (t2.micro)** | 750 hours/month | 1 instance running 24/7 |
| **EBS Storage** | 30 GB General Purpose SSD | ~15-20 GB used |
| **Data Transfer** | 100 GB outbound/month | Low usage expected |
| **Elastic IP** | 1 free (when attached) | 1 for static IP |
| **S3** | 5 GB storage | Optional for backups |
| **CloudWatch** | 10 custom metrics, 5 GB logs | Basic monitoring |

**Estimated Monthly Cost:** $0.00 (within Free Tier)

## Prerequisites

### On Your Local Machine (WSL/Ubuntu)
- AWS CLI v2 installed
- SSH client
- AWS account with IAM credentials

### AWS Account Setup
1. Active AWS account
2. IAM user with permissions:
   - EC2FullAccess
   - VPCFullAccess
   - CloudWatchLogsFullAccess (optional)

## Step-by-Step Deployment

### Phase 1: AWS Infrastructure Setup

#### 1. Configure AWS CLI

```bash
# Install AWS CLI (if not already installed)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS credentials
aws configure
# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: us-east-1 (or your preferred region)
# - Default output format: json
```

#### 2. Create SSH Key Pair

```bash
# Create key pair for EC2 access
aws ec2 create-key-pair \
    --key-name ummatics-monitor-key \
    --query 'KeyMaterial' \
    --output text > ~/.ssh/ummatics-monitor-key.pem

# Set correct permissions
chmod 400 ~/.ssh/ummatics-monitor-key.pem
```

#### 3. Create Security Group

```bash
# Get your default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text)

# Create security group
SECURITY_GROUP_ID=$(aws ec2 create-security-group \
    --group-name ummatics-monitor-sg \
    --description "Security group for Ummatics Impact Monitor" \
    --vpc-id $VPC_ID \
    --query 'GroupId' \
    --output text)

# Allow SSH from your IP
MY_IP=$(curl -s ifconfig.me)
aws ec2 authorize-security-group-ingress \
    --group-id $SECURITY_GROUP_ID \
    --protocol tcp \
    --port 22 \
    --cidr ${MY_IP}/32

# Allow HTTP (port 80)
aws ec2 authorize-security-group-ingress \
    --group-id $SECURITY_GROUP_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0

# Allow Frontend access (port 3000)
aws ec2 authorize-security-group-ingress \
    --group-id $SECURITY_GROUP_ID \
    --protocol tcp \
    --port 3000 \
    --cidr 0.0.0.0/0

# Optional: Allow API access (port 5000) - for debugging only
aws ec2 authorize-security-group-ingress \
    --group-id $SECURITY_GROUP_ID \
    --protocol tcp \
    --port 5000 \
    --cidr ${MY_IP}/32
```

#### 4. Launch EC2 Instance

```bash
# Get the latest Ubuntu 22.04 AMI ID
AMI_ID=$(aws ec2 describe-images \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    --query "sort_by(Images, &CreationDate)[-1].ImageId" \
    --output text)

# Launch EC2 instance (t2.micro - Free Tier)
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type t2.micro \
    --key-name ummatics-monitor-key \
    --security-group-ids $SECURITY_GROUP_ID \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ummatics-monitor}]' \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "Instance ID: $INSTANCE_ID"

# Wait for instance to be running
aws ec2 wait instance-running --instance-ids $INSTANCE_ID

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "Public IP: $PUBLIC_IP"
```

#### 5. Allocate Elastic IP (Optional but Recommended)

```bash
# Allocate Elastic IP
ALLOCATION_ID=$(aws ec2 allocate-address \
    --domain vpc \
    --query 'AllocationId' \
    --output text)

# Associate with instance
aws ec2 associate-address \
    --instance-id $INSTANCE_ID \
    --allocation-id $ALLOCATION_ID

# Get Elastic IP
ELASTIC_IP=$(aws ec2 describe-addresses \
    --allocation-ids $ALLOCATION_ID \
    --query 'Addresses[0].PublicIp' \
    --output text)

echo "Elastic IP: $ELASTIC_IP"
```

### Phase 2: Application Deployment

#### 6. Connect to EC2 Instance

```bash
# SSH into the instance (wait 2-3 minutes after launch)
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@$ELASTIC_IP
```

#### 7. Install Docker and Docker Compose on EC2

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# Logout and login again to apply docker group changes
exit
```

#### 8. Deploy Application from Local Machine

Create the automated deployment script:

```bash
# On your local WSL/Ubuntu machine
# This will create the deploy-to-aws.sh script
```

#### 9. Run Deployment Script

```bash
# Make the script executable
chmod +x deploy-to-aws.sh

# Run deployment
./deploy-to-aws.sh $ELASTIC_IP
```

### Phase 3: Post-Deployment Configuration

#### 10. Configure Environment Variables on EC2

```bash
# SSH back into EC2
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@$ELASTIC_IP

# Navigate to application directory
cd ~/ummatics-impact-monitor

# Create .env file
nano .env
```

Add your credentials:
```env
# Database Configuration
DB_NAME=ummatics_monitor
DB_USER=postgres
DB_PASSWORD=your_secure_password_here

# Dashboard Authentication
DASHBOARD_PASSWORD=your_dashboard_password_here

# API Keys
GOOGLE_ALERTS_RSS_URL=your_google_alerts_rss_url
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
GA4_PROPERTY_ID=your_ga4_property_id
CONTACT_EMAIL=contact@ummatics.org
```

#### 11. Upload Google Credentials

```bash
# From your local machine, copy Google credentials
scp -i ~/.ssh/ummatics-monitor-key.pem \
    /path/to/google-credentials.json \
    ubuntu@$ELASTIC_IP:~/ummatics-impact-monitor/credentials/
```

#### 12. Start Application

```bash
# On EC2 instance
cd ~/ummatics-impact-monitor

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

#### 13. Initialize Database and Run First Ingestion

```bash
# Wait for services to be healthy (about 30 seconds)
sleep 30

# Run initial data ingestion
docker-compose exec api python ingestion.py

# Check logs
docker-compose logs api | tail -50
```

### Phase 4: Access and Verification

#### 14. Access the Dashboard

```bash
# Open in browser
echo "Dashboard URL: http://$ELASTIC_IP:3000"
```

#### 15. Set Up Monitoring (Optional)

```bash
# Install CloudWatch agent on EC2
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Create CloudWatch config
sudo nano /opt/aws/amazon-cloudwatch-agent/etc/config.json
```

## Automated Deployment Script

The `deploy-to-aws.sh` script automates the deployment process. See the script file for details.

## Maintenance and Operations

### Daily Operations

```bash
# Check application status
docker-compose ps

# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Update application
cd ~/ummatics-impact-monitor
git pull
docker-compose down
docker-compose up -d --build
```

### Backup Database

```bash
# Backup PostgreSQL database
docker-compose exec db pg_dump -U postgres ummatics_monitor > backup_$(date +%Y%m%d).sql

# Upload to S3 (optional)
aws s3 cp backup_$(date +%Y%m%d).sql s3://your-backup-bucket/
```

### Restore Database

```bash
# Restore from backup
cat backup_20250112.sql | docker-compose exec -T db psql -U postgres ummatics_monitor
```

## Cost Optimization Tips

1. **Use t2.micro exclusively** - Stays within Free Tier
2. **Keep Elastic IP attached** - No charges when attached to running instance
3. **Monitor data transfer** - Stay under 100 GB/month
4. **Use S3 Standard-IA for old backups** - Cheaper storage
5. **Set up billing alarms** - Alert if costs exceed $1

## Troubleshooting

### Cannot Connect to EC2

```bash
# Check instance status
aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].State.Name'

# Check security group rules
aws ec2 describe-security-groups --group-ids $SECURITY_GROUP_ID
```

### Docker Issues

```bash
# Check Docker service
sudo systemctl status docker

# Restart Docker
sudo systemctl restart docker

# Clean up Docker resources
docker system prune -a
```

### Application Not Accessible

```bash
# Check firewall
sudo ufw status

# Check Docker containers
docker-compose ps

# Check logs for errors
docker-compose logs --tail=100
```

## Security Best Practices

1. **Change default passwords** in .env file
2. **Restrict SSH access** to your IP only
3. **Enable HTTPS** with Let's Encrypt (optional)
4. **Regular updates**: `sudo apt update && sudo apt upgrade`
5. **Use AWS Secrets Manager** for sensitive credentials (optional)
6. **Enable CloudTrail** for audit logging
7. **Set up AWS Backup** for automated EBS snapshots

## Scaling Beyond Free Tier

When your needs grow:

1. **Upgrade to t3.small or t3.medium**
2. **Add RDS PostgreSQL** - managed database
3. **Use Application Load Balancer** - better availability
4. **Add Auto Scaling** - handle traffic spikes
5. **Use ElastiCache** - caching layer
6. **CloudFront CDN** - faster frontend delivery

## Clean Up Resources

To avoid charges after testing:

```bash
# Stop and remove containers
docker-compose down -v

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids $INSTANCE_ID

# Release Elastic IP
aws ec2 release-address --allocation-id $ALLOCATION_ID

# Delete security group (after instance terminates)
aws ec2 delete-security-group --group-id $SECURITY_GROUP_ID

# Delete key pair
aws ec2 delete-key-pair --key-name ummatics-monitor-key
rm ~/.ssh/ummatics-monitor-key.pem
```

## Support and Documentation

- AWS Free Tier: https://aws.amazon.com/free/
- EC2 Documentation: https://docs.aws.amazon.com/ec2/
- Docker Documentation: https://docs.docker.com/

---

**Version:** 1.0.0
**Last Updated:** January 12, 2025
**Status:** Production Ready ✅
