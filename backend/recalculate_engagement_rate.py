#!/usr/bin/env python3
"""
Recalculate engagement rates for all historical data.
Engagement rate = (total engagement from day's tweets / follower_count) * 100
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', 5432),
        database=os.getenv('DB_NAME', 'ummatics_monitor'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )

def recalculate_engagement_rates():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all dates with metrics
    cur.execute("""
        SELECT DISTINCT date, platform, follower_count
        FROM social_media_daily_metrics
        WHERE platform = 'Twitter'
        ORDER BY date
    """)
    
    metrics = cur.fetchall()
    print(f"Found {len(metrics)} daily metrics to recalculate")
    
    updated = 0
    for metric in metrics:
        date = metric['date']
        platform = metric['platform']
        follower_count = metric['follower_count']
        
        # Get total engagement and mentions for this date
        cur.execute("""
            SELECT 
                COUNT(*) as total_mentions,
                COALESCE(SUM(likes + retweets + replies), 0) as total_engagement
            FROM social_mentions
            WHERE platform = %s 
            AND posted_at::date = %s
        """, (platform, date))
        
        result = cur.fetchone()
        total_mentions = result['total_mentions'] if result else 0
        total_engagement = result['total_engagement'] if result else 0
        
        # Calculate engagement rate as percentage of followers
        # Use the follower count from Nov 2025 onwards, 0 before (since those are backfilled)
        if follower_count > 0:
            engagement_rate = (total_engagement / follower_count * 100)
        else:
            engagement_rate = 0
        
        # Update the metrics
        cur.execute("""
            UPDATE social_media_daily_metrics
            SET engagement_rate = %s,
                mentions_count = %s
            WHERE date = %s AND platform = %s
        """, (engagement_rate, total_mentions, date, platform))
        
        updated += 1
        if updated % 100 == 0:
            print(f"Updated {updated}/{len(metrics)} records...")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\nCompleted! Updated {updated} records.")

if __name__ == '__main__':
    recalculate_engagement_rates()
