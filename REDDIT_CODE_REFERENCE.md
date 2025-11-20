# Reddit Support - Code Implementation Reference

## Files to Create/Modify

### 1. CREATE: `backend/reddit_ingestion.py` (NEW FILE)

**Purpose**: Handle Reddit API integration and ingestion

**Template Structure** (detailed code in REDDIT_IMPLEMENTATION_PLAN.md):

```python
import os
import psycopg2
import praw
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Configuration from environment
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID', '')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET', '')
REDDIT_USERNAME = os.getenv('REDDIT_USERNAME', '')
REDDIT_PASSWORD = os.getenv('REDDIT_PASSWORD', '')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'UmmaticsMonitor/1.0')
REDDIT_SEARCH_TERMS = os.getenv('REDDIT_SEARCH_TERMS', 'ummatics').split(',')
REDDIT_SUBREDDITS = os.getenv('REDDIT_SUBREDDITS', '').split(',')

# Database configuration (same as ingestion.py)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'ummatics_monitor'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

def get_reddit_client():
    """Authenticate with Reddit API using PRAW"""
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD
        )
        return reddit
    except Exception as e:
        logger.error(f"Failed to authenticate with Reddit API: {e}")
        raise

def search_reddit_posts(reddit, search_terms):
    """Search for posts across all subreddits using search terms"""
    posts = []
    for term in search_terms:
        try:
            for post in reddit.subreddit('all').search(term, time_filter='month', limit=100):
                posts.append(post)
                logger.info(f"Found post: {post.title[:50]}... in r/{post.subreddit}")
        except Exception as e:
            logger.warning(f"Error searching for '{term}': {e}")
    return posts

def fetch_subreddit_posts(reddit, subreddits):
    """Fetch recent posts from specific subreddits"""
    posts = []
    for sub in subreddits:
        if not sub.strip():
            continue
        try:
            for post in reddit.subreddit(sub.replace('r/', '')).new(limit=50):
                posts.append(post)
                logger.info(f"Found post in {sub}: {post.title[:50]}...")
        except Exception as e:
            logger.warning(f"Error fetching from {sub}: {e}")
    return posts

def store_reddit_mentions(conn, posts):
    """Insert Reddit posts into database"""
    cur = conn.cursor()
    inserted_count = 0
    
    for post in posts:
        try:
            # Prepare data
            week_start_date = datetime.now().date()
            post_id = post.id
            subreddit = str(post.subreddit)
            author = str(post.author) if post.author else '[deleted]'
            title = post.title
            content = post.selftext
            post_url = post.url
            posted_at = datetime.fromtimestamp(post.created_utc)
            upvotes = post.score
            downvotes = post.downs if hasattr(post, 'downs') else 0
            comments = post.num_comments
            awards = post.all_awardings.__len__() if hasattr(post, 'all_awardings') else 0
            
            # Insert into database
            cur.execute("""
                INSERT INTO reddit_mentions 
                (week_start_date, post_id, subreddit, author, title, content, 
                 post_url, posted_at, upvotes, downvotes, comments_count, award_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (post_id) DO NOTHING
            """, (week_start_date, post_id, subreddit, author, title, content,
                  post_url, posted_at, upvotes, downvotes, comments, awards))
            
            inserted_count += 1
            
        except Exception as e:
            logger.warning(f"Error storing post {post.id}: {e}")
    
    conn.commit()
    logger.info(f"Inserted {inserted_count} Reddit posts")
    return inserted_count

def analyze_and_update_sentiment(conn):
    """Analyze sentiment for posts without sentiment scores"""
    from ingestion import analyze_sentiment
    
    cur = conn.cursor()
    
    # Get posts without sentiment analysis
    cur.execute("""
        SELECT id, title, content 
        FROM reddit_mentions 
        WHERE sentiment IS NULL
        LIMIT 100
    """)
    
    posts = cur.fetchall()
    updated = 0
    
    for post_id, title, content in posts:
        try:
            # Combine title and content for sentiment
            text = f"{title}. {content}" if content else title
            
            # Analyze sentiment using shared module
            sentiment_label, sentiment_score = analyze_sentiment(text)
            
            # Update database
            cur.execute("""
                UPDATE reddit_mentions 
                SET sentiment = %s, sentiment_score = %s, sentiment_analyzed_at = %s
                WHERE id = %s
            """, (sentiment_label, sentiment_score, datetime.now(), post_id))
            
            updated += 1
            
        except Exception as e:
            logger.warning(f"Error analyzing sentiment for post {post_id}: {e}")
    
    conn.commit()
    logger.info(f"Updated sentiment for {updated} posts")
    return updated

def update_reddit_metrics(conn):
    """Compute daily and per-subreddit metrics"""
    cur = conn.cursor()
    today = datetime.now().date()
    
    try:
        # Insert daily metrics
        cur.execute("""
            INSERT INTO reddit_daily_metrics (date, mentions_count, posts_count, comments_count, avg_upvotes, avg_comments, total_engagement)
            SELECT 
                %s as date,
                COUNT(*) as mentions_count,
                COUNT(CASE WHEN is_comment = FALSE THEN 1 END) as posts_count,
                COUNT(CASE WHEN is_comment = TRUE THEN 1 END) as comments_count,
                AVG(CAST(upvotes AS FLOAT)) as avg_upvotes,
                AVG(CAST(comments_count AS FLOAT)) as avg_comments,
                SUM(upvotes + comments_count) as total_engagement
            FROM reddit_mentions
            WHERE DATE(posted_at) = %s
            ON CONFLICT (date) DO UPDATE SET
                mentions_count = EXCLUDED.mentions_count,
                posts_count = EXCLUDED.posts_count,
                comments_count = EXCLUDED.comments_count,
                avg_upvotes = EXCLUDED.avg_upvotes,
                avg_comments = EXCLUDED.avg_comments,
                total_engagement = EXCLUDED.total_engagement
        """, (today, today))
        
        # Insert per-subreddit metrics
        cur.execute("""
            INSERT INTO reddit_subreddit_metrics (date, subreddit, mentions_count, avg_upvotes, avg_comments)
            SELECT 
                %s as date,
                subreddit,
                COUNT(*) as mentions_count,
                AVG(CAST(upvotes AS FLOAT)) as avg_upvotes,
                AVG(CAST(comments_count AS FLOAT)) as avg_comments
            FROM reddit_mentions
            WHERE DATE(posted_at) = %s
            GROUP BY subreddit
            ON CONFLICT (date, subreddit) DO UPDATE SET
                mentions_count = EXCLUDED.mentions_count,
                avg_upvotes = EXCLUDED.avg_upvotes,
                avg_comments = EXCLUDED.avg_comments
        """, (today, today))
        
        # Update social_sentiment_metrics
        cur.execute("""
            INSERT INTO social_sentiment_metrics (date, platform, positive_count, negative_count, neutral_count, average_sentiment_score)
            SELECT
                %s as date,
                'Reddit' as platform,
                COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as positive_count,
                COUNT(CASE WHEN sentiment = 'negative' THEN 1 END) as negative_count,
                COUNT(CASE WHEN sentiment = 'neutral' THEN 1 END) as neutral_count,
                AVG(CAST(sentiment_score AS FLOAT)) as average_sentiment_score
            FROM reddit_mentions
            WHERE DATE(posted_at) = %s
            ON CONFLICT (date, platform) DO UPDATE SET
                positive_count = EXCLUDED.positive_count,
                negative_count = EXCLUDED.negative_count,
                neutral_count = EXCLUDED.neutral_count,
                average_sentiment_score = EXCLUDED.average_sentiment_score
        """, (today, today))
        
        conn.commit()
        logger.info("Updated Reddit metrics")
        
    except Exception as e:
        logger.error(f"Error updating metrics: {e}")
        conn.rollback()

def ingest_reddit():
    """Main Reddit ingestion function"""
    logger.info("Starting Reddit ingestion...")
    
    try:
        # Check if enabled
        if os.getenv('REDDIT_INGESTION_ENABLED', '1') not in ('1', 'true', 'True'):
            logger.info("Reddit ingestion disabled")
            return
        
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        
        # Authenticate with Reddit
        reddit = get_reddit_client()
        logger.info("Authenticated with Reddit API")
        
        # Fetch posts
        posts = search_reddit_posts(reddit, REDDIT_SEARCH_TERMS)
        if REDDIT_SUBREDDITS and REDDIT_SUBREDDITS[0].strip():
            posts.extend(fetch_subreddit_posts(reddit, REDDIT_SUBREDDITS))
        
        logger.info(f"Found {len(posts)} posts total")
        
        # Store posts
        store_reddit_mentions(conn, posts)
        
        # Analyze sentiment
        analyze_and_update_sentiment(conn)
        
        # Update metrics
        update_reddit_metrics(conn)
        
        conn.close()
        logger.info("Reddit ingestion complete")
        
    except Exception as e:
        logger.error(f"Reddit ingestion failed: {e}")
        raise

if __name__ == '__main__':
    ingest_reddit()
```

