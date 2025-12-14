# AWS Lambda Sentiment Analysis

## Overview
This Lambda function performs sentiment analysis using the DistilBERT transformer model. It's designed for cost-effective, serverless sentiment analysis within AWS free tier limits.

## Architecture
- **Model**: `distilbert-base-uncased-finetuned-sst-2-english` (268MB)
- **Runtime**: Python 3.11 in Lambda container
- **Memory**: 2048MB (needed for transformer model)
- **Timeout**: 60 seconds
- **Cold Start**: ~5-10 seconds (first invocation)
- **Warm Start**: ~100-500ms

## Cost Estimate

### Free Tier (First 12 Months)
- **Requests**: 1M free requests/month
- **Compute**: 400,000 GB-seconds free

### After Free Tier
For 10,000 sentiment analyses per month:
- Memory: 2048MB = 2GB
- Duration: ~2 seconds per batch of 50 texts
- Requests: 200 invocations (10,000 texts / 50 per batch)

**Monthly Cost**: 
- Requests: 200 × $0.0000002 = $0.00004
- Compute: 200 × 2s × 2GB × $0.0000166667 = $0.013
- **Total: ~$0.01/month**

Compare to running EC2 24/7: ~$10-15/month

### vs Current Transformer (In-Container)
- Current: Runs in EC2 container, uses memory 24/7
- Lambda: Only charged when analyzing sentiment
- **Savings**: ~99% cost reduction for occasional sentiment analysis

## Deployment

### Prerequisites
```bash
# Install AWS SAM CLI
pip install aws-sam-cli

# Configure AWS credentials
aws configure
```

### Deploy to AWS
```bash
cd lambda
chmod +x deploy.sh
./deploy.sh
```

This will:
1. Create ECR repository
2. Build Docker image with transformer model
3. Push to ECR
4. Deploy Lambda function using SAM
5. Output function URL and ARN

### Test Locally
```bash
chmod +x test-local.sh
./test-local.sh
```

### Test on AWS
```bash
aws lambda invoke \
    --function-name ummatics-sentiment-analysis \
    --payload '{"texts":["I love this!", "This is bad", "It is okay"]}' \
    response.json

cat response.json | python3 -m json.tool
```

## Integration with Backend

### Environment Variables
Add to `.env`:
```bash
USE_LAMBDA_SENTIMENT=1
SENTIMENT_LAMBDA_FUNCTION=ummatics-sentiment-analysis
AWS_REGION=us-east-1
```

### IAM Permissions
The EC2 instance or container needs permission to invoke Lambda:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-east-1:*:function:ummatics-sentiment-analysis"
    }
  ]
}
```

## API Usage

### Input Format
```json
{
  "texts": [
    "This is amazing!",
    "I don't like this.",
    "It's okay."
  ]
}
```

### Output Format
```json
{
  "statusCode": 200,
  "body": {
    "results": [
      {"sentiment": "positive", "score": 0.98},
      {"sentiment": "negative", "score": 0.87},
      {"sentiment": "neutral", "score": 0.65}
    ],
    "count": 3
  }
}
```

### Sentiment Labels
- `positive`: Positive sentiment (score = confidence)
- `negative`: Negative sentiment (score = confidence)
- `neutral`: Neutral/mixed sentiment (score = confidence)

## Performance Optimization

### Batch Processing
- Process up to 50 texts per invocation
- Lambda has 6MB payload limit
- Backend batches requests automatically

### Cold Start Mitigation
- Model cached in global scope
- Reused across warm invocations
- Consider using Lambda provisioned concurrency if needed (costs extra)

### Memory Tuning
- 2048MB: Good balance of speed and cost
- 1024MB: Slower but cheaper (not recommended)
- 3008MB: Faster cold starts (2x cost)

## Monitoring

### CloudWatch Metrics
- Invocations
- Duration
- Errors
- Throttles

### Logs
```bash
aws logs tail /aws/lambda/ummatics-sentiment-analysis --follow
```

## Troubleshooting

### "Task timed out after 60 seconds"
- Increase timeout in `template.yaml`
- Reduce batch size in backend

### "Out of memory"
- Increase MemorySize in `template.yaml`
- Current: 2048MB (sufficient for DistilBERT)

### "Cold start too slow"
- Enable provisioned concurrency (costs money)
- Or accept 5-10s delay on first request

### "Lambda invocation failed"
- Check IAM permissions on EC2/container
- Verify Lambda function exists and is deployed
- Check CloudWatch logs for errors

## Cost Monitoring

### View Costs
```bash
# Get Lambda costs for last month
aws ce get-cost-and-usage \
    --time-period Start=2025-11-01,End=2025-12-01 \
    --granularity MONTHLY \
    --metrics BlendedCost \
    --filter file://lambda-cost-filter.json
```

### Set Billing Alerts
1. Go to AWS Billing Console
2. Create budget for Lambda
3. Set threshold at $1/month
4. Get email alerts if exceeded

## Cleanup

To remove Lambda and save costs:
```bash
# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name ummatics-sentiment-stack

# Delete ECR repository
aws ecr delete-repository --repository-name ummatics-sentiment --force
```
