import os
import psycopg2
from datetime import datetime, timedelta
import requests
import feedparser
import logging
import time
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
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', '')
TWITTER_USERNAME = os.getenv('TWITTER_USERNAME', 'ummatics')  # Twitter handle to track
GA4_PROPERTY_ID = os.getenv('GA4_PROPERTY_ID', '')
CONTACT_EMAIL = os.getenv('CONTACT_EMAIL', 'contact@ummatics.org')
OPENALEX_ROR_ID = os.getenv('OPENALEX_ROR_ID', '')  # Research Organization Registry ID

# API retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def get_db_connection():
    """Create database connection with error handling"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise


def get_current_week_dates():
    """Get the start and end dates of the current week (Monday to Sunday)"""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def make_api_request(url, headers=None, params=None, max_retries=MAX_RETRIES):
    """
    Make API request with retry logic
    
    Args:
        url: API endpoint URL
        headers: Request headers
        params: Query parameters
        max_retries: Maximum number of retry attempts
        
    Returns:
        Response object or None on failure
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit
                logger.warning(f"Rate limited, waiting {RETRY_DELAY * 2} seconds...")
                time.sleep(RETRY_DELAY * 2)
            else:
                logger.error(f"HTTP error: {e}")
                return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY)
    
    logger.error(f"Failed after {max_retries} attempts")
    return None


def ingest_google_alerts():
    """
    Fetch news mentions from Google Alerts RSS feed
    
    Collects:
    - Article title
    - URL
    - Source
    - Publication date
    - Snippet/summary
    """
    logger.info("Starting Google Alerts ingestion...")
    
    if not GOOGLE_ALERTS_RSS_URL:
        logger.warning("Google Alerts RSS URL not configured. Skipping.")
        return
    
    try:
        # Parse RSS feed
        feed = feedparser.parse(GOOGLE_ALERTS_RSS_URL)
        
        if not feed.entries:
            logger.warning("No entries found in Google Alerts feed")
            return
        
        monday, sunday = get_current_week_dates()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        new_mentions = 0
        duplicate_mentions = 0
        
        for entry in feed.entries:
            try:
                title = entry.get('title', '').strip()
                url = entry.get('link', '').strip()
                
                if not title or not url:
                    logger.warning("Entry missing title or URL, skipping")
                    continue
                
                # Extract source
                source = entry.get('source', {}).get('title', 'Unknown')
                if not source or source == 'Unknown':
                    # Try to extract from URL
                    try:
                        from urllib.parse import urlparse
                        source = urlparse(url).netloc
                    except:
                        source = 'Unknown'
                
                # Parse publication date
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_at = datetime(*entry.published_parsed[:6])
                else:
                    published_at = datetime.now()
                
                # Get snippet (limit to 500 characters)
                snippet = entry.get('summary', '')
                if snippet:
                    # Remove HTML tags if present
                    import re
                    snippet = re.sub('<[^<]+?>', '', snippet)[:500]
                
                # Insert news mention with deduplication
                cur.execute("""
                    INSERT INTO news_mentions (week_start_date, title, url, source, published_at, snippet)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url, title) DO NOTHING
                """, (monday, title, url, source, published_at, snippet))
                
                if cur.rowcount > 0:
                    new_mentions += 1
                    logger.debug(f"Added news mention: {title[:50]}...")
                else:
                    duplicate_mentions += 1
                    
            except Exception as e:
                logger.error(f"Error processing news entry '{entry.get('title', 'N/A')[:30]}...': {e}")
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Google Alerts ingestion complete. New: {new_mentions}, Duplicates: {duplicate_mentions}")
        
    except Exception as e:
        logger.error(f"Error in Google Alerts ingestion: {e}")


