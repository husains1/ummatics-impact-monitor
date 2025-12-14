#!/bin/bash
# Quick deployment script for Lambda sentiment analysis

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Lambda Sentiment Analysis - Quick Deploy                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Install with: pip install awscli"
    exit 1
fi
echo "✓ AWS CLI found"

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    echo "⚠️  SAM CLI not found. Installing..."
    pip install aws-sam-cli
fi
echo "✓ SAM CLI found"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi
echo "✓ Docker found"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Run: aws configure"
    exit 1
fi
echo "✓ AWS credentials configured"

echo ""
echo "All prerequisites met! Proceeding with deployment..."
echo ""

# Navigate to lambda directory
cd "$(dirname "$0")"

# Run deployment
./deploy.sh

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Deployment Complete!                                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Test the Lambda function:"
echo "   aws lambda invoke --function-name ummatics-sentiment-analysis \\"
echo "     --payload '{\"texts\":[\"I love this!\"]}' response.json"
echo ""
echo "2. Enable in backend (.env):"
echo "   USE_LAMBDA_SENTIMENT=1"
echo ""
echo "3. Rebuild backend:"
echo "   docker-compose build api && docker-compose up -d api"
echo ""
echo "4. Monitor costs:"
echo "   aws cloudwatch get-metric-statistics \\"
echo "     --namespace AWS/Lambda \\"
echo "     --metric-name Invocations \\"
echo "     --dimensions Name=FunctionName,Value=ummatics-sentiment-analysis \\"
echo "     --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%S)Z \\"
echo "     --end-time $(date -u +%Y-%m-%dT%H:%M:%S)Z \\"
echo "     --period 86400 \\"
echo "     --statistics Sum"
echo ""
