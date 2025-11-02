import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
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
    """Get overview data for the dashboard"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get last 12 weeks of data
        cur.execute("""
            SELECT 
                week_start_date,
                total_news_mentions,
                total_social_mentions,
                total_citations,
                total_website_sessions
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
                COALESCE(total_citations, 0) as citations,
                COALESCE(total_website_sessions, 0) as website_sessions
            FROM weekly_snapshots
            WHERE week_start_date = %s
        """, (monday,))
        current_week = cur.fetchone()
        
        if not current_week:
            current_week = {
                'news_mentions': 0,
                'social_mentions': 0,
                'citations': 0,
                'website_sessions': 0
            }
        
        cur.close()
        conn.close()
        
        return jsonify({
            'current_week': current_week,
            'weekly_trends': [dict(row) for row in weekly_data]
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
        
        # Get last 12 weeks of platform metrics
        cur.execute("""
            SELECT 
                week_start_date,
                platform,
                follower_count,
                mentions_count,
                engagement_rate
            FROM social_media_metrics
            ORDER BY week_start_date DESC, platform
            LIMIT 36
        """)
        platform_metrics = cur.fetchall()
        
        # Get recent mentions (last 4 weeks)
        four_weeks_ago = (datetime.now() - timedelta(weeks=4)).date()
        cur.execute("""
            SELECT 
                platform,
                author,
                content,
                post_url,
                posted_at,
                likes,
                retweets,
                replies
            FROM social_mentions
            WHERE week_start_date >= %s
            ORDER BY posted_at DESC
            LIMIT 100
        """, (four_weeks_ago,))
        recent_mentions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'platform_metrics': [dict(row) for row in platform_metrics],
            'recent_mentions': [dict(row) for row in recent_mentions]
        })
        
    except Exception as e:
        logger.error(f"Error fetching social data: {e}")
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
        
        # Get top cited works
        cur.execute("""
            SELECT 
                title,
                authors,
                publication_date,
                cited_by_count,
                doi,
                source_url
            FROM citations
            ORDER BY cited_by_count DESC
            LIMIT 20
        """)
        top_works = cur.fetchall()
        
        # Get recent citations
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
            ORDER BY updated_at DESC
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