---

### 2. MODIFY: `backend/ingestion.py`

**Changes**: Add call to `ingest_reddit()` in `run_full_ingestion()` function

**Location**: In the `run_full_ingestion()` function (find the function that calls all ingestion methods)

**Before**:
```python
def run_full_ingestion():
    """Run all ingestion tasks"""
    logger.info("Starting full ingestion cycle...")
    ingest_google_alerts()
    ingest_twitter()
    ingest_website_analytics()
    ingest_citations()
    update_sentiment_metrics()
    logger.info("Full ingestion cycle complete")
```

**After**:
```python
def run_full_ingestion():
    """Run all ingestion tasks"""
    logger.info("Starting full ingestion cycle...")
    ingest_google_alerts()
    ingest_twitter()
    
    # NEW: Add Reddit ingestion
    try:
        from reddit_ingestion import ingest_reddit
        ingest_reddit()
    except Exception as e:
        logger.error(f"Reddit ingestion error: {e}")
    
    ingest_website_analytics()
    ingest_citations()
    update_sentiment_metrics()
    logger.info("Full ingestion cycle complete")
```

---

### 3. MODIFY: `backend/requirements.txt`

**Changes**: Add PRAW (Reddit API library)

**Add these lines**:
```
praw==7.7.0
prawcore==2.4.0
```

