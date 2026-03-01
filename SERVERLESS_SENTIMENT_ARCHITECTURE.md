# Serverless LLM Sentiment Analysis Architecture

## Overview
Plan for migrating from TextBlob to transformer-based sentiment analysis using AWS serverless services within free tier limits.

## Current Implementation
- **Library**: TextBlob (rule-based, not ML)
- **Location**: `backend/transformer_sentiment.py` and `backend/api.py`
- **Execution**: Runs synchronously in Flask API during ingestion
- **Performance**: Fast but limited accuracy for nuanced sentiment

## Proposed Architecture Options

### Option 1: AWS Lambda + Hugging Face Model (Recommended)
**Service**: AWS Lambda with containerized transformer model

**Pros**:
- ✅ Free tier: 1M requests/month, 400,000 GB-seconds compute
- ✅ No servers to manage
- ✅ Pay only for execution time
- ✅ Can use Docker container (up to 10GB) for full transformer model
- ✅ Perfect for batch processing (nightly runs)

**Cons**:
- ⚠️ Cold start latency (3-10 seconds for large models)
- ⚠️ Max execution time: 15 minutes
- ⚠️ Memory limit: 10GB (enough for most sentiment models)

**Implementation**:
```
Lambda Function (Python 3.11 container)
├── transformers library
├── PyTorch (CPU only)
├── Model: distilbert-base-uncased-finetuned-sst-2-english (268MB)
└── Handler: process_batch(texts) -> sentiments
```

**Cost Estimate** (beyond free tier):
- Requests: 10,000/month = $2/month
- Compute: ~1s per batch of 10 tweets = negligible
- Total: ~$2/month after free tier

**Example Lambda Handler**:
```python
from transformers import pipeline
import json

# Load model once (outside handler for warm starts)
sentiment_pipeline = pipeline("sentiment-analysis", 
                              model="distilbert-base-uncased-finetuned-sst-2-english")

def lambda_handler(event, context):
    texts = event['texts']  # Array of strings
    results = sentiment_pipeline(texts, truncation=True, max_length=512)
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
```

### Option 2: AWS Fargate (ECS) Spot Instances
**Service**: Fargate Spot for containerized transformer API

**Pros**:
- ✅ No cold starts (always running)
- ✅ Can run larger models (up to 30GB memory)
- ✅ Fargate Spot is 70% cheaper than regular Fargate
- ✅ Easy to deploy existing Docker containers

**Cons**:
- ❌ Not eligible for free tier
- ❌ Minimum cost: ~$10-15/month even with Spot
- ⚠️ Spot instances can be interrupted (rare for small tasks)

**Implementation**:
```
Fargate Task (Always On)
├── Container: Python 3.11
├── Model: bert-base-multilingual-cased (667MB)
├── API: FastAPI endpoint /sentiment
├── Resources: 0.5 vCPU, 1GB RAM
└── Schedule: Run only during ingestion hours (reduce cost)
```

**Cost Estimate**:
- Fargate Spot: $0.01419/vCPU-hour, $0.00156/GB-hour
- 0.5 vCPU + 1GB = ~$0.0079/hour
- Running 24/7: $5.68/month
- Running 2 hours/day: $0.47/month (ideal for scheduled ingestion)

### Option 3: SageMaker Serverless Inference
**Service**: SageMaker Serverless Endpoints for ML models

**Pros**:
- ✅ Purpose-built for ML inference
- ✅ Auto-scaling from 0
- ✅ Managed service (no container management)
- ✅ Integrated with Hugging Face

**Cons**:
- ❌ NOT in free tier (expensive)
- ❌ $0.20/hour minimum + $0.024/GB-hour memory
- ❌ Minimum cost: ~$25/month even with minimal usage

**Implementation**:
```
SageMaker Endpoint
├── Model: Hugging Face from Model Hub
├── Instance: Serverless (4GB memory, 6 vCPUs)
├── Auto-scaling: 0 to 5 instances
└── Integration: boto3 invoke_endpoint()
```

**Cost Estimate**:
- Compute: $0.20/hour when active
- Memory: $0.024/GB-hour
- Inference: $0.20 per 1M requests
- Total: $25-40/month (NOT recommended for free tier)

### Option 4: Local Model on EC2 (Current Architecture Extended)
**Service**: Run transformer on existing EC2 instance

**Pros**:
- ✅ Already within existing EC2 free tier (t2.micro)
- ✅ No additional AWS service costs
- ✅ Simple deployment (add to backend container)
- ✅ No cold starts