def ingest_twitter():
    """
    Fetch Twitter mentions and metrics
    
    Collects:
    - Mentions of Ummatics
    - Follower count for @ummatics account
    - Engagement metrics (likes, retweets, replies)
    - Weekly engagement rate
    """
    logger.info("Starting Twitter ingestion...")
    
    if not TWITTER_BEARER_TOKEN:
        logger.warning("Twitter Bearer Token not configured. Skipping.")
        return
    
    try:
        monday, sunday = get_current_week_dates()
        headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # ========== PART 1: Get Follower Count ==========
        follower_count = 0
        try:
            logger.info(f"Fetching follower count for @{TWITTER_USERNAME}...")
            user_url = f"https://api.twitter.com/2/users/by/username/{TWITTER_USERNAME}"
            user_params = {"user.fields": "public_metrics"}
            
            user_response = make_api_request(user_url, headers=headers, params=user_params)
            
            if user_response and user_response.status_code == 200:
                user_data = user_response.json()
                if 'data' in user_data and 'public_metrics' in user_data['data']:
                    follower_count = user_data['data']['public_metrics'].get('followers_count', 0)
                    logger.info(f"Current follower count: {follower_count:,}")
                else:
                    logger.warning("Could not extract follower count from response")
            else:
                logger.warning(f"Failed to fetch follower count for @{TWITTER_USERNAME}")
        
        except Exception as e:
            logger.error(f"Error fetching Twitter follower count: {e}")
        
        # ========== PART 2: Search for Mentions ==========
        logger.info("Searching for Ummatics mentions...")
        search_url = "https://api.twitter.com/2/tweets/search/recent"
        
        search_params = {
            "query": f"Ummatics OR @{TWITTER_USERNAME} -is:retweet",  # Exclude retweets
            "max_results": 100,
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username,name"
        }
        
        search_response = make_api_request(search_url, headers=headers, params=search_params)
        
        new_mentions = 0
        total_engagement = 0
        
        if search_response and search_response.status_code == 200:
            data = search_response.json()
            
            if 'data' in data and data['data']:
                # Create user lookup dictionary
                users = {}
                if 'includes' in data and 'users' in data['includes']:
                    users = {user['id']: user for user in data['includes']['users']}
                
                for tweet in data['data']:
                    try:
                        tweet_id = tweet['id']
                        author_id = tweet.get('author_id', '')
                        
                        # Get author information
                        author_info = users.get(author_id, {})
                        author_username = author_info.get('username', 'Unknown')
                        author_name = author_info.get('name', 'Unknown')
                        
                        content = tweet.get('text', '')
                        post_url = f"https://twitter.com/{author_username}/status/{tweet_id}"
                        
                        # Parse timestamp
                        created_at_str = tweet.get('created_at', '')
                        if created_at_str:
                            posted_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        else:
                            posted_at = datetime.now()
                        
                        # Extract engagement metrics
                        metrics = tweet.get('public_metrics', {})
                        likes = metrics.get('like_count', 0)
                        retweets = metrics.get('retweet_count', 0)
                        replies = metrics.get('reply_count', 0)
                        
                        total_engagement += likes + retweets + replies
                        
                        # Insert social mention with deduplication
                        cur.execute("""
                            INSERT INTO social_mentions 
                            (week_start_date, platform, post_id, author, content, post_url, posted_at, likes, retweets, replies)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (post_id) DO NOTHING
                        """, (monday, 'Twitter', tweet_id, author_username, content, post_url, posted_at, likes, retweets, replies))
                        
                        if cur.rowcount > 0:
                            new_mentions += 1
                            logger.debug(f"Added mention from @{author_username}: {content[:40]}...")
                            
                    except Exception as e:
                        logger.error(f"Error processing tweet {tweet.get('id', 'N/A')}: {e}")
                        continue
                
                logger.info(f"Processed {new_mentions} new Twitter mentions")
            else:
                logger.info("No new Twitter mentions found")
        else:
            logger.warning("Failed to fetch Twitter mentions")
        
        # ========== PART 3: Calculate and Store Metrics ==========
        # Calculate average engagement rate
        engagement_rate = round(total_engagement / max(new_mentions, 1), 2) if new_mentions > 0 else 0.0
        
        # Update social media metrics
        cur.execute("""
            INSERT INTO social_media_metrics (week_start_date, platform, follower_count, mentions_count, engagement_rate)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (week_start_date, platform) 
            DO UPDATE SET 
                follower_count = EXCLUDED.follower_count,
                mentions_count = EXCLUDED.mentions_count,
                engagement_rate = EXCLUDED.engagement_rate
        """, (monday, 'Twitter', follower_count, new_mentions, engagement_rate))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Twitter ingestion complete. Followers: {follower_count:,}, Mentions: {new_mentions}, Engagement Rate: {engagement_rate}")
        
    except Exception as e:
        logger.error(f"Error in Twitter ingestion: {e}")


