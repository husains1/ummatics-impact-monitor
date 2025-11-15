import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _get_pipeline():
    try:
        from transformers import pipeline
        model_name = os.getenv('TRANSFORMER_SENTIMENT_MODEL', 'cardiffnlp/twitter-roberta-base-sentiment')
        # Use huggingface pipeline for sentiment-analysis
        pipe = pipeline('sentiment-analysis', model=model_name, tokenizer=model_name)
        logger.info(f"Loaded transformer sentiment model: {model_name}")
        return pipe
    except Exception as e:
        logger.error(f"Error loading transformer pipeline: {e}")
        return None


def analyze_sentiment_transformer(text):
    """Analyze sentiment using the transformer pipeline.
    Returns (label, score) where label in {'positive','negative','neutral'} and score is float polarity/confidence.
    If pipeline is unavailable, returns ('neutral', 0.0)"""
    try:
        if not text:
            return 'neutral', 0.0

        # Lightweight cleaning similar to TextBlob pipeline
        s = str(text)
        if s.strip().upper().startswith('RT'):
            s = s.split(':', 1)[-1] if ':' in s else s[2:]
        import re
        s = re.sub(r"https?://\\S+", "", s)
        s = s.replace('...', ' ').replace('…', ' ')
        s = re.sub(r"\\s+", ' ', s).strip()

        pipe = _get_pipeline()
        if not pipe:
            return 'neutral', 0.0

        result = pipe(s[:512])  # truncate to a reasonable length for tokenizer
        if not result:
            return 'neutral', 0.0

        # pipeline returns list of dicts like [{'label': 'LABEL_0', 'score': 0.99}] or {'label':'positive'} depending on model
        out = result[0]
        label = out.get('label')
        score = float(out.get('score', 0.0))

        # Normalize labels for common models
        if isinstance(label, str):
            l = label.lower()
            if l.startswith('pos') or 'positive' in l:
                normalized = 'positive'
            elif l.startswith('neg') or 'negative' in l:
                normalized = 'negative'
            elif l.startswith('neu') or 'neutral' in l:
                normalized = 'neutral'
            else:
                # some models use numeric mapping (e.g., CARDIFF labels might be 'LABEL_0')
                # For cardiff models, labels are often 'LABEL_0'->negative, 'LABEL_1'->neutral, 'LABEL_2'->positive
                if label.upper().startswith('LABEL_'):
                    try:
                        idx = int(label.split('_')[-1])
                        if idx == 0:
                            normalized = 'negative'
                        elif idx == 1:
                            normalized = 'neutral'
                        elif idx == 2:
                            normalized = 'positive'
                        else:
                            normalized = 'neutral'
                    except Exception:
                        normalized = 'neutral'
                else:
                    normalized = 'neutral'
        else:
            normalized = 'neutral'

        return normalized, round(score, 2)
    except Exception as e:
        logger.error(f"Transformer sentiment error: {e}")
        return 'neutral', 0.0
