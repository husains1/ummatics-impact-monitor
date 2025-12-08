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
from apify_client import ApifyClient
import html
from bs4 import BeautifulSoup
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
APIFY_API_TOKEN = os.getenv('APIFY_API_TOKEN', '')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')  # Used for follower count and fallback
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


def google_search_subreddits():
    """
    Use Google search to discover new subreddits mentioning 'ummatics' or 'ummatic'.
    This complements the existing Reddit RSS search with Google's more comprehensive indexing.
    Saves discovered subreddits to the database.
    
    Returns:
        list: List of newly discovered subreddit names
    """
    logger.info("Starting Google search for Reddit subreddits...")
    
    discovered_subreddits = set()
    
    try:
        # Construct Google search query to search Reddit
        query = 'site:reddit.com "ummatics" OR "ummatic"'
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=50"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        logger.info(f"Fetching Google search results: {search_url}")
        
        response = requests.get(search_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Google search failed with status code {response.status_code}")
            return []
        
        # Parse HTML response
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract links from search results
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Google wraps URLs in /url?q=...&sa=... format
            if '/url?q=' in href:
                match_url = re.search(r'/url\?q=(.*?)&', href)
                if match_url:
                    url = urllib.parse.unquote(match_url.group(1))
                    
                    # Extract subreddit name from Reddit URL
                    match_sub = re.search(r'reddit\.com/r/([a-zA-Z0-9_]+)/', url)
                    if match_sub:
                        subreddit = match_sub.group(1).lower()
                        if subreddit not in ['all', 'popular', 'announcements', 'reddit']:
                            discovered_subreddits.add(subreddit)
                            logger.info(f"Discovered subreddit from Google search: r/{subreddit}")
        
        # Get current subreddits from environment
        current_urls = os.getenv('REDDIT_RSS_URLS', '').split(',')
        current_subreddits = set()
        for url in current_urls:
            match = re.search(r'/r/([a-zA-Z0-9_]+)/', url)
            if match:
                current_subreddits.add(match.group(1).lower())
        
        # Check database for previously discovered subreddits
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT subreddit_name FROM discovered_subreddits")
        db_subreddits = set(row[0].lower() for row in cur.fetchall())
        
        # Find truly new subreddits (not in env or database)
        new_subreddits = discovered_subreddits - current_subreddits - db_subreddits
        
        if discovered_subreddits:
            logger.info(f"Total subreddits found via Google: {len(discovered_subreddits)}")
            logger.info(f"New subreddits (not already monitored): {len(new_subreddits)}")
            
            # Save all discovered subreddits to database
            for subreddit in discovered_subreddits:
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
            logger.info(f"Saved {len(discovered_subreddits)} subreddits to database")
        else:
            logger.info("No subreddits discovered via Google search")
        
        cur.close()
        conn.close()
        
        logger.info(f"Google subreddit discovery complete. New: {len(new_subreddits)}")
        return list(new_subreddits)
        
    except Exception as e:
        logger.error(f"Error in Google subreddit discovery: {e}")
        return []


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
                # Use more complete headers to avoid blocking
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
                req = urllib.request.Request(rss_url, headers=headers)
                response = urllib.request.urlopen(req, timeout=30)
                content = response.read()
                feed = feedparser.parse(content)

                logger.info(f"Found {len(feed.entries)} entries in feed")
                
                # Check if we got HTML error page instead of RSS
                if hasattr(feed, 'bozo') and feed.bozo:
                    logger.warning(f"Feed parsing error for {rss_url}: {feed.get('bozo_exception', 'Unknown error')}")
                    if len(feed.entries) == 0:
                        logger.error(f"No valid RSS entries found, possibly blocked or invalid URL")
                        continue

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

                        # Decode HTML entities and strip tags before trimming
                        # First decode HTML entities like &lt; &gt; &amp;
                        decoded_summary = html.unescape(full_summary)
                        # Then remove HTML tags
                        clean_summary = re.sub(r'<[^>]+>', '', decoded_summary)
                        # Now trim content for storage (after filtering and cleaning)
                        content = clean_summary[:1000]

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

        # Update daily metrics for Reddit (Reddit has no follower concept)
        if total_mentions_today > 0:
            cur.execute("""
                INSERT INTO social_media_daily_metrics (date, platform, mentions_count, engagement_rate)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (date, platform)
                DO UPDATE SET
                    mentions_count = EXCLUDED.mentions_count,
                    engagement_rate = EXCLUDED.engagement_rate
            """, (today, 'Reddit', total_mentions_today, 0.0))

        # Update sentiment metrics for Reddit
        if total_new_mentions > 0:
            update_sentiment_metrics(today, 'Reddit')

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Reddit ingestion complete. New mentions: {total_new_mentions}")

    except Exception as e:
        logger.error(f"Error in Reddit ingestion: {e}")


def ingest_twitter(max_tweets=100, days_back=None):
    """Fetch Twitter mentions using Twitter API (with fallback to Apify on error)
    
    Args:
        max_tweets: Maximum number of tweets to fetch (default: 100)
        days_back: If specified, fetch tweets from this many days ago (for historical backfill)
    """
    logger.info(f"Starting Twitter ingestion (max_tweets={max_tweets}, days_back={days_back})...")

    if not TWITTER_BEARER_TOKEN:
        logger.warning("Twitter Bearer Token not configured, skipping Twitter ingestion")
        return

    try:
        monday, sunday = get_current_week_dates()
        today = datetime.now().date()

        # Get existing tweet IDs from database to avoid duplicates
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT post_id FROM social_mentions 
            WHERE platform = 'Twitter'
        """)
        existing_tweet_ids = set(row[0] for row in cur.fetchall())
        logger.info(f"Found {len(existing_tweet_ids)} existing tweets in database")
        cur.close()
        conn.close()

        all_tweets = []

        # Try Twitter API first
        try:
            logger.info("Attempting to use Twitter API...")
            search_url = "https://api.twitter.com/2/tweets/search/recent"
            headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
            
            params = {
                "query": "(Ummatics OR ummatics OR Ummatic OR ummatic OR @ummatics) -from:ummatics",
                "max_results": min(max_tweets, 100),
                "tweet.fields": "created_at,public_metrics,author_id",
                "expansions": "author_id",
                "user.fields": "username"
            }
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if response.status_code == 429:
                logger.warning("Twitter API rate limit exceeded")
            elif response.status_code == 200:
                data = response.json()
                users = {user['id']: user for user in data.get('includes', {}).get('users', [])}
                
                for tweet in data.get('data', []):
                    # Convert Twitter API format to Apify-like format for consistent processing
                    author_id = tweet.get('author_id', '')
                    author_username = users.get(author_id, {}).get('username', 'Unknown')
                    
                    all_tweets.append({
                        'id': tweet['id'],
                        'text': tweet.get('text', ''),
                        'author': {'userName': author_username},
                        'createdAt': tweet.get('created_at', ''),
                        'url': f"https://twitter.com/{author_username}/status/{tweet['id']}",
                        'likeCount': tweet.get('public_metrics', {}).get('like_count', 0),
                        'retweetCount': tweet.get('public_metrics', {}).get('retweet_count', 0),
                        'replyCount': tweet.get('public_metrics', {}).get('reply_count', 0)
                    })
                
                logger.info(f"Twitter API returned {len(all_tweets)} tweets")
            else:
                logger.error(f"Twitter API error: {response.status_code} - {response.text}")
        
        except Exception as e:
            logger.warning(f"Twitter API error: {e}, falling back to Apify")

            if not APIFY_API_TOKEN:
                logger.warning("Apify API token not configured, skipping Apify fallback")
                return

            try:
                logger.info("Attempting to use Apify Twitter Scraper...")
                client = ApifyClient(APIFY_API_TOKEN)
                
                # Use quoted phrases for exact word matching (not substring)
                search_queries = [
                    '"ummatics" -from:ummatics',
                    '"ummatic" -from:ummatics'
                ]
                
                for search_query in search_queries:
                    logger.info(f"Searching Twitter via Apify for: {search_query}")
                    
                    run_input = {
                        "searchTerms": [search_query],
                        "maxItems": max_tweets,
                        "includeSearchTerms": False,
                        "onlyImage": False,
                        "onlyQuote": False,
                        "onlyTwitterBlue": False,
                        "onlyVerifiedUsers": False,
                        "onlyVideo": False,
                        "sort": "Latest",
                    }
                    
                    if days_back:
                        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                        end_date = datetime.now().strftime("%Y-%m-%d")
                        # Use 'since' and 'until' parameters for date filtering
                        run_input["since"] = start_date
                        run_input["until"] = end_date
                        logger.info(f"Fetching historical tweets from {start_date} to {end_date}")
                    
                    # Use timeout to prevent runaway scraping - accept whatever we get within time limit
                    run = client.actor("61RPP7dywgiy0JPD0").call(
                        run_input=run_input,
                        timeout_secs=120  # Abort after 2 minutes
                    )
                    
                    # Fetch all data from Apify dataset
                    dataset_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
                    logger.info(f"Apify dataset returned {len(dataset_items)} items for query: {search_query}")
                    
                    # IMMEDIATELY log full data to file BEFORE processing (so we don't lose data on errors)
                    if dataset_items:
                        import json
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        log_file = f"/app/apify_data_{timestamp}_{search_query.replace(' ', '_').replace('-', '_')}.json"
                        try:
                            with open(log_file, 'w') as f:
                                json.dump(dataset_items, f, indent=2, default=str)
                            logger.info(f"✓ Saved {len(dataset_items)} tweets to {log_file}")
                        except Exception as log_err:
                            logger.error(f"Failed to save Apify data to file: {log_err}")
                    
                    # Add to all_tweets list with strict filtering
                    for item in dataset_items:
                        # Even with quoted search, Apify can return fuzzy matches
                        # Apply strict word boundary check to filter out false positives
                        text = item.get('text', '').lower()
                        
                        # Check for exact word matches using word boundaries
                        import re
                        has_ummatics = bool(re.search(r'\bummatics\b', text, re.IGNORECASE))
                        has_ummatic = bool(re.search(r'\bummatic\b', text, re.IGNORECASE))
                        
                        if has_ummatics or has_ummatic:
                            all_tweets.append(item)
                        else:
                            logger.debug(f"Filtered out tweet {item.get('id', 'unknown')} - no exact match for 'ummatics' or 'ummatic'")
                
                logger.info(f"Apify returned {len(all_tweets)} total tweets")
                
            except Exception as apify_error:
                logger.error(f"Apify error: {apify_error}, unable to fetch Twitter mentions")
        
        # ALWAYS fetch follower count from Twitter API (not Apify)
        
        follower_count = 0
        if TWITTER_BEARER_TOKEN:
            try:
                user_url = "https://api.twitter.com/2/users/by/username/ummatics"
                headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
                params = {"user.fields": "public_metrics"}
                response = requests.get(user_url, headers=headers, params=params)
                
                if response.status_code == 200:
                    user_data = response.json()
                    if 'data' in user_data and 'public_metrics' in user_data['data']:
                        follower_count = user_data['data']['public_metrics'].get('followers_count', 0)
                        logger.info(f"Fetched follower count from Twitter API: {follower_count}")
                elif response.status_code == 429:
                    logger.warning("Twitter API rate limit for user lookup")
                else:
                    logger.warning(f"Could not fetch follower count: HTTP {response.status_code}")
            except Exception as e:
                logger.warning(f"Error fetching follower count from Twitter API: {e}")
        
        # Fallback to previous follower count if API fails
        if follower_count == 0:
            try:
                user_url = "https://api.twitter.com/2/users/by/username/ummatics"
                headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
                params = {"user.fields": "public_metrics"}
                response = requests.get(user_url, headers=headers, params=params)
                
                if response.status_code == 200:
                    user_data = response.json()
                    if 'data' in user_data and 'public_metrics' in user_data['data']:
                        follower_count = user_data['data']['public_metrics'].get('followers_count', 0)
                        logger.info(f"Fetched follower count from Twitter API: {follower_count}")
                elif response.status_code == 429:
                    logger.warning("Twitter API rate limit for user lookup")
                else:
                    logger.warning(f"Could not fetch follower count: HTTP {response.status_code}")
            except Exception as e:
                logger.warning(f"Error fetching follower count from Twitter API: {e}")
        
        # Fallback to previous follower count if API fails
        if follower_count == 0:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT follower_count FROM social_media_daily_metrics 
                WHERE platform = 'Twitter' 
                ORDER BY date DESC LIMIT 1
            """)
            result = cur.fetchone()
            if result and result[0] > 0:
                follower_count = result[0]
                logger.info(f"Using previous follower count: {follower_count}")
            cur.close()
            conn.close()
        
        # Process tweets and save to database
        conn = get_db_connection()
        cur = conn.cursor()
        
        new_mentions = 0
        skipped_duplicates = 0
        skipped_own_posts = 0
        total_engagement = 0
        
        for tweet in all_tweets:
            try:
                # Extract tweet data
                tweet_id = tweet.get('id', '')
                if not tweet_id:
                    continue
                
                # Get author info
                author_info = tweet.get('author', {})
                author_username = author_info.get('userName', 'Unknown')
                
                # Skip if this is from @ummatics itself (double check)
                if author_username.lower() == 'ummatics':
                    skipped_own_posts += 1
                    logger.debug(f"Skipping own post: {tweet_id}")
                    continue
                
                # Skip if we already have this tweet
                if tweet_id in existing_tweet_ids:
                    skipped_duplicates += 1
                    logger.debug(f"Skipping duplicate tweet: {tweet_id}")
                    continue
                
                # Extract tweet content and metadata
                content = tweet.get('text', '')
                post_url = tweet.get('url', f"https://twitter.com/{author_username}/status/{tweet_id}")
                
                # Parse created date - handle multiple formats
                created_at = tweet.get('createdAt', '')
                if created_at:
                    try:
                        # Try ISO format first (Apify format)
                        posted_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        try:
                            # Try Twitter's standard format: "Thu Mar 04 04:48:05 +0000 2010"
                            from datetime import datetime as dt
                            posted_at = dt.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                        except (ValueError, TypeError):
                            # Fallback to now if all parsing fails
                            logger.warning(f"Could not parse date '{created_at}' for tweet {tweet_id}, using current time")
                            posted_at = datetime.now()
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
                    logger.info(f"Added new mention from @{author_username}: {tweet_id} (sentiment: {sentiment})")
                    
            except Exception as e:
                logger.error(f"Error processing tweet: {e}")
                continue
        
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
        
        # Update sentiment metrics for today
        update_sentiment_metrics(today)
        
        logger.info(f"Twitter ingestion complete. New mentions: {new_mentions}, Followers: {follower_count}")
        logger.info(f"Skipped {skipped_duplicates} duplicates and {skipped_own_posts} own posts")
        
    except Exception as e:
        logger.error(f"Error in Twitter ingestion: {e}")
        import traceback
        logger.error(traceback.format_exc())