**Cons**:
- ⚠️ t2.micro only has 1GB RAM (too small for BERT-based models)
- ⚠️ Would need t3.small (2GB RAM) = $0.0208/hour = ~$15/month
- ⚠️ Model size limits (can use DistilBERT 268MB)
- ⚠️ Sentiment analysis slows down API responses

**Implementation**:
```
EC2 Instance Upgrade
├── Type: t3.small (2GB RAM, 2 vCPU)
├── Model: distilbert-base-uncased-finetuned-sst-2-english
├── Async: Run sentiment analysis in background job
└── Storage: Model cache in /app/models/
```

**Cost**: $15/month (t3.small outside free tier)

## Recommended Approach: Lambda with Container

### Why Lambda?
1. **Cost**: Stays within free tier for first year, $2/month after
2. **Simplicity**: Single function, no infrastructure management  
3. **Scalability**: Auto-scales for batch processing
4. **Efficiency**: Only runs during ingestion (not 24/7)

### Architecture Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ummatics Impact Monitor                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Daily Ingestion (Scheduler)
                              ▼
        ┌──────────────────────────────────────────┐
        │  Backend API (Flask on EC2)               │
        │  - Collects tweets/posts                  │
        │  - Stores in PostgreSQL                   │
        │  - Triggers Lambda for sentiment          │
        └──────────────────────────────────────────┘
                              │
                              │ Invoke Lambda with batch of texts
                              ▼
        ┌──────────────────────────────────────────┐
        │  AWS Lambda Function                      │
        │  Container: Python 3.11                   │
        │  Model: distilbert-sst2 (268MB)          │
        │  Handler: process_sentiment_batch()       │
        │  - Batch size: 50 texts                   │
        │  - Execution: ~5s per batch               │
        └──────────────────────────────────────────┘
                              │
                              │ Return sentiment scores
                              ▼
        ┌──────────────────────────────────────────┐
        │  Backend API                              │
        │  - Update sentiment in database           │
        │  - Calculate aggregate metrics            │
        └──────────────────────────────────────────┘
```

### Implementation Steps

#### 1. Create Lambda Container
**File**: `lambda_sentiment/Dockerfile`
```dockerfile
FROM public.ecr.aws/lambda/python:3.11

# Copy requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download model at build time (not runtime)
RUN python -c "from transformers import pipeline; pipeline('sentiment-analysis', model='distilbert-base-uncased-finetuned-sst-2-english')"

# Copy handler
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

CMD ["lambda_function.lambda_handler"]
```

**File**: `lambda_sentiment/requirements.txt`
```
transformers==4.35.0
torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
```

**File**: `lambda_sentiment/lambda_function.py`
```python
from transformers import pipeline
import json

# Load model once (warm start optimization)
model = pipeline("sentiment-analysis", 
                 model="distilbert-base-uncased-finetuned-sst-2-english",
                 device=-1)  # CPU

