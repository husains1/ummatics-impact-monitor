"""
AWS Lambda function for sentiment analysis using DistilBERT transformer.

Cost optimization:
- Uses Lambda free tier: 1M requests/month, 400,000 GB-seconds compute
- Model cached between invocations (warm starts ~100ms)
- Batch processing for efficiency
- Lightweight DistilBERT model (268MB)

Estimated costs after free tier:
- 10,000 invocations/month @ 512MB, 2s avg = $0.17/month
- Much cheaper than running EC2 24/7 (~$10/month)
"""

import json
import os
import logging
import re
from typing import List, Dict

# Set HuggingFace cache to /tmp (Lambda only writable directory)
os.environ['TRANSFORMERS_CACHE'] = '/tmp/transformers_cache'
os.environ['HF_HOME'] = '/tmp/hf_home'

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global variable to cache model (persists between warm starts)
sentiment_pipeline = None

# Model cache directory (bundled in container image)
MODEL_CACHE_DIR = "/opt/ml/model"


def get_sentiment_pipeline():
    """
    Load and cache the sentiment analysis model.
    Uses global variable to persist between invocations.
    Model is pre-downloaded in container image for faster cold starts.
    """
    global sentiment_pipeline
    
    if sentiment_pipeline is None:
        logger.info("Loading DistilBERT model (cold start)...")
        from transformers import pipeline
        
        # Use CPU-optimized model (Lambda doesn't have GPU)
        # Model pre-downloaded in container at /opt/ml/model
        sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            model_kwargs={"cache_dir": MODEL_CACHE_DIR},
            device=-1,  # CPU
            truncation=True,
            max_length=512
        )
        logger.info("Model loaded successfully")
    
    return sentiment_pipeline


def clean_text(text: str) -> str:
    """Clean text for sentiment analysis."""
    if not text:
        return ""
    
    s = str(text)
    # Remove RT prefix
    s = re.sub(r"^RT\s+@\w+:\s*", '', s)
    # Remove URLs
    s = re.sub(r'http[s]?://\S+', '', s)
    # Remove HTML entities
    s = s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    # Normalize ellipses
    s = s.replace('…', ' ')
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    # Truncate to model limit
    return s[:512]


def analyze_texts(texts: List[str]) -> List[Dict]:
    """
    Analyze sentiment using DistilBERT transformer.
    
    Returns list of dicts with sentiment and confidence score.
    """
    pipeline = get_sentiment_pipeline()
    results = []
    
    # Process in batches of 10 for efficiency
    batch_size = 10
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        
        try:
            # Clean texts
            cleaned = [clean_text(text) for text in batch]
            
            # Skip empty texts
            non_empty = [(idx, text) for idx, text in enumerate(cleaned) if text]
            
            if not non_empty:
                # All texts empty, return neutral
                for _ in batch:
                    results.append({
                        'sentiment': 'neutral',
                        'score': 0.0
                    })
                continue
            
            # Run inference only on non-empty texts
            indices, valid_texts = zip(*non_empty) if non_empty else ([], [])
            predictions = pipeline(list(valid_texts))
            
            # Map predictions back to original batch positions
            pred_map = {idx: pred for idx, pred in zip(indices, predictions)}
            
            for idx in range(len(batch)):
                if idx in pred_map:
                    pred = pred_map[idx]
                    label = pred['label'].lower()
                    
                    # Map HuggingFace labels to our format
                    if label == 'positive':
                        sentiment = 'positive'
                    elif label == 'negative':
                        sentiment = 'negative'
                    else:
                        sentiment = 'neutral'
                    
                    results.append({
                        'sentiment': sentiment,
                        'score': round(pred['score'], 2)
                    })
                else:
                    # Empty text
                    results.append({
                        'sentiment': 'neutral',
                        'score': 0.0
                    })
                    
        except Exception as e:
            logger.error(f"Batch processing error: {e}", exc_info=True)
            # Fallback to neutral for this batch
            for _ in batch:
                results.append({
                    'sentiment': 'neutral',
                    'score': 0.0,
                    'error': str(e)
                })
    
    return results


def lambda_handler(event, context):
    """
    Lambda handler for sentiment analysis.
    
    Input event format:
    {
        "texts": ["text1", "text2", ...]
    }
    
    Output format:
    {
        "statusCode": 200,
        "body": {
            "results": [
                {"sentiment": "positive", "score": 0.95},
                {"sentiment": "negative", "score": 0.82},
                ...
            ],
            "count": 2
        }
    }
    """
    try:
        # Parse input
        if isinstance(event, str):
            event = json.loads(event)
        
        # Handle both direct invocation and API Gateway format
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            texts = body.get('texts', [])
        else:
            texts = event.get('texts', [])
        
        if not texts:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No texts provided'})
            }
        
        if not isinstance(texts, list):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'texts must be a list'})
            }
        
        logger.info(f"Processing {len(texts)} texts")
        
        # Analyze sentiment
        results = analyze_texts(texts)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'results': results,
                'count': len(results)
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda handler error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