def cleanup_citations():
    """Clean up citations: check for dead URLs and remove duplicates"""
    logger.info("Starting citation cleanup...")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get all citations that aren't already marked as dead
        cur.execute("""
            SELECT id, source_url, title, authors, publication_date, created_at 
            FROM citations 
            WHERE is_dead = FALSE
            ORDER BY title, publication_date DESC, created_at DESC
        """)
        citations = cur.fetchall()
        
        dead_count = 0
        duplicate_count = 0
        checked_count = 0
        
        # Track seen titles to identify duplicates
        seen_titles = {}  # title -> (id, has_working_url, publication_date, created_at)
        
        for citation in citations:
            cit_id, source_url, title, authors, pub_date, created_at = citation
            checked_count += 1
            
            # Check if URL is accessible
            is_url_dead = False
            if source_url:
                try:
                    # Use HEAD request to check if URL exists (faster than GET)
                    # Use browser-like user agent to match actual user experience
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    response = requests.head(source_url, timeout=10, allow_redirects=True, headers=headers)
                    # Consider 4xx and 5xx status codes as dead
                    if response.status_code >= 400:
                        is_url_dead = True
                        logger.info(f"Dead URL (HTTP {response.status_code}): {source_url[:80]}")
                except Exception as e:
                    # Connection errors, timeouts, etc. also indicate dead URL
                    is_url_dead = True
                    logger.info(f"Dead URL (error: {str(e)[:50]}): {source_url[:80]}")
            else:
                # No URL means we can't verify it
                is_url_dead = True
            
            # Handle duplicates by title
            if title in seen_titles:
                prev_id, prev_has_working_url, prev_pub_date, prev_created = seen_titles[title]
                
                # Decide which one to keep:
                # 1. Prefer the one with a working URL
                # 2. If both working or both dead, keep the newer publication date
                # 3. If same pub date, keep the one created more recently
                
                keep_current = False
                if not is_url_dead and prev_has_working_url:
                    # Both working - keep newer pub date or newer created_at
                    keep_current = (pub_date, created_at) > (prev_pub_date, prev_created)
                elif is_url_dead and not prev_has_working_url:
                    # Both dead - keep newer pub date or newer created_at
                    keep_current = (pub_date, created_at) > (prev_pub_date, prev_created)
                elif not is_url_dead:
                    # Current has working URL, previous doesn't
                    keep_current = True
                # else: previous has working URL, current doesn't - keep previous
                
                if keep_current:
                    # Mark previous as duplicate (dead)
                    cur.execute("UPDATE citations SET is_dead = TRUE WHERE id = %s", (prev_id,))
                    duplicate_count += 1
                    logger.info(f"Marked duplicate as dead: {title[:60]}... (ID: {prev_id})")
                    # Update tracking
                    seen_titles[title] = (cit_id, not is_url_dead, pub_date, created_at)
                    # Mark current as dead if its URL is dead
                    if is_url_dead:
                        cur.execute("UPDATE citations SET is_dead = TRUE WHERE id = %s", (cit_id,))
                        dead_count += 1
                else:
                    # Mark current as duplicate (dead)
                    cur.execute("UPDATE citations SET is_dead = TRUE WHERE id = %s", (cit_id,))
                    duplicate_count += 1
                    logger.info(f"Marked duplicate as dead: {title[:60]}... (ID: {cit_id})")
            else:
                # First occurrence of this title
                seen_titles[title] = (cit_id, not is_url_dead, pub_date, created_at)
                # Mark as dead if URL is dead
                if is_url_dead:
                    cur.execute("UPDATE citations SET is_dead = TRUE WHERE id = %s", (cit_id,))
                    dead_count += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Citation cleanup complete:")
        logger.info(f"  - Checked {checked_count} citations")
        logger.info(f"  - Marked {dead_count} as dead (broken URLs)")
        logger.info(f"  - Marked {duplicate_count} as dead (duplicates)")
        logger.info(f"  - Total marked as dead: {dead_count + duplicate_count}")
        
    except Exception as e:
        logger.error(f"Error in citation cleanup: {e}")
        import traceback
        logger.error(traceback.format_exc())


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
                
                # Classify citation type: organization vs word usage
                # Check title, abstract, and display_name for ummatics.org references
                title_lower = title.lower() if title else ''
                abstract = work.get('abstract', '') or ''
                abstract_lower = abstract.lower() if abstract else ''
                display_name = work.get('display_name', '') or ''
                display_name_lower = display_name.lower() if display_name else ''
                
                citation_type = 'word'  # Default to word usage
                
                # Check for organization references
                org_indicators = [
                    'ummatics.org',
                    'ummatics organization',
                    'ummatics institute',
                    'ummatics foundation',
                    'ummatics research',
                    'ummatics journal'
                ]
                
                full_text = f"{title_lower} {abstract_lower} {display_name_lower}"
                for indicator in org_indicators:
                    if indicator in full_text:
                        citation_type = 'organization'
                        break
                
                # If it mentions "ummatics" (not just "ummatic"), more likely organization
                if citation_type == 'word' and 'ummatics' in full_text and 'ummatic' not in full_text.replace('ummatics', ''):
                    citation_type = 'organization'
                
                # Check if work already exists
                cur.execute("SELECT work_id FROM citations WHERE work_id = %s", (work_id,))
                exists = cur.fetchone()
                
                # Insert or update citation
                cur.execute("""
                    INSERT INTO citations (work_id, doi, title, authors, publication_date, cited_by_count, source_url, citation_type, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (work_id) 
                    DO UPDATE SET 
                        cited_by_count = EXCLUDED.cited_by_count,
                        citation_type = EXCLUDED.citation_type,
                        updated_at = EXCLUDED.updated_at
                    RETURNING (xmax = 0) AS inserted
                """, (work_id, doi, title, authors, publication_date, cited_by_count, source_url, citation_type, datetime.now()))
                
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
        ingest_openalex()
        update_weekly_snapshot()

        logger.info("=" * 60)
        logger.info("Full data ingestion completed successfully")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error in full ingestion: {e}")


if __name__ == "__main__":
    run_full_ingestion()