---

### 4. MODIFY: `backend/api.py`

**Changes**: Add new Reddit endpoints

**Add these endpoints** (add to the Flask app):

```python
@app.route('/api/reddit', methods=['GET'])
@require_auth
def get_reddit():
    """Get Reddit metrics and mentions"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get last 30 days of daily metrics
        cur.execute("""
            SELECT 
                date,
                mentions_count,
                posts_count,
                comments_count,
                avg_upvotes,
                avg_comments,
                total_engagement
            FROM reddit_daily_metrics
            ORDER BY date DESC
            LIMIT 30
        """)
        daily_metrics = cur.fetchall()
        
        # Get subreddit breakdown (last 7 days)
        cur.execute("""
            SELECT 
                subreddit,
                SUM(mentions_count) as total_mentions,
                AVG(avg_upvotes) as avg_upvotes,
                AVG(avg_comments) as avg_comments
            FROM reddit_subreddit_metrics
            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY subreddit
            ORDER BY total_mentions DESC
            LIMIT 20
        """)
        subreddit_breakdown = cur.fetchall()
        
        # Get recent mentions
        cur.execute("""
            SELECT 
                post_id,
                subreddit,
                title,
                author,
                upvotes,
                comments_count,
                posted_at,
                sentiment,
                sentiment_score,
                post_url
            FROM reddit_mentions
            ORDER BY posted_at DESC
            LIMIT 20
        """)
        recent_mentions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'daily_metrics': [dict(row) for row in daily_metrics],
            'subreddit_breakdown': [dict(row) for row in subreddit_breakdown],
            'recent_mentions': [dict(row) for row in recent_mentions]
        })
        
    except Exception as e:
        logger.error(f"Error fetching Reddit data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/reddit/sentiment', methods=['GET'])
@require_auth
def get_reddit_sentiment():
    """Get Reddit sentiment analysis"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get overall sentiment
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as positive_count,
                COUNT(CASE WHEN sentiment = 'negative' THEN 1 END) as negative_count,
                COUNT(CASE WHEN sentiment = 'neutral' THEN 1 END) as neutral_count,
                AVG(CAST(sentiment_score AS FLOAT)) as average_score
            FROM reddit_mentions
            WHERE sentiment_analyzed_at IS NOT NULL
        """)
        overall = cur.fetchone()
        
        # Get sentiment trends (last 14 days)
        cur.execute("""
            SELECT 
                date,
                positive_count,
                negative_count,
                neutral_count,
                average_sentiment_score
            FROM social_sentiment_metrics
            WHERE platform = 'Reddit'
            AND date >= CURRENT_DATE - INTERVAL '14 days'
            ORDER BY date DESC
        """)
        trends = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'overall_sentiment': dict(overall) if overall else {},
            'sentiment_trends': [dict(row) for row in trends]
        })
        
    except Exception as e:
        logger.error(f"Error fetching Reddit sentiment: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/reddit/subreddit/<subreddit>', methods=['GET'])
@require_auth
def get_subreddit_metrics(subreddit):
    """Get metrics for specific subreddit"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get total metrics
        cur.execute("""
            SELECT 
                COUNT(*) as total_mentions,
                AVG(CAST(upvotes AS FLOAT)) as avg_upvotes,
                AVG(CAST(comments_count AS FLOAT)) as avg_comments,
                COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as positive,
                COUNT(CASE WHEN sentiment = 'negative' THEN 1 END) as negative,
                COUNT(CASE WHEN sentiment = 'neutral' THEN 1 END) as neutral
            FROM reddit_mentions
            WHERE subreddit = %s
        """, (subreddit,))
        metrics = cur.fetchone()
        
        # Get recent posts
        cur.execute("""
            SELECT 
                post_id,
                title,
                author,
                upvotes,
                comments_count,
                posted_at,
                sentiment,
                sentiment_score,
                post_url
            FROM reddit_mentions
            WHERE subreddit = %s
            ORDER BY posted_at DESC
            LIMIT 10
        """, (subreddit,))
        recent_posts = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'subreddit': subreddit,
            'metrics': dict(metrics) if metrics else {},
            'recent_posts': [dict(row) for row in recent_posts]
        })
        
    except Exception as e:
        logger.error(f"Error fetching subreddit metrics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/reddit/search', methods=['GET'])
@require_auth
def search_reddit_mentions():
    """Search Reddit mentions by keyword"""
    try:
        query = request.args.get('q', '')
        limit = request.args.get('limit', 50, type=int)
        
        if not query:
            return jsonify({'error': 'Query parameter required'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                post_id,
                subreddit,
                title,
                content,
                author,
                upvotes,
                comments_count,
                posted_at,
                sentiment,
                sentiment_score,
                post_url
            FROM reddit_mentions
            WHERE title ILIKE %s OR content ILIKE %s
            ORDER BY posted_at DESC
            LIMIT %s
        """, (f"%{query}%", f"%{query}%", limit))
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'query': query,
            'count': len(results),
            'results': [dict(row) for row in results]
        })
        
    except Exception as e:
        logger.error(f"Error searching Reddit mentions: {e}")
        return jsonify({'error': str(e)}), 500
```

