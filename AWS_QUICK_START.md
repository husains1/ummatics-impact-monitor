# AWS Quick Start Guide - Ummatics Impact Monitor

## 🚀 One-Command Deployment

Deploy the entire application to AWS in minutes!

### Prerequisites

1. **AWS Account** with Free Tier eligibility
2. **AWS CLI v2** installed and configured
3. **WSL/Ubuntu** terminal

### Install AWS CLI (if needed)

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

### Configure AWS Credentials

```bash
aws configure
# Enter:
# - AWS Access Key ID: your-access-key
# - AWS Secret Access Key: your-secret-key
# - Default region: us-east-1 (or preferred)
# - Default output format: json
```

## 🎯 Complete Setup (Recommended)

This script does EVERYTHING automatically:
- Creates EC2 key pair
- Sets up security group
- Launches EC2 instance
- Allocates Elastic IP
- Installs Docker
- Deploys application

```bash
cd ~/ummatics-impact-monitor
./aws-setup-complete.sh
```

**Time:** ~5-10 minutes
**Cost:** $0.00 (Free Tier)

After completion:
1. Dashboard will be at: `http://YOUR_ELASTIC_IP:3000`
2. SSH access: `ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@YOUR_ELASTIC_IP`

## 🔧 Manual Deployment (If EC2 Already Exists)

If you already have an EC2 instance running with Docker:

```bash
cd ~/ummatics-impact-monitor
./deploy-to-aws.sh YOUR_EC2_IP
```

## 📝 Post-Deployment Configuration

### 1. SSH to Your Instance

```bash
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@YOUR_ELASTIC_IP
```

### 2. Configure Environment Variables

```bash
cd ~/ummatics-impact-monitor
nano .env
```

Add your API credentials:

```env
# Database
DB_NAME=ummatics_monitor
DB_USER=postgres
DB_PASSWORD=change_this_password

# Dashboard
DASHBOARD_PASSWORD=change_this_password

# API Keys
GOOGLE_ALERTS_RSS_URL=your_rss_url
TWITTER_BEARER_TOKEN=your_twitter_token
CONTACT_EMAIL=contact@ummatics.org
```

Save and exit (`Ctrl+X`, `Y`, `Enter`)

### 3. Upload Google Credentials (from local machine)

```bash
# On your local WSL/Ubuntu
scp -i ~/.ssh/ummatics-monitor-key.pem \
    /path/to/google-credentials.json \
    ubuntu@YOUR_ELASTIC_IP:~/ummatics-impact-monitor/credentials/
```

### 4. Restart and Collect Data

```bash
# On EC2 instance
cd ~/ummatics-impact-monitor
docker-compose restart
docker-compose exec api python ingestion.py
```

### 5. Access Dashboard

Open browser: `http://YOUR_ELASTIC_IP:3000`

## 🛠️ Common Operations

### View Application Status

```bash
docker-compose ps
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f scheduler
```

### Manual Data Collection

```bash
docker-compose exec api python ingestion.py
```

### Restart Services

```bash
# All services
docker-compose restart

# Specific service
docker-compose restart api
```

### Update Application

```bash
cd ~/ummatics-impact-monitor
git pull
docker-compose down
docker-compose up -d --build
```

### Backup Database

```bash
docker-compose exec db pg_dump -U postgres ummatics_monitor > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
cat backup_20250112.sql | docker-compose exec -T db psql -U postgres ummatics_monitor
```

## 💰 Cost Management

### Resources Used (All Free Tier)

| Resource | Free Tier | Your Usage |
|----------|-----------|------------|
| EC2 t2.micro | 750 hrs/month | 720 hrs/month (24/7) |
| EBS Storage | 30 GB | ~15-20 GB |
| Data Transfer | 100 GB out | <5 GB typical |
| Elastic IP | Free when attached | 1 IP |

**Monthly Cost: $0.00** ✅

### Monitor Usage

```bash
# Check current month usage
aws ce get-cost-and-usage \
    --time-period Start=2025-01-01,End=2025-01-31 \
    --granularity MONTHLY \
    --metrics BlendedCost
```

### Set Up Billing Alarm

