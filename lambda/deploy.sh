#!/bin/bash
# Deploy sentiment analysis Lambda to AWS

set -e

echo "=== Deploying Sentiment Analysis Lambda ==="

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME="ummatics-sentiment"
LAMBDA_FUNCTION_NAME="ummatics-sentiment-analysis"

echo "AWS Region: $AWS_REGION"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "ECR Repo: $ECR_REPO_NAME"

# Step 1: Create ECR repository if it doesn't exist
echo ""
echo "Step 1: Creating ECR repository..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION

# Step 2: Login to ECR
echo ""
echo "Step 2: Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Step 3: Build Docker image
echo ""
echo "Step 3: Building Docker image..."
docker build -t $ECR_REPO_NAME:latest .

# Step 4: Tag and push image
echo ""
echo "Step 4: Pushing image to ECR..."
docker tag $ECR_REPO_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest

# Step 5: Deploy Lambda using SAM
echo ""
echo "Step 5: Deploying Lambda function..."
sam deploy \
    --template-file template.yaml \
    --stack-name ummatics-sentiment-stack \
    --capabilities CAPABILITY_IAM \
    --region $AWS_REGION \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset

# Step 6: Get Lambda function URL
echo ""
echo "Step 6: Getting Lambda function URL..."
FUNCTION_URL=$(aws lambda get-function-url-config --function-name $LAMBDA_FUNCTION_NAME --region $AWS_REGION --query FunctionUrl --output text 2>/dev/null || echo "Not configured")

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Lambda Function Name: $LAMBDA_FUNCTION_NAME"
echo "Lambda Function URL: $FUNCTION_URL"
echo ""
echo "To test the function:"
echo "aws lambda invoke --function-name $LAMBDA_FUNCTION_NAME --payload '{\"texts\":[\"I love this!\"]}' response.json"
echo ""
echo "To enable in backend, set environment variable:"
echo "USE_LAMBDA_SENTIMENT=1"
echo ""