def ingest_google_analytics():
    """
    Fetch Google Analytics 4 data
    
    Collects:
    - Sessions, users, pageviews
    - New vs returning visitors
    - Average session duration
    - Bounce rate
    - Top pages
    - Geographic distribution
    """
    logger.info("Starting Google Analytics ingestion...")
    
    if not GA4_PROPERTY_ID:
        logger.warning("GA4 Property ID not configured. Skipping.")
        return
    
    try:
        # Initialize GA4 client
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not credentials_path or not os.path.exists(credentials_path):
            logger.warning("Google service account credentials not found. Skipping GA4.")
            return
        
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        client = BetaAnalyticsDataClient(credentials=credentials)
        
        monday, sunday = get_current_week_dates()
        
        # ========== PART 1: Basic Website Metrics ==========
        logger.info("Fetching basic website metrics...")
        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=monday.isoformat(), end_date=sunday.isoformat())],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="newUsers"),  # NEW: Track new visitors
                Metric(name="screenPageViews"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
            ],
        )
        
        response = client.run_report(request)
        
        if response.rows:
            row = response.rows[0]
            sessions = int(row.metric_values[0].value)
            total_users = int(row.metric_values[1].value)
            new_users = int(row.metric_values[2].value)  # NEW
            pageviews = int(row.metric_values[3].value)
            avg_duration = float(row.metric_values[4].value)
            bounce_rate = float(row.metric_values[5].value)
            
            # Calculate returning users
            returning_users = total_users - new_users
            
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
            """, (monday, sessions, total_users, pageviews, avg_duration, bounce_rate))
            
            logger.info(f"Website metrics - Sessions: {sessions:,}, Users: {total_users:,} (New: {new_users:,}, Returning: {returning_users:,})")
        else:
            logger.warning("No website metrics data returned from GA4")
            return
        
        # ========== PART 2: Top Pages ==========
        logger.info("Fetching top pages...")
        request_pages = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=monday.isoformat(), end_date=sunday.isoformat())],
            dimensions=[Dimension(name="pagePath")],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="averageSessionDuration"),
            ],
            limit=20,  # Get top 20 pages
        )
        
        response_pages = client.run_report(request_pages)
        
        pages_count = 0
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
            pages_count += 1
        
        logger.info(f"Stored {pages_count} top pages")
        
        # ========== PART 3: Geographic Distribution ==========
        logger.info("Fetching geographic data...")
        request_geo = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=monday.isoformat(), end_date=sunday.isoformat())],
            dimensions=[Dimension(name="country")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
            ],
            limit=30,  # Get top 30 countries
        )
        
        response_geo = client.run_report(request_geo)
        
        countries_count = 0
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
            countries_count += 1
        
        logger.info(f"Stored {countries_count} countries")
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("Google Analytics ingestion complete")
        
    except Exception as e:
        logger.error(f"Error in Google Analytics ingestion: {e}")
        import traceback
        logger.error(traceback.format_exc())


def ingest_openalex():
    """
    Fetch citation data from OpenAlex API
    
    Collects:
    - Academic works and publications
    - Citation counts
    - Author information
    - Publication dates
    - DOI links
    """
    logger.info("Starting OpenAlex ingestion...")
    
    try:
        base_url = "https://api.openalex.org/works"
        headers = {"User-Agent": f"mailto:{CONTACT_EMAIL}"}
        
        # Determine search method
        if OPENALEX_ROR_ID:
            # Search by institution ROR ID
            search_filter = f"institutions.ror:{OPENALEX_ROR_ID}"
            logger.info(f"Searching OpenAlex by ROR ID: {OPENALEX_ROR_ID}")
        else:
            # Fallback: Search by organization name in affiliations
            search_filter = "affiliations.display_name:Ummatics"
            logger.info("Searching OpenAlex by affiliation name: Ummatics")
            logger.warning("Consider setting OPENALEX_ROR_ID environment variable for more accurate results")
        
        params = {
            "filter": search_filter,
            "per_page": 200,
            "sort": "cited_by_count:desc"
        }
        
        response = make_api_request(base_url, headers=headers, params=params)
        
        if not response or response.status_code != 200:
            logger.error("Failed to fetch data from OpenAlex API")
            return
        
        data = response.json()
        
        if 'results' not in data or not data['results']:
            logger.warning("No results found in OpenAlex. Check your ROR ID or search criteria.")
            return
        
        monday, sunday = get_current_week_dates()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        total_citations = 0
        works_count = 0
        
        for work in data['results']:
            try:
                work_id = work.get('id', '')
                if not work_id:
                    continue
                
                doi = work.get('doi', '').replace('https://doi.org/', '') if work.get('doi') else None
                title = work.get('title', 'Untitled')
                
                # Extract authors (first 5)
                authors_list = work.get('authorships', [])
                authors = ', '.join([
                    a.get('author', {}).get('display_name', 'Unknown') 
                    for a in authors_list[:5]
                ])
                
                # Parse publication date
                publication_date = None
                if work.get('publication_date'):
                    try:
                        publication_date = datetime.fromisoformat(work['publication_date']).date()
                    except:
                        pass
                
                cited_by_count = work.get('cited_by_count', 0)
                total_citations += cited_by_count
                works_count += 1
                
                # Generate source URL
                source_url = work_id  # OpenAlex IDs are URLs
                if not source_url.startswith('http'):
                    source_url = f"https://openalex.org/{work_id.split('/')[-1]}"
                
                # Insert or update citation
                cur.execute("""
                    INSERT INTO citations (work_id, doi, title, authors, publication_date, cited_by_count, source_url, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (work_id) 
                    DO UPDATE SET 
                        cited_by_count = EXCLUDED.cited_by_count,
                        updated_at = EXCLUDED.updated_at
                """, (work_id, doi, title, authors, publication_date, cited_by_count, source_url, datetime.now()))
                
                logger.debug(f"Processed work: {title[:50]}... (Citations: {cited_by_count})")
                
            except Exception as e:
                logger.error(f"Error processing OpenAlex work: {e}")
                continue
        
        # Calculate new citations this week
        cur.execute("""
            SELECT total_citations FROM citation_metrics 
            ORDER BY week_start_date DESC LIMIT 1
        """)
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
        
        logger.info(f"OpenAlex ingestion complete. Works: {works_count}, Total Citations: {total_citations:,}, New This Week: {new_citations}")
        
    except Exception as e:
        logger.error(f"Error in OpenAlex ingestion: {e}")
        import traceback
        logger.error(traceback.format_exc())


def update_weekly_snapshot():
    """
    Update the weekly snapshot with aggregated data from all sources
    
    Consolidates:
    - News mentions count
    - Social mentions count
    - Total citations
    - Website sessions
    """
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
        logger.info(f"  News: {news_count}, Social: {social_count}, Citations: {citations_count}, Sessions: {sessions_count}")
        
    except Exception as e:
        logger.error(f"Error updating weekly snapshot: {e}")


def validate_configuration():
    """
    Validate that required configuration is present
    
    Returns:
        dict: Configuration status for each data source
    """
    logger.info("Validating configuration...")
    
    config_status = {
        'google_alerts': bool(GOOGLE_ALERTS_RSS_URL),
        'twitter': bool(TWITTER_BEARER_TOKEN),
        'google_analytics': bool(GA4_PROPERTY_ID and os.getenv('GOOGLE_APPLICATION_CREDENTIALS')),
        'openalex': True,  # No API key required
        'database': True  # Assumed if we got this far
    }
    
    for source, configured in config_status.items():
        status = "✓ Configured" if configured else "✗ Not configured"
        logger.info(f"  {source.replace('_', ' ').title()}: {status}")
    
    if not any(config_status.values()):
        logger.error("No data sources are configured! Please check your environment variables.")
        return config_status
    
    return config_status


def run_full_ingestion():
    """
    Run complete data ingestion from all sources
    
    Process:
    1. Validate configuration
    2. Collect data from all configured sources
    3. Update weekly aggregations
    4. Log summary
    """
    logger.info("=" * 70)
    logger.info(" " * 20 + "UMMATICS IMPACT MONITOR")
    logger.info(" " * 22 + "Data Ingestion Process")
    logger.info("=" * 70)
    
    start_time = datetime.now()
    
    # Validate configuration
    config_status = validate_configuration()
    
    try:
        # Run ingestion for each configured source
        logger.info("-" * 70)
        
        if config_status['google_alerts']:
            ingest_google_alerts()
        else:
            logger.info("Skipping Google Alerts (not configured)")
        
        logger.info("-" * 70)
        
        if config_status['twitter']:
            ingest_twitter()
        else:
            logger.info("Skipping Twitter (not configured)")
        
        logger.info("-" * 70)
        
        if config_status['google_analytics']:
            ingest_google_analytics()
        else:
            logger.info("Skipping Google Analytics (not configured)")
        
        logger.info("-" * 70)
        
        if config_status['openalex']:
            ingest_openalex()
        else:
            logger.info("Skipping OpenAlex (disabled)")
        
        logger.info("-" * 70)
        
        # Update weekly snapshot
        update_weekly_snapshot()
        
        # Calculate duration
        duration = datetime.now() - start_time
        
        logger.info("=" * 70)
        logger.info(f"Full data ingestion completed successfully in {duration.total_seconds():.1f} seconds")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Error in full ingestion: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    run_full_ingestion()