```bash
# Alert if costs exceed $1
aws cloudwatch put-metric-alarm \
    --alarm-name billing-alarm \
    --alarm-description "Alert if costs exceed $1" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 21600 \
    --evaluation-periods 1 \
    --threshold 1.0 \
    --comparison-operator GreaterThanThreshold
```

## 🔒 Security Best Practices

### 1. Change Default Passwords

```bash
# On EC2, edit .env and change:
nano ~/ummatics-impact-monitor/.env
# - DB_PASSWORD
# - DASHBOARD_PASSWORD
```

### 2. Restrict SSH Access

```bash
# Get your current IP
MY_IP=$(curl -s ifconfig.me)

# Update security group (replace SG_ID)
aws ec2 authorize-security-group-ingress \
    --group-id YOUR_SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr ${MY_IP}/32
```

### 3. Enable HTTPS (Optional)

```bash
# Install Certbot on EC2
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com
```

### 4. Keep System Updated

```bash
# On EC2
sudo apt update && sudo apt upgrade -y
```

## 🗑️ Cleanup Resources

To remove everything and stop charges:

```bash
# Get values from aws-setup-info.txt
INSTANCE_ID="i-xxxxxxxxxxxxx"
ALLOCATION_ID="eipalloc-xxxxxxxxxxxxx"
SECURITY_GROUP_ID="sg-xxxxxxxxxxxxx"

# Terminate instance
aws ec2 terminate-instances --instance-ids $INSTANCE_ID

# Wait for termination
aws ec2 wait instance-terminated --instance-ids $INSTANCE_ID

# Release Elastic IP
aws ec2 release-address --allocation-id $ALLOCATION_ID

# Delete security group
aws ec2 delete-security-group --group-id $SECURITY_GROUP_ID

# Delete key pair
aws ec2 delete-key-pair --key-name ummatics-monitor-key
rm ~/.ssh/ummatics-monitor-key.pem
```

## 📊 Monitoring

### CloudWatch Logs (Optional)

```bash
# View CloudWatch logs
aws logs tail /aws/ec2/ummatics-monitor --follow
```

### Health Check

```bash
# Check API health
curl http://YOUR_ELASTIC_IP:5000/api/health

# Expected response:
# {"status":"healthy","timestamp":"2025-01-12T10:30:00.123456"}
```

## 🐛 Troubleshooting

### Can't Connect to EC2

```bash
# Check instance status
aws ec2 describe-instances --instance-ids INSTANCE_ID

# Check security group
aws ec2 describe-security-groups --group-ids SG_ID

# Update your IP in security group
MY_IP=$(curl -s ifconfig.me)
aws ec2 authorize-security-group-ingress \
    --group-id SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr ${MY_IP}/32
```

### Dashboard Not Loading

```bash
# On EC2, check containers
docker-compose ps

# Check logs
docker-compose logs frontend

# Restart if needed
docker-compose restart frontend
```

### Database Connection Error

```bash
# Check database container
docker-compose logs db

# Restart database
docker-compose restart db

# Wait 30 seconds, then restart API
sleep 30
docker-compose restart api
```

### No Data Showing

```bash
# Run manual ingestion
docker-compose exec api python ingestion.py

# Check logs for errors
docker-compose logs api | grep ERROR

# Verify API keys in .env
cat .env
```

## 📚 Additional Resources

- **Full Documentation:** [AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Project README:** [README.md](README.md)
- **AWS Free Tier:** https://aws.amazon.com/free/
- **EC2 Docs:** https://docs.aws.amazon.com/ec2/
- **Docker Docs:** https://docs.docker.com/

## 🆘 Support

### Common Issues

1. **Rate Limits:** Twitter API has rate limits. Data ingestion runs daily at 9 AM.
2. **Credentials:** Ensure all API keys are valid and have proper permissions.
3. **Memory:** t2.micro has 1GB RAM. Monitor with `docker stats`.

### Get Help

1. Check logs: `docker-compose logs -f`
2. Review [AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md)
3. Check AWS console for any alerts

---

**Quick Start Version:** 1.0.0
**Last Updated:** January 12, 2025
**Deployment Time:** ~5-10 minutes
**Monthly Cost:** $0.00 (Free Tier) ✅