def lambda_handler(event, context):
    """
    Event format:
    {
        "texts": ["tweet 1", "tweet 2", ...],
        "batch_size": 50
    }
    """
    try:
        texts = event.get('texts', [])
        if not texts:
            return {'statusCode': 400, 'body': 'No texts provided'}
        
        # Process in batches
        results = []
        for i in range(0, len(texts), 50):
            batch = texts[i:i+50]
            batch_results = model(batch, truncation=True, max_length=512)
            results.extend(batch_results)
        
        # Convert to our format
        output = []
        for text, result in zip(texts, results):
            sentiment = 'positive' if result['label'] == 'POSITIVE' else 'negative'
            score = result['score'] if sentiment == 'positive' else (1 - result['score'])
            output.append({
                'text': text,
                'sentiment': sentiment,
                'score': score
            })
        
        return {
            'statusCode': 200,
            'body': json.dumps(output)
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

#### 2. Deploy Lambda
```bash
# Build and push to ECR
aws ecr create-repository --repository-name ummatics-sentiment-lambda
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

cd lambda_sentiment
docker build -t ummatics-sentiment-lambda .
docker tag ummatics-sentiment-lambda:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/ummatics-sentiment-lambda:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/ummatics-sentiment-lambda:latest

# Create Lambda function
aws lambda create-function \
  --function-name ummatics-sentiment-analysis \
  --package-type Image \
  --code ImageUri=YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/ummatics-sentiment-lambda:latest \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --memory-size 3008 \
  --timeout 300
```

#### 3. Update Backend to Call Lambda
**File**: `backend/ingestion.py`
```python
import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-east-1')

def analyze_sentiment_batch(texts):
    """Call Lambda function for sentiment analysis"""
    try:
        response = lambda_client.invoke(
            FunctionName='ummatics-sentiment-analysis',
            InvocationType='RequestResponse',
            Payload=json.dumps({'texts': texts})
        )
        
        result = json.loads(response['Payload'].read())
        if result['statusCode'] == 200:
            return json.loads(result['body'])
        else:
            logger.error(f"Lambda error: {result['body']}")
            return None
    except Exception as e:
        logger.error(f"Lambda invocation failed: {e}")
        return None

# Usage in ingestion
new_tweets = fetch_tweets()
texts = [tweet['text'] for tweet in new_tweets]
sentiments = analyze_sentiment_batch(texts)

for tweet, sentiment in zip(new_tweets, sentiments):
    tweet['sentiment'] = sentiment['sentiment']
    tweet['sentiment_score'] = sentiment['score']
```

### Alternative: Smaller Model on Current EC2

If Lambda is too complex, use DistilBERT on current EC2:

**File**: `backend/requirements.txt`
```
transformers==4.35.0
torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
```

**File**: `backend/sentiment_transformer.py`
```python
from transformers import pipeline
import logging

logger = logging.getLogger(__name__)

# Load model once at startup
try:
    sentiment_model = pipeline("sentiment-analysis",
                               model="distilbert-base-uncased-finetuned-sst-2-english",
                               device=-1)
    logger.info("Transformer sentiment model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load transformer model: {e}")
    sentiment_model = None

def analyze_sentiment_transformer(text):
    """Analyze sentiment using transformer model"""
    if not sentiment_model:
        # Fallback to TextBlob
        from textblob import TextBlob
        blob = TextBlob(text)
        return 'positive' if blob.sentiment.polarity > 0 else 'negative', blob.sentiment.polarity
    
    try:
        result = sentiment_model(text, truncation=True, max_length=512)[0]
        sentiment = 'positive' if result['label'] == 'POSITIVE' else 'negative'
        score = result['score'] if sentiment == 'positive' else (1 - result['score'])
        return sentiment, score
    except Exception as e:
        logger.error(f"Transformer sentiment failed: {e}")
        # Fallback to TextBlob
        from textblob import TextBlob
        blob = TextBlob(text)
        return 'positive' if blob.sentiment.polarity > 0 else 'negative', blob.sentiment.polarity
```

**Note**: This requires upgrading EC2 to t3.small (2GB RAM) = $15/month.

## Cost Summary

| Option | Setup Cost | Monthly Cost | Free Tier | Complexity |
|--------|-----------|--------------|-----------|------------|
| **Lambda Container** | $0 | $0-2 | ✅ Yes (1st year) | Medium |
| Fargate Spot (2h/day) | $0 | $0.47 | ❌ No | Medium |
| Fargate Spot (24/7) | $0 | $5.68 | ❌ No | Medium |
| SageMaker Serverless | $0 | $25-40 | ❌ No | Low |
| EC2 t3.small | $0 | $15 | ❌ No | Low |

## Recommendation

**Start with Lambda Container**:
1. Stays within free tier for 1 year (1M requests/month)
2. Easy to implement with existing AWS setup
3. Scales automatically for batch processing
4. Falls back to TextBlob if Lambda unavailable
5. Can upgrade to Fargate later if needed

**Deployment Timeline**:
- Week 1: Create Lambda container with DistilBERT
- Week 2: Test with sample data, validate accuracy
- Week 3: Update backend to call Lambda
- Week 4: Monitor costs and performance
- Month 2: Consider Fargate if Lambda limits hit

## Model Options

| Model | Size | Accuracy | Speed | Recommendation |
|-------|------|----------|-------|----------------|
| **distilbert-base-uncased-finetuned-sst-2-english** | 268MB | Good | Fast | ✅ Best for Lambda |
| bert-base-multilingual-cased | 667MB | Better | Medium | Use if multilingual needed |
| roberta-base | 498MB | Better | Medium | Alternative to BERT |
| twitter-roberta-base-sentiment | 499MB | Best | Medium | ✅ Ideal for tweets |

**Recommended**: Start with `distilbert-sst2` for general sentiment, switch to `twitter-roberta-base-sentiment` if tweet-specific accuracy needed.
