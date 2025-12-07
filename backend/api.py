import os
import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timedelta, date
from decimal import Decimal
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom JSON encoder for dates and decimals
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

app = Flask(__name__)
app.json_encoder = DateTimeEncoder
CORS(app)

# Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'ummatics_monitor'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'changeme')


def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise


def require_auth(f):
    """Decorator to require password authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f"Bearer {DASHBOARD_PASSWORD}":
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_current_week_dates():
    """Get the start and end dates of the current week (Monday to Sunday)"""
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


@app.route('/api/auth', methods=['POST'])
def authenticate():
    """Authenticate user with password"""
    data = request.get_json()
    password = data.get('password', '')
    
    if password == DASHBOARD_PASSWORD:
        return jsonify({'success': True, 'token': DASHBOARD_PASSWORD})
    else:
        return jsonify({'success': False, 'error': 'Invalid password'}), 401


@app.route('/api/overview', methods=['GET'])
@require_auth
def get_overview():
    """Get overview data for the dashboard with enhanced content"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get last 12 weeks of data
        cur.execute("""
            SELECT 
                week_start_date,
                total_news_mentions,
                total_social_mentions,
                total_citations
            FROM weekly_snapshots
            ORDER BY week_start_date DESC
            LIMIT 12
        """)
        weekly_data = cur.fetchall()
        
        # Get current week totals
        monday, sunday = get_current_week_dates()
        cur.execute("""
            SELECT 
                COALESCE(total_news_mentions, 0) as news_mentions,
                COALESCE(total_social_mentions, 0) as social_mentions,
                COALESCE(total_citations, 0) as citations
            FROM weekly_snapshots
            WHERE week_start_date = %s
        """, (monday,))
        current_week = cur.fetchone()
        
        if not current_week:
            current_week = {
                'news_mentions': 0,
                'social_mentions': 0,
                'citations': 0
            }
        
        # Get recent mentions (last 10 from all platforms)
        cur.execute("""
            SELECT 
                TO_CHAR(posted_at, 'YYYY-MM-DD')::TEXT as date,
                platform,
                content as text,
                author,
                post_url as url,
                (COALESCE(likes, 0) + COALESCE(retweets, 0) + COALESCE(replies, 0)) as engagement_score
            FROM social_mentions
            ORDER BY posted_at DESC
            LIMIT 10
        """)
        recent_mentions = cur.fetchall()
        
        # Get platform breakdown for current week
        cur.execute("""
            SELECT 
                platform,
                COUNT(*) as mention_count
            FROM social_mentions
            WHERE week_start_date = %s
            GROUP BY platform
            ORDER BY mention_count DESC
        """, (monday,))
        platform_breakdown = cur.fetchall()
        
        # Get sentiment summary for current week
        cur.execute("""
            SELECT 
                platform,
                COALESCE(AVG(sentiment_score), 0) as avg_sentiment,
                COALESCE(AVG(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) * 100, 0) as positive_pct,
                COALESCE(AVG(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) * 100, 0) as neutral_pct,
                COALESCE(AVG(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) * 100, 0) as negative_pct
            FROM social_sentiment_metrics
            WHERE date >= %s AND date <= %s
            GROUP BY platform
        """, (monday, sunday))
        sentiment_summary = cur.fetchall()
        
        # Get top discovered subreddits
        cur.execute("""
            SELECT 
                subreddit_name,
                TO_CHAR(discovered_at, 'YYYY-MM-DD')::TEXT as discovered_at,
                is_active
            FROM discovered_subreddits
            WHERE is_active = true
            ORDER BY discovered_at DESC
            LIMIT 10
        """)
        top_subreddits = cur.fetchall()
        
        # Get trending keywords (extract from recent mentions)
        # Simple approach: get most common words from recent tweets/posts
        cur.execute("""
            SELECT 
                unnest(string_to_array(lower(content), ' ')) as word,
                COUNT(*) as frequency
            FROM social_mentions
            WHERE posted_at >= %s
            GROUP BY word
            HAVING LENGTH(unnest(string_to_array(lower(content), ' '))) > 4
            ORDER BY frequency DESC
            LIMIT 15
        """, (monday,))
        trending_keywords = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'current_week': current_week,
            'weekly_trends': [dict(row) for row in weekly_data],
            'recent_mentions': [dict(row) for row in recent_mentions],
            'platform_breakdown': [dict(row) for row in platform_breakdown],
            'sentiment_summary': [dict(row) for row in sentiment_summary],
            'top_subreddits': [dict(row) for row in top_subreddits],
            'trending_keywords': [dict(row) for row in trending_keywords]
        })
        
    except Exception as e:
        logger.error(f"Error fetching overview: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/social', methods=['GET'])
@require_auth
def get_social():
    """Get social media metrics and mentions"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Allow frontend to request historic data
        historic = request.args.get('historic', '0') in ('1', 'true', 'True')
        
        if historic:
            # Return ALL historical platform metrics (no limit)
            # Force string types by casting to TEXT (prevents psycopg2 from re-parsing)
            # Set follower_count to 0 for dates before Nov 2025 (backfilled data)
            cur.execute("""
                SELECT 
                    TO_CHAR(date, 'YYYY-MM-DD')::TEXT as week_start_date,
                    platform,
                    CASE 
                        WHEN date < '2025-11-01' THEN 0 
                        ELSE follower_count 
                    END as follower_count,
                    mentions_count,
                    engagement_rate,
                    TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS')::TEXT as created_at
                FROM social_media_daily_metrics
                ORDER BY date DESC, platform
            """)
            platform_metrics = cur.fetchall()
            
            # Return ALL mentions (no limit)
            # Force string types by casting to TEXT
            cur.execute("""
                SELECT
                    platform,
                    author,
                    content,
                    post_url,
                    TO_CHAR(posted_at, 'YYYY-MM-DD"T"HH24:MI:SS')::TEXT as posted_at,
                    likes,
                    retweets,
                    replies,
                    sentiment,
                    sentiment_score
                FROM social_mentions
                ORDER BY posted_at DESC
            """)
            recent_mentions = cur.fetchall()
        else:
            # Get last 60 days of platform metrics (daily data)
            # Set follower_count to 0 for dates before Nov 2025 (backfilled data)
            cur.execute("""
                SELECT 
                    TO_CHAR(date, 'YYYY-MM-DD') as week_start_date,
                    platform,
                    CASE 
                        WHEN date < '2025-11-01' THEN 0 
                        ELSE follower_count 
                    END as follower_count,
                    mentions_count,
                    engagement_rate,
                    created_at
                FROM social_media_daily_metrics
                ORDER BY date DESC, platform
                LIMIT 180
            """)
            platform_metrics = cur.fetchall()
            
            # Default: recent mentions (last 4 weeks)
            four_weeks_ago = (datetime.now() - timedelta(weeks=4)).date()
            cur.execute("""
                SELECT 
                    platform,
                    author,
                    content,
                    post_url,
                    TO_CHAR(posted_at, 'YYYY-MM-DD"T"HH24:MI:SS') as posted_at,
                    likes,
                    retweets,
                    replies,
                    sentiment,
                    sentiment_score
                FROM social_mentions
                WHERE week_start_date >= %s
                ORDER BY posted_at DESC
                LIMIT 100
            """, (four_weeks_ago,))
            recent_mentions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Manual JSON serialization to avoid date format issues
        response_data = {
            'platform_metrics': [dict(row) for row in platform_metrics],
            'recent_mentions': [dict(row) for row in recent_mentions]
        }
        return Response(
            json.dumps(response_data, cls=DateTimeEncoder),
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error fetching social data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sentiment', methods=['GET'])
@require_auth
def get_sentiment():
    """Get sentiment analysis data for social mentions"""
    try:
        # Allow filtering by platform (Twitter or Reddit)
        platform = request.args.get('platform', 'Twitter')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get ALL historical sentiment metrics for the specified platform
        # Force string types by casting to TEXT (prevents psycopg2 from re-parsing)
        cur.execute("""
            SELECT
                TO_CHAR(date, 'YYYY-MM-DD')::TEXT as date,
                platform,
                positive_count,
                negative_count,
                neutral_count,
                unanalyzed_count,
                average_sentiment_score,
                TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS')::TEXT as created_at
            FROM social_sentiment_metrics
            WHERE platform = %s
            ORDER BY date DESC
        """, (platform,))
        sentiment_metrics = cur.fetchall()
        
        # Get sentiment-categorized recent mentions for the specified platform
        cur.execute("""
            SELECT 
                author,
                content,
                post_url,
                posted_at,
                sentiment,
                sentiment_score,
                likes,
                retweets,
                replies
            FROM social_mentions 
            WHERE platform = %s
            AND sentiment IS NOT NULL
            ORDER BY posted_at DESC
            LIMIT 50
        """, (platform,))
        categorized_mentions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Manual JSON serialization to avoid Flask's automatic date conversion
        # Use custom encoder for datetime objects
        response_data = {
            'sentiment_metrics': [dict(row) for row in sentiment_metrics],
            'categorized_mentions': [dict(row) for row in categorized_mentions]
        }
        return Response(
            json.dumps(response_data, cls=DateTimeEncoder),
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error fetching sentiment data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/website', methods=['GET'])
@require_auth
def get_website():
    """Get website analytics data"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get last 12 weeks of website metrics
        cur.execute("""
            SELECT 
                week_start_date,
                total_sessions,
                total_users,
                total_pageviews,
                avg_session_duration,
                bounce_rate
            FROM website_metrics
            ORDER BY week_start_date DESC
            LIMIT 12
        """)
        weekly_metrics = cur.fetchall()
        
        # Get top pages from last week
        last_week = (datetime.now() - timedelta(weeks=1)).date()
        monday = last_week - timedelta(days=last_week.weekday())
        
        cur.execute("""
            SELECT 
                page_path,
                pageviews,
                avg_time_on_page
            FROM top_pages
            WHERE week_start_date = %s
            ORDER BY pageviews DESC
            LIMIT 10
        """, (monday,))
        top_pages = cur.fetchall()
        
        # Get geographic distribution from last week
        cur.execute("""
            SELECT 
                country,
                sessions,
                users
            FROM geographic_metrics
            WHERE week_start_date = %s
            ORDER BY sessions DESC
            LIMIT 20
        """, (monday,))
        geographic_data = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'weekly_metrics': [dict(row) for row in weekly_metrics],
            'top_pages': [dict(row) for row in top_pages],
            'geographic_data': [dict(row) for row in geographic_data]
        })
        
    except Exception as e:
        logger.error(f"Error fetching website data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/citations', methods=['GET'])
@require_auth
def get_citations():
    """Get academic citation data"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get weekly citation metrics
        cur.execute("""
            SELECT 
                week_start_date,
                total_citations,
                new_citations_this_week,
                total_works
            FROM citation_metrics
            ORDER BY week_start_date DESC
            LIMIT 12
        """)
        weekly_metrics = cur.fetchall()
        
        # Get top cited works (sorted by most recent publication date)
        cur.execute("""
            SELECT 
                title,
                authors,
                publication_date,
                cited_by_count,
                doi,
                source_url,
                updated_at
            FROM citations
            ORDER BY publication_date DESC NULLS LAST
            LIMIT 20
        """)
        top_works = cur.fetchall()
        
        # Get recent citations (sorted by publication date, not update time)
        cur.execute("""
            SELECT 
                title,
                authors,
                publication_date,
                cited_by_count,
                doi,
                source_url,
                updated_at
            FROM citations
            ORDER BY publication_date DESC NULLS LAST
            LIMIT 10
        """)
        recent_citations = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'weekly_metrics': [dict(row) for row in weekly_metrics],
            'top_works': [dict(row) for row in top_works],
            'recent_citations': [dict(row) for row in recent_citations]
        })
        
    except Exception as e:
        logger.error(f"Error fetching citation data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/news', methods=['GET'])
@require_auth
def get_news():
    """Get news mentions from Google Alerts"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get news mentions from last 8 weeks
        eight_weeks_ago = (datetime.now() - timedelta(weeks=8)).date()
        monday = eight_weeks_ago - timedelta(days=eight_weeks_ago.weekday())
        
        cur.execute("""
            SELECT 
                title,
                url,
                source,
                published_at,
                snippet,
                week_start_date
            FROM news_mentions
            WHERE week_start_date >= %s
            ORDER BY published_at DESC
        """, (monday,))
        news_mentions = cur.fetchall()
        
        # Get weekly counts
        cur.execute("""
            SELECT 
                week_start_date,
                COUNT(*) as mention_count
            FROM news_mentions
            WHERE week_start_date >= %s
            GROUP BY week_start_date
            ORDER BY week_start_date DESC
        """, (monday,))
        weekly_counts = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'news_mentions': [dict(row) for row in news_mentions],
            'weekly_counts': [dict(row) for row in weekly_counts]
        })
        
    except Exception as e:
        logger.error(f"Error fetching news data: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.getenv('FLASK_DEBUG', 'False') == 'True')
