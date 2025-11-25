#!/usr/bin/env python3
"""
Process Apify tweet data from JSON file and insert into database
"""
import json
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from ingestion import get_db_connection, analyze_sentiment_textblob, update_sentiment_metrics, get_current_week_dates

def parse_twitter_date(date_str):
    """Parse Twitter date format: 'Sat Nov 22 21:02:18 +0000 2025'"""
    try:
        return datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
    except (ValueError, TypeError) as e:
        print(f"Warning: Could not parse date '{date_str}': {e}")
        return datetime.now()

def process_apify_json(json_file):
    """Process Apify JSON file and insert tweets into database"""
    
    print(f"Loading data from {json_file}...")
    with open(json_file, 'r') as f:
        tweets = json.load(f)
    
    print(f"Loaded {len(tweets)} tweets from file")
    
    # Get existing tweet IDs
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT post_id FROM social_mentions WHERE platform = 'Twitter'")
    existing_tweet_ids = set(row[0] for row in cur.fetchall())
    print(f"Found {len(existing_tweet_ids)} existing tweets in database")
    cur.close()
    conn.close()
    
    monday, sunday = get_current_week_dates()
    today = datetime.now().date()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    new_mentions = 0
    skipped_duplicates = 0
    skipped_own_posts = 0
    total_engagement = 0
    errors = 0
    
    for idx, tweet in enumerate(tweets, 1):
        try:
            # Extract tweet data
            tweet_id = tweet.get('id', '')
            if not tweet_id:
                print(f"Tweet {idx}: Missing ID, skipping")
                continue
            
            # Get author info
            author_info = tweet.get('author', {})
            author_username = author_info.get('userName', 'Unknown')
            
            # Skip if this is from @ummatics itself
            if author_username.lower() == 'ummatics':
                skipped_own_posts += 1
                continue
            
            # Skip if we already have this tweet
            if tweet_id in existing_tweet_ids:
                skipped_duplicates += 1
                continue
            
            # Extract tweet content and metadata
            content = tweet.get('text', '') or tweet.get('fullText', '')
            post_url = tweet.get('url', f"https://twitter.com/{author_username}/status/{tweet_id}")
            
            # Parse created date
            created_at = tweet.get('createdAt', '')
            if created_at:
                posted_at = parse_twitter_date(created_at)
            else:
                posted_at = datetime.now()
            
            # Extract engagement metrics
            likes = tweet.get('likeCount', 0)
            retweets = tweet.get('retweetCount', 0)
            replies = tweet.get('replyCount', 0)
            
            total_engagement += likes + retweets + replies
            
            # Analyze sentiment using TextBlob
            sentiment, sentiment_score = analyze_sentiment_textblob(content)
            
            # Insert into database
            cur.execute("""
                INSERT INTO social_mentions 
                (week_start_date, platform, post_id, author, content, post_url, posted_at, likes, retweets, replies, sentiment, sentiment_score, sentiment_analyzed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (post_id) DO NOTHING
            """, (monday, 'Twitter', tweet_id, author_username, content, post_url, posted_at, likes, retweets, replies, sentiment, sentiment_score, datetime.now()))
            
            if cur.rowcount > 0:
                new_mentions += 1
                if new_mentions % 100 == 0:
                    print(f"Processed {new_mentions} new tweets...")
                    
        except Exception as e:
            errors += 1
            print(f"Error processing tweet {idx} (ID: {tweet.get('id', 'unknown')}): {e}")
            if errors > 50:
                print("Too many errors, stopping...")
                break
            continue
    
    # Update follower count
    follower_count = 0
    if tweets and tweets[0].get('author'):
        # Use follower count from first tweet's author if it's ummatics
        first_author = tweets[0].get('author', {})
        if first_author.get('userName', '').lower() == 'ummatics':
            follower_count = first_author.get('followers', 0)
    
    if follower_count == 0:
        # Get from previous record
        cur.execute("""
            SELECT follower_count FROM social_media_daily_metrics 
            WHERE platform = 'Twitter' 
            ORDER BY date DESC LIMIT 1
        """)
        result = cur.fetchone()
        if result and result[0] > 0:
            follower_count = result[0]
    
    # Calculate engagement rate from ALL tweets posted today (not just new ones)
    # Engagement rate = (total engagement from all today's tweets / follower_count) * 100
    cur.execute("""
        SELECT 
            COUNT(*) as total_mentions,
            COALESCE(SUM(likes + retweets + replies), 0) as total_engagement
        FROM social_mentions
        WHERE platform = 'Twitter' 
        AND posted_at::date = %s
    """, (today,))
    
    result = cur.fetchone()
    total_mentions_today = result[0] if result else 0
    total_engagement_today = result[1] if result else 0
    
    # Calculate engagement rate as percentage of followers
    engagement_rate = (total_engagement_today / follower_count * 100) if follower_count > 0 else 0
    
    # Update social media daily metrics
    cur.execute("""
        INSERT INTO social_media_daily_metrics (date, platform, follower_count, mentions_count, engagement_rate)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (date, platform) 
        DO UPDATE SET 
            follower_count = EXCLUDED.follower_count,
            mentions_count = EXCLUDED.mentions_count,
            engagement_rate = EXCLUDED.engagement_rate
    """, (today, 'Twitter', follower_count, total_mentions_today, engagement_rate))
    
    conn.commit()
    cur.close()
    conn.close()
    
    # Update sentiment metrics
    update_sentiment_metrics(today)
    
    print(f"\n=== Processing Complete ===")
    print(f"Total tweets in file: {len(tweets)}")
    print(f"New mentions added: {new_mentions}")
    print(f"Skipped duplicates: {skipped_duplicates}")
    print(f"Skipped own posts: {skipped_own_posts}")
    print(f"Errors: {errors}")
    print(f"Follower count: {follower_count}")
    print(f"Engagement rate: {engagement_rate:.2f}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python process_apify_json.py <json_file>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    if not os.path.exists(json_file):
        print(f"Error: File {json_file} not found")
        sys.exit(1)
    
    process_apify_json(json_file)
