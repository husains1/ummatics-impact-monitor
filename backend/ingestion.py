import os
import psycopg2
from datetime import datetime, timedelta
import requests
import feedparser
import urllib.request
import urllib.parse
import logging
import time  # Add time module for delays
import re
import json
from textblob import TextBlob
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'ummatics_monitor'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

# API Configuration
GOOGLE_ALERTS_RSS_URL = os.getenv('GOOGLE_ALERTS_RSS_URL', '')
REDDIT_RSS_URLS = os.getenv('REDDIT_RSS_URLS', '').split(',') if os.getenv('REDDIT_RSS_URLS') else []
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')
GA4_PROPERTY_ID = os.getenv('GA4_PROPERTY_ID', '')
CONTACT_EMAIL = os.getenv('CONTACT_EMAIL', 'contact@ummatics.org')


def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG)


def get_current_week_dates():
    """Get the start and end dates of the current week (Monday to Sunday)"""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def analyze_sentiment(text):
    """Wrapper that uses transformer classifier when enabled via env var, otherwise TextBlob.
    Returns: (sentiment_label, sentiment_score)
    - sentiment_label: 'positive', 'negative', or 'neutral'
    - sentiment_score: model confidence or polarity (rounded)
    """
    try:
        use_transformer = os.getenv('USE_TRANSFORMER', '0') in ('1', 'true', 'True')
        if use_transformer:
            # lazy import to avoid hard dependency when not in use
            try:
                from transformer_sentiment import analyze_sentiment_transformer
                return analyze_sentiment_transformer(text)
            except Exception as e:
                logger.warning(f"Transformer unavailable, falling back to TextBlob: {e}")

        if not text:
            return 'neutral', 0.0

        # Clean text: remove RT prefixes, urls, and trailing ellipses
        import re
        s = str(text)
        s = re.sub(r"^RT\s+@\w+:\s*", '', s)
        s = re.sub(r'http[s]?://\S+', '', s)
        s = s.replace('…', ' ')
        s = re.sub(r'\s+', ' ', s).strip()

        blob = TextBlob(s)
        polarity = blob.sentiment.polarity
        if polarity > 0.1:
            sentiment = 'positive'
        elif polarity < -0.1:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        return sentiment, round(polarity, 2)
    except Exception as e:
        logger.warning(f"Error analyzing sentiment: {e}")
        return 'neutral', 0.0

def analyze_sentiment_textblob(text):
    """Analyze sentiment using TextBlob only (faster, for Reddit posts).
    Returns: (sentiment_label, sentiment_score)
    """
    try:
        if not text:
            return 'neutral', 0.0

        # Clean text
        import re
        s = str(text)
        s = re.sub(r"^RT\s+@\w+:\s*", '', s)
        s = re.sub(r'http[s]?://\S+', '', s)
        s = s.replace('…', ' ')
        s = re.sub(r'\s+', ' ', s).strip()

        blob = TextBlob(s)
        polarity = blob.sentiment.polarity
        if polarity > 0.1:
            sentiment = 'positive'
        elif polarity < -0.1:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        return sentiment, round(polarity, 2)
    except Exception as e:
        logger.warning(f"Error analyzing sentiment with TextBlob: {e}")
        return 'neutral', 0.0


