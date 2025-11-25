#!/usr/bin/env python3
"""
Regenerate historical metrics for all dates with Twitter mentions
"""
import os
import psycopg2
from datetime import datetime, timedelta
from textblob import TextBlob

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'ummatics_monitor'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

def update_sentiment_metrics(target_date, platform):
    """Update sentiment metrics for a specific date and platform"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get sentiment and scores for the date
    cur.execute("""
        SELECT sentiment, sentiment_score 
        FROM social_mentions 
        WHERE platform = %s 
        AND DATE(posted_at) = %s
    """, (platform, target_date))
    
    rows = cur.fetchall()
    
    if rows:
        positive_count = sum(1 for r in rows if r[0] == 'positive')
        negative_count = sum(1 for r in rows if r[0] == 'negative')
        neutral_count = sum(1 for r in rows if r[0] == 'neutral')
        unanalyzed_count = sum(1 for r in rows if r[0] is None or r[0] == '')
        
        # Calculate average score from numeric sentiment_score column
        valid_scores = [float(r[1]) for r in rows if r[1] is not None]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        # Insert or update sentiment metrics
        cur.execute("""
            INSERT INTO social_sentiment_metrics 
            (date, platform, positive_count, negative_count, neutral_count, unanalyzed_count, average_sentiment_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, platform) 
            DO UPDATE SET 
                positive_count = EXCLUDED.positive_count,
                negative_count = EXCLUDED.negative_count,
                neutral_count = EXCLUDED.neutral_count,
                unanalyzed_count = EXCLUDED.unanalyzed_count,
                average_sentiment_score = EXCLUDED.average_sentiment_score
        """, (target_date, platform, positive_count, negative_count, neutral_count, unanalyzed_count, avg_score))
        
        conn.commit()
        print(f"✓ {target_date}: {len(rows)} mentions (+{positive_count} -{negative_count} ={neutral_count}), avg: {avg_score:.3f}")
    
    cur.close()
    conn.close()

def regenerate_all_metrics():
    """Regenerate metrics for all dates with Twitter mentions"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get all unique dates with Twitter mentions
    cur.execute("""
        SELECT DISTINCT DATE(posted_at) as date, COUNT(*) as count
        FROM social_mentions 
        WHERE platform = 'Twitter'
        GROUP BY DATE(posted_at)
        ORDER BY date
    """)
    
    dates = cur.fetchall()
    cur.close()
    conn.close()
    
    print(f"Found {len(dates)} unique dates with Twitter mentions")
    print(f"Date range: {dates[0][0]} to {dates[-1][0]}")
    print("Regenerating metrics...\n")
    
    for date, count in dates:
        update_sentiment_metrics(date, 'Twitter')
    
    print(f"\n✅ Complete! Regenerated metrics for {len(dates)} dates")

def regenerate_daily_metrics():
    """Regenerate daily metrics for all dates"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get all unique dates
    cur.execute("""
        SELECT DISTINCT DATE(posted_at) as date
        FROM social_mentions 
        WHERE platform = 'Twitter'
        ORDER BY date
    """)
    
    dates = [row[0] for row in cur.fetchall()]
    
    print(f"\nRegenerating daily metrics for {len(dates)} dates...")
    
    for date in dates:
        # Get mention count for the date
        cur.execute("""
            SELECT COUNT(*) 
            FROM social_mentions 
            WHERE platform = 'Twitter' 
            AND DATE(posted_at) = %s
        """, (date,))
        
        mention_count = cur.fetchone()[0]
        
        # For historical dates, we don't have follower count data
        # Use the most recent follower count or 0
        cur.execute("""
            SELECT follower_count 
            FROM social_media_daily_metrics 
            WHERE platform = 'Twitter' 
            AND follower_count IS NOT NULL
            ORDER BY date DESC 
            LIMIT 1
        """)
        
        result = cur.fetchone()
        follower_count = result[0] if result else 0
        
        # Insert or update daily metrics
        cur.execute("""
            INSERT INTO social_media_daily_metrics (date, platform, follower_count, mentions_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (date, platform) 
            DO UPDATE SET mentions_count = EXCLUDED.mentions_count
        """, (date, 'Twitter', follower_count, mention_count))
        
        conn.commit()
        print(f"✓ {date}: {mention_count} mentions, {follower_count} followers")
    
    cur.close()
    conn.close()
    
    print(f"\n✅ Daily metrics complete!")

if __name__ == "__main__":
    print("=" * 60)
    print("REGENERATING HISTORICAL METRICS")
    print("=" * 60)
    
    regenerate_all_metrics()
    regenerate_daily_metrics()
    
    print("\n" + "=" * 60)
    print("ALL METRICS REGENERATED SUCCESSFULLY")
    print("=" * 60)