---

### 5. MODIFY: `docker-compose.yml`

**Changes**: Add Reddit environment variables

**Add to `api` service**:
```yaml
    environment:
      - REDDIT_CLIENT_ID=${REDDIT_CLIENT_ID}
      - REDDIT_CLIENT_SECRET=${REDDIT_CLIENT_SECRET}
      - REDDIT_USERNAME=${REDDIT_USERNAME}
      - REDDIT_PASSWORD=${REDDIT_PASSWORD}
      - REDDIT_USER_AGENT=${REDDIT_USER_AGENT:-UmmaticsMonitor/1.0 by ummatics}
      - REDDIT_SEARCH_TERMS=${REDDIT_SEARCH_TERMS:-ummatics}
      - REDDIT_SUBREDDITS=${REDDIT_SUBREDDITS:-}
      - REDDIT_INGESTION_ENABLED=${REDDIT_INGESTION_ENABLED:-1}
      - USE_TRANSFORMER=${USE_TRANSFORMER:-1}
```

---

### 6. CREATE: `frontend/src/components/RedditDashboard.jsx` (NEW FILE)

**Purpose**: React component for Reddit analytics dashboard

**Basic template**:
```jsx
import React, { useState, useEffect } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const COLORS = ['#10b981', '#ef4444', '#6b7280']

export function RedditDashboard({ redditData, redditSentiment, token }) {
  if (!redditData) {
    return <div className="p-8 text-center text-gray-500">Loading Reddit data...</div>
  }

  return (
    <div className="space-y-6">
      {/* Daily Metrics Chart */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Daily Reddit Activity</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={redditData.daily_metrics || []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="mentions_count" stroke="#3b82f6" name="Total Mentions" />
            <Line type="monotone" dataKey="total_engagement" stroke="#8b5cf6" name="Engagement" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Subreddit Breakdown */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Top Subreddits</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 px-4">Subreddit</th>
                <th className="text-right py-2 px-4">Mentions</th>
                <th className="text-right py-2 px-4">Avg Upvotes</th>
                <th className="text-right py-2 px-4">Avg Comments</th>
              </tr>
            </thead>
            <tbody>
              {(redditData.subreddit_breakdown || []).map((sub, idx) => (
                <tr key={idx} className="border-b hover:bg-gray-50">
                  <td className="py-2 px-4 font-medium">{sub.subreddit}</td>
                  <td className="text-right py-2 px-4">{sub.total_mentions}</td>
                  <td className="text-right py-2 px-4">{sub.avg_upvotes?.toFixed(1)}</td>
                  <td className="text-right py-2 px-4">{sub.avg_comments?.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sentiment Distribution */}
      {redditSentiment && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-bold mb-4">Sentiment Distribution</h2>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={[
                    { name: 'Positive', value: redditSentiment.overall_sentiment?.positive_count || 0 },
                    { name: 'Negative', value: redditSentiment.overall_sentiment?.negative_count || 0 },
                    { name: 'Neutral', value: redditSentiment.overall_sentiment?.neutral_count || 0 }
                  ]}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {COLORS.map((color, index) => (
                    <Cell key={`cell-${index}`} fill={color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-xl font-bold mb-4">Sentiment Score Trend</h2>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={redditSentiment.sentiment_trends || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[-1, 1]} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="average_sentiment_score" stroke="#10b981" name="Avg Sentiment" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Recent Mentions */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Recent Mentions</h2>
        <div className="space-y-4">
          {(redditData.recent_mentions || []).map((mention, idx) => (
            <div key={idx} className="border rounded-lg p-4 hover:bg-gray-50">
              <div className="flex justify-between items-start">
                <div>
                  <a href={mention.post_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-semibold">
                    {mention.title}
                  </a>
                  <p className="text-sm text-gray-600 mt-1">
                    in <span className="font-medium">{mention.subreddit}</span> by {mention.author}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{new Date(mention.posted_at).toLocaleDateString()}</p>
                </div>
                <div className="text-right">
                  <span className={`px-3 py-1 rounded text-sm font-medium ${
                    mention.sentiment === 'positive' ? 'bg-green-100 text-green-800' :
                    mention.sentiment === 'negative' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {mention.sentiment}
                  </span>
                  <p className="text-xs text-gray-600 mt-2">Score: {mention.sentiment_score?.toFixed(2)}</p>
                </div>
              </div>
              <div className="flex gap-4 mt-2 text-xs text-gray-600">
                <span>👍 {mention.upvotes}</span>
                <span>💬 {mention.comments_count}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
```

---

### 7. MODIFY: `frontend/src/App.jsx`

**Changes**: Add Reddit tab and data fetching

**Find this section**:
```jsx
const [activeTab, setActiveTab] = useState('overview')
const [sentimentData, setSentimentData] = useState(null)
```

**Add after it**:
```jsx
const [redditData, setRedditData] = useState(null)
const [redditSentiment, setRedditSentiment] = useState(null)
```

**Find the tabs rendering section** (look for where tabs are displayed), **add to list**:
```jsx
<button onClick={() => setActiveTab('reddit')} ...>Reddit</button>
```

**Find the data fetching useEffect**, **add**:
```jsx
if (activeTab === 'reddit') {
  fetchData('/reddit', setRedditData)
  fetchData('/reddit/sentiment', setRedditSentiment)
}
```

**Find the content rendering section**, **add after other tabs**:
```jsx
{activeTab === 'reddit' && (
  <RedditDashboard 
    redditData={redditData} 
    redditSentiment={redditSentiment} 
    token={token} 
  />
)}
```

**Add import at top**:
```jsx
import { RedditDashboard } from './components/RedditDashboard'
```

---

## Database Migration SQL

**Run this on your database**:

```sql
-- Create reddit_mentions table
CREATE TABLE IF NOT EXISTS reddit_mentions (
    id SERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL,
    post_id VARCHAR(255) UNIQUE NOT NULL,
    subreddit VARCHAR(255) NOT NULL,
    author VARCHAR(255),
    title TEXT NOT NULL,
    content TEXT,
    post_url TEXT NOT NULL,
    posted_at TIMESTAMP NOT NULL,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    award_count INTEGER DEFAULT 0,
    is_comment BOOLEAN DEFAULT FALSE,
    parent_post_id VARCHAR(255),
    sentiment VARCHAR(20),
    sentiment_score DECIMAL(5, 3),
    sentiment_analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create reddit_daily_metrics table
CREATE TABLE IF NOT EXISTS reddit_daily_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    mentions_count INTEGER DEFAULT 0,
    posts_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    avg_upvotes DECIMAL(10, 2) DEFAULT 0,
    avg_comments DECIMAL(10, 2) DEFAULT 0,
    total_engagement INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create reddit_subreddit_metrics table
CREATE TABLE IF NOT EXISTS reddit_subreddit_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    subreddit VARCHAR(255) NOT NULL,
    mentions_count INTEGER DEFAULT 0,
    avg_upvotes DECIMAL(10, 2) DEFAULT 0,
    avg_comments DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, subreddit)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_reddit_mentions_date ON reddit_mentions(week_start_date);
CREATE INDEX IF NOT EXISTS idx_reddit_mentions_subreddit ON reddit_mentions(subreddit);
CREATE INDEX IF NOT EXISTS idx_reddit_mentions_posted_at ON reddit_mentions(posted_at);
CREATE INDEX IF NOT EXISTS idx_reddit_daily_metrics_date ON reddit_daily_metrics(date);
CREATE INDEX IF NOT EXISTS idx_reddit_subreddit_metrics_date ON reddit_subreddit_metrics(date);
CREATE INDEX IF NOT EXISTS idx_reddit_subreddit_metrics_subreddit ON reddit_subreddit_metrics(subreddit);
```

---

## Environment Variables for .env

```bash
# Reddit API Credentials
REDDIT_CLIENT_ID=xxxxxxxxxxxx
REDDIT_CLIENT_SECRET=xxxxxxxxxxxx
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
REDDIT_USER_AGENT="UmmaticsMonitor/1.0 by YourUsername"

# Reddit Configuration
REDDIT_SEARCH_TERMS="ummatics,keyword1,keyword2"
REDDIT_SUBREDDITS="r/science,r/health"
REDDIT_INGESTION_ENABLED=1

# Sentiment (existing, verify it's set)
USE_TRANSFORMER=1
```

---

## Testing Commands

```bash
# Test Reddit client authentication
docker-compose exec -T api python3 -c "
from reddit_ingestion import get_reddit_client
reddit = get_reddit_client()
print('Auth successful:', reddit.auth.authorized)
"

# Run ingestion manually
docker-compose exec -T api python3 /app/reddit_ingestion.py

# Check database records
docker-compose exec -T db psql -U postgres -d ummatics_monitor -c "
SELECT COUNT(*) FROM reddit_mentions;
"

# Test API endpoints
curl -H "Authorization: Bearer your_password" http://localhost:5000/api/reddit
curl -H "Authorization: Bearer your_password" http://localhost:5000/api/reddit/sentiment
```

---

**All code templates provided above. Ready to implement!** ✅
