#!/usr/bin/env python3
"""
Script to recalculate sentiment for existing Reddit posts using transformer.
This updates posts that were previously analyzed with TextBlob.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Add parent directory to path to import analyze_sentiment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion import analyze_sentiment

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME', 'ummatics_monitor'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )

def recalculate_reddit_sentiment():
    """Recalculate sentiment for all Reddit posts using transformer."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all Reddit posts
    cur.execute("""
        SELECT id, content, author
        FROM social_mentions
        WHERE platform = 'Reddit'
        ORDER BY posted_at DESC
    """)
    
    reddit_posts = cur.fetchall()
    total_posts = len(reddit_posts)
    
    if total_posts == 0:
        print("No Reddit posts found in database.")
        cur.close()
        conn.close()
        return
    
    print(f"Found {total_posts} Reddit posts. Recalculating sentiment using transformer...")
    
    updated_count = 0
    for i, post in enumerate(reddit_posts, 1):
        try:
            # Analyze sentiment using transformer
            sentiment, sentiment_score = analyze_sentiment(post['content'])
            
            # Update the post
            cur.execute("""
                UPDATE social_mentions
                SET sentiment = %s,
                    sentiment_score = %s,
                    sentiment_analyzed_at = %s
                WHERE id = %s
            """, (sentiment, sentiment_score, datetime.now(), post['id']))
            
            updated_count += 1
            print(f"[{i}/{total_posts}] Updated post by {post['author']}: {sentiment} ({sentiment_score})")
            
        except Exception as e:
            print(f"[{i}/{total_posts}] Error updating post ID {post['id']}: {e}")
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\nCompleted! Updated {updated_count}/{total_posts} Reddit posts with transformer-based sentiment.")

if __name__ == '__main__':
    # Check if transformer is enabled
    use_transformer = os.getenv('USE_TRANSFORMER', '0') in ('1', 'true', 'True')
    if not use_transformer:
        print("WARNING: USE_TRANSFORMER is not set to 1. Sentiment will use TextBlob instead.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
    
    recalculate_reddit_sentiment()