def update_sentiment_metrics(date, platform='Twitter'):
    """Update daily sentiment metrics based on analyzed social mentions

    Args:
        date: The date to update metrics for
        platform: The social platform to update ('Twitter', 'Reddit', etc.)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Count sentiment categories for the specified date and platform
        cur.execute("""
            SELECT
                COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as positive_count,
                COUNT(CASE WHEN sentiment = 'negative' THEN 1 END) as negative_count,
                COUNT(CASE WHEN sentiment = 'neutral' THEN 1 END) as neutral_count,
                COUNT(CASE WHEN sentiment IS NULL THEN 1 END) as unanalyzed_count,
                AVG(CAST(sentiment_score AS FLOAT)) as avg_score
            FROM social_mentions
            WHERE platform = %s
            AND DATE(posted_at) = %s
        """, (platform, date))

        result = cur.fetchone()
        positive = result[0] if result[0] else 0
        negative = result[1] if result[1] else 0
        neutral = result[2] if result[2] else 0
        unanalyzed = result[3] if result[3] else 0
        avg_score = result[4] if result[4] else 0.0

        # Insert or update sentiment metrics
        cur.execute("""
            INSERT INTO social_sentiment_metrics (date, platform, positive_count, negative_count, neutral_count, unanalyzed_count, average_sentiment_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, platform)
            DO UPDATE SET
                positive_count = EXCLUDED.positive_count,
                negative_count = EXCLUDED.negative_count,
                neutral_count = EXCLUDED.neutral_count,
                unanalyzed_count = EXCLUDED.unanalyzed_count,
                average_sentiment_score = EXCLUDED.average_sentiment_score
        """, (date, platform, positive, negative, neutral, unanalyzed, avg_score))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Sentiment metrics updated for {platform} on {date}: {positive} positive, {negative} negative, {neutral} neutral, {unanalyzed} unanalyzed")
    except Exception as e:
        logger.error(f"Error updating sentiment metrics for {platform}: {e}")


def ingest_google_alerts():
    """Fetch news mentions from Google Alerts RSS feed"""
    logger.info("Starting Google Alerts ingestion...")
    
    if not GOOGLE_ALERTS_RSS_URL:
        logger.warning("Google Alerts RSS URL not configured")
        return
    
    try:
        feed = feedparser.parse(GOOGLE_ALERTS_RSS_URL)
        monday, sunday = get_current_week_dates()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        new_mentions = 0
        for entry in feed.entries:
            try:
                title = entry.get('title', '')
                url = entry.get('link', '')
                source = entry.get('source', {}).get('title', 'Unknown')
                published_at = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
                snippet = entry.get('summary', '')[:500]
                
                # Insert news mention
                cur.execute("""
                    INSERT INTO news_mentions (week_start_date, title, url, source, published_at, snippet)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url, title) DO NOTHING
                """, (monday, title, url, source, published_at, snippet))
                
                if cur.rowcount > 0:
                    new_mentions += 1
                    
            except Exception as e:
                logger.error(f"Error processing news entry: {e}")
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Google Alerts ingestion complete. New mentions: {new_mentions}")
        
    except Exception as e:
        logger.error(f"Error in Google Alerts ingestion: {e}")


def discover_new_subreddits():
    """
    Search for new subreddits mentioning 'ummatics' or 'ummatic' using Reddit's search RSS.
    Uses both sitewide search and targeted searches within specific subreddits.
    Returns a list of newly discovered subreddit names.
    """
    logger.info("Starting subreddit discovery via Reddit search RSS...")

    discovered_subreddits = set()

    try:
        # Strategy 1: Sitewide search
        # This searches ALL of Reddit for posts containing the keywords
        search_query = "ummatic OR ummatics"
        search_url = f"https://www.reddit.com/search.rss?q={urllib.parse.quote(search_query)}"

        logger.info(f"Fetching Reddit sitewide search RSS: {search_url}")

        req = urllib.request.Request(
            search_url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; UmmaticsBot/1.0; +http://ummatics.org)'}
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            feed_content = response.read()

        feed = feedparser.parse(feed_content)
        logger.info(f"Found {len(feed.entries)} results from sitewide search")

        # Extract subreddit names from the post links
        for entry in feed.entries:
            try:
                link = entry.get('link', '')
                match = re.search(r'reddit\.com/r/([a-zA-Z0-9_]+)/', link)
                if match:
                    subreddit = match.group(1).lower()
                    if subreddit not in ['all', 'popular', 'announcements', 'reddit']:
                        discovered_subreddits.add(subreddit)
                        logger.info(f"Discovered subreddit from sitewide search: r/{subreddit}")
            except Exception as e:
                logger.error(f"Error processing search result: {e}")
                continue

        # Strategy 2: Search within specific Islamic/Muslim subreddits
        # Reddit's sitewide search may miss older posts, so we also search within
        # specific subreddits where relevant content is likely to appear
        target_subreddits = [
            'islam', 'Muslim', 'MuslimLounge', 'progressive_islam',
            'PanIslamistPosting', 'islamichistory', 'converts',
            'pakistan', 'egypt', 'turkey', 'indonesia', 'malaysia',
            'saudiarabia', 'arabs', 'MiddleEastNews'
        ]

        for subreddit in target_subreddits:
            try:
                targeted_query = f"{search_query} subreddit:{subreddit}"
                targeted_url = f"https://www.reddit.com/search.rss?q={urllib.parse.quote(targeted_query)}"

                logger.info(f"Searching within r/{subreddit}...")

                req = urllib.request.Request(
                    targeted_url,
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; UmmaticsBot/1.0; +http://ummatics.org)'}
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    feed_content = response.read()

                feed = feedparser.parse(feed_content)

                if len(feed.entries) > 0:
                    logger.info(f"  Found {len(feed.entries)} results in r/{subreddit}")
                    # If we find results in this subreddit, add it to discovered list
                    discovered_subreddits.add(subreddit.lower())

            except Exception as e:
                logger.error(f"Error searching r/{subreddit}: {e}")
                continue

        # Get current subreddits from environment
        current_urls = os.getenv('REDDIT_RSS_URLS', '').split(',')
        current_subreddits = set()
        for url in current_urls:
            match = re.search(r'/r/([a-zA-Z0-9_]+)/', url)
            if match:
                current_subreddits.add(match.group(1).lower())

        # Find new subreddits not already being monitored
        new_subreddits = discovered_subreddits - current_subreddits

        if new_subreddits:
            logger.info(f"Found {len(new_subreddits)} new subreddits: {', '.join(new_subreddits)}")

            # Save discovered subreddits to database
            conn = get_db_connection()
            cur = conn.cursor()
            for subreddit in new_subreddits:
                try:
                    cur.execute("""
                        INSERT INTO discovered_subreddits (subreddit_name, is_active)
                        VALUES (%s, %s)
                        ON CONFLICT (subreddit_name) DO UPDATE SET
                            last_checked = CURRENT_TIMESTAMP
                    """, (subreddit, True))
                except Exception as e:
                    logger.error(f"Error saving subreddit {subreddit}: {e}")
            conn.commit()
            cur.close()
            conn.close()
        else:
            logger.info("No new subreddits discovered")

        logger.info(f"Subreddit discovery complete. Total discovered: {len(discovered_subreddits)}, New: {len(new_subreddits)}")
        return list(new_subreddits)

    except Exception as e:
        logger.error(f"Error in subreddit discovery: {e}")
        return []


def ingest_reddit():
    """Fetch Reddit mentions from RSS feeds"""
    logger.info("Starting Reddit ingestion...")

    if not REDDIT_RSS_URLS or len(REDDIT_RSS_URLS) == 0:
        logger.warning("Reddit RSS URLs not configured")
        return

    try:
        monday, sunday = get_current_week_dates()
        today = datetime.now().date()

        conn = get_db_connection()
        cur = conn.cursor()

        total_new_mentions = 0
        total_mentions_today = 0

        for feed_index, rss_url in enumerate(REDDIT_RSS_URLS):
            rss_url = rss_url.strip()
            if not rss_url:
                continue

            try:
                logger.info(f"Fetching Reddit RSS feed {feed_index + 1}/{len(REDDIT_RSS_URLS)}: {rss_url}")
                # Reddit requires User-Agent header to return RSS/XML instead of HTML
                req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0 (compatible; UmmaticsBot/1.0)'})
                response = urllib.request.urlopen(req)
                content = response.read()
                feed = feedparser.parse(content)

                logger.info(f"Found {len(feed.entries)} entries in feed")

                for entry_index, entry in enumerate(feed.entries):
                    try:
                        # Extract Reddit post details
                        post_id = entry.get('id', '')
                        if not post_id:
                            continue

                        # Reddit RSS feeds provide different fields
                        title = entry.get('title', '')
                        author = entry.get('author', 'Unknown')
                        post_url = entry.get('link', '')
                        full_summary = entry.get('summary', '')

                        # Filter: Only include posts containing "ummatics" or "ummatic" (case insensitive)
                        # Check FULL summary first before trimming
                        combined_text = f"{title} {full_summary}".lower()
                        if 'ummatics' not in combined_text and 'ummatic' not in combined_text:
                            continue  # Skip posts that don't mention ummatics/ummatic

                        # Now trim content for storage (after filtering)
                        content = full_summary[:1000]

                        # Parse published date
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            posted_at = datetime(*entry.published_parsed[:6])
                        else:
                            posted_at = datetime.now()

                        # Reddit RSS doesn't provide engagement metrics, so we set them to 0
                        # In the future, you could scrape these or use an API
                        upvotes = 0
                        comments = 0

                        # Analyze sentiment using TextBlob (fast, low memory)
                        sentiment_text = f"{title} {content}"
                        sentiment, sentiment_score = analyze_sentiment_textblob(sentiment_text)

                        # Add small delay every 5 posts to avoid overloading
                        if (entry_index + 1) % 5 == 0:
                            time.sleep(0.5)  # 500ms delay

                        # Insert Reddit mention
                        cur.execute("""
                            INSERT INTO social_mentions
                            (week_start_date, platform, post_id, author, content, post_url, posted_at,
                             likes, retweets, replies, sentiment, sentiment_score, sentiment_analyzed_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (post_id) DO NOTHING
                        """, (monday, 'Reddit', post_id, author, content, post_url, posted_at,
                              upvotes, 0, comments, sentiment, sentiment_score, datetime.now()))

                        if cur.rowcount > 0:
                            total_new_mentions += 1
                            if posted_at.date() == today:
                                total_mentions_today += 1

                    except Exception as e:
                        logger.error(f"Error processing Reddit entry: {e}")
                        continue

                # Log progress
                logger.info(f"Processed {len(feed.entries)} entries from {rss_url}")

                # Add delay between feeds to avoid rate limiting
                if feed_index < len(REDDIT_RSS_URLS) - 1:
                    time.sleep(2)  # 2 second delay between feeds

            except Exception as e:
                logger.error(f"Error fetching Reddit RSS feed {rss_url}: {e}")
                continue

        # Update daily metrics for Reddit
        if total_mentions_today > 0:
            cur.execute("""
                INSERT INTO social_media_daily_metrics (date, platform, follower_count, mentions_count, engagement_rate)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (date, platform)
                DO UPDATE SET
                    mentions_count = EXCLUDED.mentions_count,
                    engagement_rate = EXCLUDED.engagement_rate
            """, (today, 'Reddit', 0, total_mentions_today, 0.0))

        # Update sentiment metrics for Reddit
        if total_new_mentions > 0:
            update_sentiment_metrics(today, 'Reddit')

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Reddit ingestion complete. New mentions: {total_new_mentions}")

    except Exception as e:
        logger.error(f"Error in Reddit ingestion: {e}")


def get_twitter_user_info(username):
    """Fetch Twitter user information including follower count"""
    if not TWITTER_BEARER_TOKEN:
        return None
    
    try:
        user_url = f"https://api.twitter.com/2/users/by/username/{username}"
        headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
        params = {"user.fields": "public_metrics"}
        
        response = requests.get(user_url, headers=headers, params=params)
        
        # Handle rate limiting gracefully
        if response.status_code == 429:
            logger.warning(f"Twitter API rate limit exceeded for user lookup: {username}")
            logger.info("Rate limit will reset in ~15 minutes.")
            return None
        
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data:
            return data['data']
        return None
        
    except Exception as e:
        logger.error(f"Error fetching Twitter user info: {e}")
        return None


def ingest_twitter():
    """Fetch Twitter mentions and metrics"""
    logger.info("Starting Twitter ingestion...")
    
    if not TWITTER_BEARER_TOKEN:
        logger.warning("Twitter Bearer Token not configured")
        return
    
    try:
        monday, sunday = get_current_week_dates()
        today = datetime.now().date()
        
        # Check if we already have a follower count from today (cache)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT follower_count, created_at::date 
            FROM social_media_daily_metrics 
            WHERE platform = 'Twitter' 
            AND date = %s
        """, (today,))
        result = cur.fetchone()
        
        follower_count = 0
        fetch_new_follower_count = True
        
        # If we have a record from today, reuse the cached follower count
        if result and result[1] == today:
            follower_count = result[0]
            fetch_new_follower_count = False
            logger.info(f"Using cached follower count from today: {follower_count}")
        
        # Get existing tweet IDs from database to avoid duplicates
        cur.execute("""
            SELECT post_id FROM social_mentions 
            WHERE platform = 'Twitter'
        """)
        existing_tweet_ids = set(row[0] for row in cur.fetchall())
        logger.info(f"Found {len(existing_tweet_ids)} existing tweets in database")
        
        cur.close()
        conn.close()
        
        # Only fetch follower count if we don't have one from today
        if fetch_new_follower_count:
            ummatics_user = get_twitter_user_info("ummatics")
            if ummatics_user and 'public_metrics' in ummatics_user:
                follower_count = ummatics_user['public_metrics'].get('followers_count', 0)
                logger.info(f"Fetched new follower count from API: {follower_count}")
            else:
                logger.warning("Could not fetch follower count from API, using 0 or cached value")
                if result:
                    follower_count = result[0]
                    logger.info(f"Using previous follower count: {follower_count}")
        else:
            logger.info("Skip fetching folllower count since we have one from today...")
        
        # Search for mentions using multiple search terms (case-insensitive by default in Twitter API)
        # Twitter API search is case-insensitive by default, but we'll include variations for clarity
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
        
        params = {
            "query": "(Ummatics OR ummatics OR Ummatic OR ummatic OR @ummatics) -from:ummatics",
            "max_results": 100,
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username"
        }
        
        response = requests.get(search_url, headers=headers, params=params)
        
        # Handle rate limiting gracefully
        if response.status_code == 429:
            logger.warning("Twitter API rate limit exceeded. Saving follower count only.")
            logger.info("Rate limit will reset in ~15 minutes. Mentions will be collected in next run.")
            # Still save follower count even if we can't get mentions
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO social_media_daily_metrics (date, platform, follower_count, mentions_count, engagement_rate)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (date, platform) 
                DO UPDATE SET 
                    follower_count = EXCLUDED.follower_count
            """, (today, 'Twitter', follower_count, 0, 0))
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Twitter follower count saved: {follower_count}")
            return
        
        response.raise_for_status()
        data = response.json()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        new_mentions = 0
        skipped_duplicates = 0
        skipped_own_posts = 0
        total_engagement = 0
        
        if 'data' in data:
            users = {user['id']: user for user in data.get('includes', {}).get('users', [])}
            
            for tweet in data['data']:
                try:
                    tweet_id = tweet['id']
                    author_id = tweet.get('author_id', '')
                    author_username = users.get(author_id, {}).get('username', 'Unknown')
                    
                    # Skip if this is a post from @ummatics itself
                    if author_username.lower() == 'ummatics':
                        skipped_own_posts += 1
                        logger.debug(f"Skipping own post: {tweet_id}")
                        continue
                    
                    # Skip if we already have this tweet in the database
                    if tweet_id in existing_tweet_ids:
                        skipped_duplicates += 1
                        logger.debug(f"Skipping duplicate tweet: {tweet_id}")
                        continue
                    
                    content = tweet.get('text', '')
                    post_url = f"https://twitter.com/{author_username}/status/{tweet_id}"
                    posted_at = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                    
                    metrics = tweet.get('public_metrics', {})
                    likes = metrics.get('like_count', 0)
                    retweets = metrics.get('retweet_count', 0)
                    replies = metrics.get('reply_count', 0)
                    
                    total_engagement += likes + retweets + replies
                    
                    # Analyze sentiment using TextBlob (fast, low memory)
                    sentiment, sentiment_score = analyze_sentiment_textblob(content)
                    
                    # Insert social mention
                    cur.execute("""
                        INSERT INTO social_mentions 
                        (week_start_date, platform, post_id, author, content, post_url, posted_at, likes, retweets, replies, sentiment, sentiment_score, sentiment_analyzed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (post_id) DO NOTHING
                    """, (monday, 'Twitter', tweet_id, author_username, content, post_url, posted_at, likes, retweets, replies, sentiment, sentiment_score, datetime.now()))
                    
                    if cur.rowcount > 0:
                        new_mentions += 1
                        logger.info(f"Added new mention from @{author_username}: {tweet_id} (sentiment: {sentiment})")
                        
                except Exception as e:
                    logger.error(f"Error processing tweet: {e}")
                    continue
        
        engagement_rate = (total_engagement / max(new_mentions, 1)) if new_mentions > 0 else 0
        
        # Update social media daily metrics
        cur.execute("""
            INSERT INTO social_media_daily_metrics (date, platform, follower_count, mentions_count, engagement_rate)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (date, platform) 
            DO UPDATE SET 
                follower_count = EXCLUDED.follower_count,
                mentions_count = EXCLUDED.mentions_count,
                engagement_rate = EXCLUDED.engagement_rate
        """, (today, 'Twitter', follower_count, new_mentions, engagement_rate))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Update sentiment metrics for today
        update_sentiment_metrics(today)
        
        logger.info(f"Twitter ingestion complete. New mentions: {new_mentions}, Followers: {follower_count}")
        logger.info(f"Skipped {skipped_duplicates} duplicates and {skipped_own_posts} own posts")
        
    except Exception as e:
        logger.error(f"Error in Twitter ingestion: {e}")


def ingest_google_analytics():
    """Fetch Google Analytics 4 data"""
    logger.info("Starting Google Analytics ingestion...")
    
    if not GA4_PROPERTY_ID:
        logger.warning("GA4 Property ID not configured")
        return
    
    try:
        # Initialize GA4 client
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            client = BetaAnalyticsDataClient(credentials=credentials)
        else:
            logger.warning("Google service account credentials not found")
            return
        
        monday, sunday = get_current_week_dates()
        
        # Request basic metrics
        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=monday.isoformat(), end_date=sunday.isoformat())],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="screenPageViews"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
            ],
        )
        
        response = client.run_report(request)
        
        if response.rows:
            row = response.rows[0]
            sessions = int(row.metric_values[0].value)
            users = int(row.metric_values[1].value)
            pageviews = int(row.metric_values[2].value)
            avg_duration = float(row.metric_values[3].value)
            bounce_rate = float(row.metric_values[4].value)
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Insert website metrics
            cur.execute("""
                INSERT INTO website_metrics 
                (week_start_date, total_sessions, total_users, total_pageviews, avg_session_duration, bounce_rate)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (week_start_date) 
                DO UPDATE SET 
                    total_sessions = EXCLUDED.total_sessions,
                    total_users = EXCLUDED.total_users,
                    total_pageviews = EXCLUDED.total_pageviews,
                    avg_session_duration = EXCLUDED.avg_session_duration,
                    bounce_rate = EXCLUDED.bounce_rate
            """, (monday, sessions, users, pageviews, avg_duration, bounce_rate))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Google Analytics ingestion complete. Sessions: {sessions}, Users: {users}")
        
        # Fetch top pages
        request_pages = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=monday.isoformat(), end_date=sunday.isoformat())],
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="averageSessionDuration"),
            ],
            limit=10,
        )
        
        response_pages = client.run_report(request_pages)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        for row in response_pages.rows:
            page_path = row.dimension_values[0].value
            pageviews = int(row.metric_values[0].value)
            avg_time = float(row.metric_values[1].value)
            
            cur.execute("""
                INSERT INTO top_pages (week_start_date, page_path, pageviews, avg_time_on_page)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (week_start_date, page_path) 
                DO UPDATE SET 
                    pageviews = EXCLUDED.pageviews,
                    avg_time_on_page = EXCLUDED.avg_time_on_page
            """, (monday, page_path, pageviews, avg_time))
        
        # Fetch geographic data
        request_geo = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=monday.isoformat(), end_date=sunday.isoformat())],
            dimensions=[Dimension(name="country")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
            ],
            limit=20,
        )
        
        response_geo = client.run_report(request_geo)
        
        for row in response_geo.rows:
            country = row.dimension_values[0].value
            sessions = int(row.metric_values[0].value)
            users = int(row.metric_values[1].value)
            
            cur.execute("""
                INSERT INTO geographic_metrics (week_start_date, country, sessions, users)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (week_start_date, country) 
                DO UPDATE SET 
                    sessions = EXCLUDED.sessions,
                    users = EXCLUDED.users
            """, (monday, country, sessions, users))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in Google Analytics ingestion: {e}")


def ingest_openalex():
    """Fetch citation data from OpenAlex API"""
    logger.info("Starting OpenAlex ingestion...")
    
    try:
        monday, sunday = get_current_week_dates()
        
        # Search for works mentioning "ummatics" or "ummatic" in title, abstract, or full text
        base_url = "https://api.openalex.org/works"
        headers = {"User-Agent": f"mailto:{CONTACT_EMAIL}"}
        
        # Search parameters - looking for mentions of ummatics or ummatic
        params = {
            "filter": "default.search:ummatics|ummatic",
            "per_page": 200,
            "sort": "cited_by_count:desc"
        }
        
        logger.info("Searching OpenAlex for works mentioning 'ummatics' or 'ummatic'...")
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        works_found = len(data.get('results', []))
        logger.info(f"Found {works_found} works in OpenAlex")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        total_citations = 0
        works_count = 0
        new_works = 0
        updated_works = 0
        
        for work in data.get('results', []):
            try:
                work_id = work['id']
                doi = work.get('doi', '')
                title = work.get('title', 'Untitled')
                
                # Extract authors
                authors_list = work.get('authorships', [])
                authors = ', '.join([a.get('author', {}).get('display_name', '') for a in authors_list[:5]])
                if len(authors_list) > 5:
                    authors += ' et al.'
                
                publication_date = work.get('publication_date')
                if publication_date:
                    try:
                        publication_date = datetime.fromisoformat(publication_date).date()
                    except:
                        publication_date = None
                
                cited_by_count = work.get('cited_by_count', 0)
                total_citations += cited_by_count
                works_count += 1
                
                source_url = f"https://openalex.org/{work_id.split('/')[-1]}"
                
                # Check if work already exists
                cur.execute("SELECT work_id FROM citations WHERE work_id = %s", (work_id,))
                exists = cur.fetchone()
                
                # Insert or update citation
                cur.execute("""
                    INSERT INTO citations (work_id, doi, title, authors, publication_date, cited_by_count, source_url, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (work_id) 
                    DO UPDATE SET 
                        cited_by_count = EXCLUDED.cited_by_count,
                        updated_at = EXCLUDED.updated_at
                    RETURNING (xmax = 0) AS inserted
                """, (work_id, doi, title, authors, publication_date, cited_by_count, source_url, datetime.now()))
                
                result = cur.fetchone()
                if result and result[0]:
                    new_works += 1
                    logger.info(f"New work added: {title[:60]}... (citations: {cited_by_count})")
                else:
                    updated_works += 1
                    
            except Exception as e:
                logger.error(f"Error processing OpenAlex work: {e}")
                continue
        
        # Calculate new citations this week (simplified - compare with previous week)
        cur.execute("""
            SELECT total_citations FROM citation_metrics 
            WHERE week_start_date < %s
            ORDER BY week_start_date DESC 
            LIMIT 1
        """, (monday,))
        result = cur.fetchone()
        previous_total = result[0] if result else 0
        new_citations = max(0, total_citations - previous_total)
        
        # Insert citation metrics
        cur.execute("""
            INSERT INTO citation_metrics (week_start_date, total_citations, new_citations_this_week, total_works)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (week_start_date) 
            DO UPDATE SET 
                total_citations = EXCLUDED.total_citations,
                new_citations_this_week = EXCLUDED.new_citations_this_week,
                total_works = EXCLUDED.total_works
        """, (monday, total_citations, new_citations, works_count))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"OpenAlex ingestion complete:")
        logger.info(f"  - Total citations: {total_citations}")
        logger.info(f"  - Total works: {works_count}")
        logger.info(f"  - New works: {new_works}")
        logger.info(f"  - Updated works: {updated_works}")
        logger.info(f"  - New citations this week: {new_citations}")
        
    except Exception as e:
        logger.error(f"Error in OpenAlex ingestion: {e}")
        import traceback
        logger.error(traceback.format_exc())


def update_weekly_snapshot():
    """Update the weekly snapshot with aggregated data"""
    logger.info("Updating weekly snapshot...")
    
    try:
        monday, sunday = get_current_week_dates()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Count news mentions
        cur.execute("""
            SELECT COUNT(*) FROM news_mentions WHERE week_start_date = %s
        """, (monday,))
        news_count = cur.fetchone()[0]
        
        # Count social mentions
        cur.execute("""
            SELECT COUNT(*) FROM social_mentions WHERE week_start_date = %s
        """, (monday,))
        social_count = cur.fetchone()[0]
        
        # Get total citations
        cur.execute("""
            SELECT total_citations FROM citation_metrics WHERE week_start_date = %s
        """, (monday,))
        result = cur.fetchone()
        citations_count = result[0] if result else 0
        
        # Get website sessions
        cur.execute("""
            SELECT total_sessions FROM website_metrics WHERE week_start_date = %s
        """, (monday,))
        result = cur.fetchone()
        sessions_count = result[0] if result else 0
        
        # Insert or update weekly snapshot
        cur.execute("""
            INSERT INTO weekly_snapshots 
            (week_start_date, week_end_date, total_news_mentions, total_social_mentions, 
             total_citations, total_website_sessions)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (week_start_date) 
            DO UPDATE SET 
                total_news_mentions = EXCLUDED.total_news_mentions,
                total_social_mentions = EXCLUDED.total_social_mentions,
                total_citations = EXCLUDED.total_citations,
                total_website_sessions = EXCLUDED.total_website_sessions
        """, (monday, sunday, news_count, social_count, citations_count, sessions_count))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Weekly snapshot updated for {monday} to {sunday}")
        
    except Exception as e:
        logger.error(f"Error updating weekly snapshot: {e}")


def update_reddit_rss_urls(new_subreddits):
    """
    Update REDDIT_RSS_URLS environment variable with new subreddits.
    This updates the .env file to persist the changes.
    """
    if not new_subreddits:
        return

    logger.info(f"Updating REDDIT_RSS_URLS with {len(new_subreddits)} new subreddits")

    try:
        # Read current .env file
        env_file = '/app/.env'
        if not os.path.exists(env_file):
            logger.warning(f".env file not found at {env_file}")
            return

        with open(env_file, 'r') as f:
            lines = f.readlines()

        # Find and update REDDIT_RSS_URLS line
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('REDDIT_RSS_URLS='):
                current_value = line.split('=', 1)[1].strip()
                # Add new subreddits
                new_urls = [f"https://www.reddit.com/r/{sub}/.rss" for sub in new_subreddits]
                if current_value:
                    updated_value = f"{current_value},{','.join(new_urls)}"
                else:
                    updated_value = ','.join(new_urls)
                lines[i] = f"REDDIT_RSS_URLS={updated_value}\n"
                updated = True
                break

        if updated:
            with open(env_file, 'w') as f:
                f.writelines(lines)
            logger.info("Successfully updated .env file with new subreddits")
        else:
            logger.warning("REDDIT_RSS_URLS not found in .env file")

    except Exception as e:
        logger.error(f"Error updating .env file: {e}")


def run_full_ingestion():
    """Run complete data ingestion from all sources"""
    logger.info("=" * 60)
    logger.info("Starting full data ingestion")
    logger.info("=" * 60)

    try:
        # Discover new subreddits first
        new_subreddits = discover_new_subreddits()
        if new_subreddits:
            update_reddit_rss_urls(new_subreddits)
            # Note: New subreddits will be used in next run after container restart

        ingest_google_alerts()
        ingest_reddit()
        ingest_twitter()
        ingest_google_analytics()
        ingest_openalex()
        update_weekly_snapshot()

        logger.info("=" * 60)
        logger.info("Full data ingestion completed successfully")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error in full ingestion: {e}")


if __name__ == "__main__":
    run_full_ingestion()
