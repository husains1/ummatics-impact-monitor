# Reddit Support Implementation Plan

## Overview
This document outlines the implementation of Reddit support for the Ummatics Impact Monitor, including new database tables, API endpoints, UI components, and sentiment analysis integration.

---

## 1. Permissions & Credentials Required

### Reddit API
- **Setup**: Create app at https://www.reddit.com/prefs/apps (requires Reddit account)
- **Credentials**:
  - `REDDIT_CLIENT_ID`: OAuth 2.0 client ID
  - `REDDIT_CLIENT_SECRET`: OAuth 2.0 client secret
  - `REDDIT_USERNAME`: Reddit account username for authentication
  - `REDDIT_PASSWORD`: Reddit account password
  - `REDDIT_USER_AGENT`: Custom user agent (format: `YourApp/1.0 by YourUsername`)

- **Scopes**: Read-only access (`read` scope)
- **Rate Limits**: 60 requests per minute per authenticated user
- **Search**: Can search subreddits, posts, and comments; free tier supports historical data retrieval

### Environment Variables to Add
```bash
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
REDDIT_USER_AGENT="UmmaticsMonitor/1.0 by YourUsername"
REDDIT_SEARCH_TERMS="ummatics,keyword1,keyword2"  # Comma-separated
REDDIT_SUBREDDITS="r/subreddit1,r/subreddit2"     # Optional: target specific subreddits
```

---

## 2. Database Schema Changes

### New Tables Required

#### 2.1 Reddit Mentions Table
```sql
CREATE TABLE reddit_mentions (
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
```

#### 2.2 Reddit Daily Metrics Table
```sql
CREATE TABLE reddit_daily_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    mentions_count INTEGER DEFAULT 0,
    posts_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    avg_upvotes DECIMAL(10, 2) DEFAULT 0,
    avg_comments DECIMAL(10, 2) DEFAULT 0,
    total_engagement INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date)
);
```

#### 2.3 Reddit Subreddit Metrics Table
```sql
CREATE TABLE reddit_subreddit_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    subreddit VARCHAR(255) NOT NULL,
    mentions_count INTEGER DEFAULT 0,
    avg_upvotes DECIMAL(10, 2) DEFAULT 0,
    avg_comments DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, subreddit)
);
```

#### 2.4 Update to social_mentions table (for unified view)
```sql
-- Already has platform='Reddit' support; no schema changes needed
-- Existing columns: post_id, author, content, post_url, posted_at, likes, retweets, replies, sentiment, sentiment_analyzed_at
-- Will treat upvotes as "likes", comments_count as "replies"
```

#### 2.5 Sentiment Metrics by Platform
```sql
CREATE TABLE IF NOT EXISTS social_sentiment_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    platform VARCHAR(50) NOT NULL,
    positive_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    unanalyzed_count INTEGER DEFAULT 0,
    average_sentiment_score DECIMAL(5, 3) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, platform)
);
```

### Indexes
```sql
CREATE INDEX idx_reddit_mentions_date ON reddit_mentions(week_start_date);
CREATE INDEX idx_reddit_mentions_subreddit ON reddit_mentions(subreddit);
CREATE INDEX idx_reddit_mentions_posted_at ON reddit_mentions(posted_at);
CREATE INDEX idx_reddit_daily_metrics_date ON reddit_daily_metrics(date);
CREATE INDEX idx_reddit_subreddit_metrics_date ON reddit_subreddit_metrics(date);
CREATE INDEX idx_reddit_subreddit_metrics_subreddit ON reddit_subreddit_metrics(subreddit);
CREATE INDEX idx_sentiment_metrics_date_platform ON social_sentiment_metrics(date, platform);
```

---

## 3. Backend Implementation

### 3.1 New Module: `backend/reddit_ingestion.py`
- **Purpose**: Handle Reddit API authentication and data retrieval
- **Key Functions**:
  - `get_reddit_client()`: Authenticate with Reddit API using PRAW library
  - `search_reddit_posts()`: Search for keywords across subreddits
  - `fetch_subreddit_posts()`: Fetch posts from specific subreddits
  - `ingest_reddit()`: Main ingestion function (called by scheduler)
  - `store_reddit_mentions()`: Insert/update posts in database
  - `update_reddit_metrics()`: Compute daily/subreddit aggregates

### 3.2 Modified: `backend/ingestion.py`
- **Changes**:
  - Add `ingest_reddit()` call to `run_full_ingestion()`
  - Reuse sentiment analysis wrapper for Reddit content
  - Update platform metrics aggregation to include Reddit

### 3.3 Sentiment Analysis for Reddit
- **Approach**: Use same transformer model as Twitter
  - **Model**: `cardiffnlp/twitter-roberta-base-sentiment` (trained on social media language)
  - **Alternative (optional)**: `distilbert-base-uncased-finetuned-sst-2-english` for general text
  - **Reddit-specific tuning** (optional): Train custom model on Reddit sentiment corpus
- **Text Processing**:
  - Concatenate title + content for sentiment
  - Clean: remove URLs, markdown formatting, user mentions
  - Apply same text-cleaning pipeline as Twitter

### 3.4 Scheduler Integration
- **No changes required** to `scheduler.py`
- Existing `run_full_ingestion()` will call `ingest_reddit()` on same schedule as Twitter (daily at 9:00 AM)

### 3.5 Dependencies to Add (`backend/requirements.txt`)
```
praw==7.7.0              # Reddit API wrapper
prawcore==2.4.0          # PRAW dependencies
```

---

## 4. API Endpoints

### 4.1 New Endpoints in `backend/api.py`

#### `GET /api/reddit`
**Purpose**: Get Reddit metrics and mentions
**Response**:
```json
{
  "daily_metrics": [
    {
      "date": "2025-11-15",
      "mentions_count": 24,
      "posts_count": 12,
      "comments_count": 12,
      "avg_upvotes": 45.5,
      "avg_comments": 3.2,
      "total_engagement": 548
    }
  ],
  "subreddit_breakdown": [
    {
      "subreddit": "r/subreddit1",
      "mentions_count": 15,
      "avg_upvotes": 52.3,
      "avg_comments": 4.1
    }
  ],
  "recent_mentions": [
    {
      "post_id": "abc123",
      "subreddit": "r/subreddit1",
      "title": "Post title",
      "author": "username",
      "upvotes": 87,
      "comments": 5,
      "posted_at": "2025-11-15T10:30:00Z",
      "sentiment": "positive",
      "sentiment_score": 0.78,
      "post_url": "https://reddit.com/r/..."
    }
  ]
}
```

#### `GET /api/reddit/sentiment`
**Purpose**: Get Reddit sentiment analysis
**Response**:
```json
{
  "overall_sentiment": {
    "positive_count": 12,
    "negative_count": 3,
    "neutral_count": 9,
    "average_score": 0.35
  },
  "sentiment_trends": [
    {
      "date": "2025-11-15",
      "positive": 12,
      "negative": 3,
      "neutral": 9
    }
  ]
}
```

#### `GET /api/reddit/subreddit/:subreddit`
**Purpose**: Get metrics for specific subreddit
**Response**:
```json
{
  "subreddit": "r/subreddit1",
  "total_mentions": 45,
  "avg_upvotes": 52.3,
  "avg_comments": 4.1,
  "sentiment_breakdown": {
    "positive": 25,
    "negative": 5,
    "neutral": 15
  },
  "recent_posts": [...]
}
```

#### `GET /api/reddit/search?q=keyword`
**Purpose**: Search Reddit mentions by keyword
**Query Parameters**: `q` (search term), `limit` (default 50)

### 4.2 Modified Endpoints

#### `GET /api/social` - Updated
- Include Reddit metrics alongside Twitter
- Unified social media dashboard

#### `GET /api/sentiment` - Updated
- Add Reddit sentiment to overall platform comparison

---

## 5. Frontend Implementation

### 5.1 New Tab: `Reddit`
- **Location**: Add to tab list in `App.jsx`
- **Components**:
  - **Dashboard**: Daily metrics chart (mentions, engagement over time)
  - **Subreddit Breakdown**: Table of top subreddits by activity
  - **Recent Mentions**: List of recent posts with sentiment badges
  - **Sentiment Analysis**: Positive/neutral/negative pie chart and trends

### 5.2 UI Components
```jsx
// RedditDashboard.jsx
- Line chart: mentions/engagement over 30 days
- Table: subreddit activity (mentions, avg upvotes, avg comments)
- List: recent posts with sentiment badges (positive=green, negative=red, neutral=gray)
- Pie chart: sentiment distribution
- Trend indicators: ↑ for improving sentiment, ↓ for declining

// RedditSentimentCard.jsx
- Large sentiment score display
- Percentage breakdown (positive %, negative %, neutral %)
- Trend indicator vs previous week

// RedditMentionCard.jsx
- Post title (clickable to Reddit)
- Subreddit name
- Author and posted date
- Upvotes and comments count
- Sentiment label and score
```

### 5.3 Updated `App.jsx`
```jsx
// Add to tab list
const tabs = ['overview', 'social', 'reddit', 'website', 'citations', 'news']

// Add to data states
const [redditData, setRedditData] = useState(null)
const [redditSentiment, setRedditSentiment] = useState(null)

// Add to useEffect
if (activeTab === 'reddit') {
  fetchData('/reddit', setRedditData)
  fetchData('/reddit/sentiment', setRedditSentiment)
}
```

---

## 6. Implementation Timeline & Task Breakdown

### Phase 1: Backend Setup (1-2 days)
- [ ] Create Reddit API credentials
- [ ] Create `reddit_ingestion.py` module
- [ ] Create new database tables
- [ ] Add environment variables to docker-compose.yml
- [ ] Update `ingestion.py` to call `ingest_reddit()`
- [ ] Test Reddit API connection and ingestion

### Phase 2: API & Data Aggregation (1 day)
- [ ] Add Reddit API endpoints to `api.py`
- [ ] Implement sentiment metrics aggregation
- [ ] Test endpoints with sample data

### Phase 3: Frontend (1-2 days)
- [ ] Create Reddit dashboard tab
- [ ] Create UI components
- [ ] Add Reddit data fetching to App.jsx
- [ ] Style with Tailwind CSS

### Phase 4: Deployment & Testing (1 day)
- [ ] Update docker-compose.yml with secrets
- [ ] Rebuild Docker images
- [ ] Deploy to AWS
- [ ] Test end-to-end workflow
- [ ] Monitor ingestion logs

---

## 7. Security Considerations

- **Credentials**: Store Reddit API keys in `.env` file (never commit)
- **Rate Limiting**: PRAW handles rate limiting automatically; monitor logs for 429 errors
- **Data Privacy**: Reddit data is public; no personal data concerns beyond what Reddit stores
- **API Validation**: Validate all user inputs in search endpoints
- **Authentication**: Maintain existing JWT-based dashboard auth

---

## 8. Optional Enhancements

1. **Custom Sentiment Model for Reddit**
   - Train on Reddit corpus for Reddit-specific language nuances
   - Would require labeled Reddit sentiment dataset

2. **Comment-Level Analysis**
   - Current plan fetches posts only; could expand to fetch top comments
   - Would increase ingestion time and storage

3. **Subreddit Recommendations**
   - ML model to suggest relevant subreddits based on engagement

4. **Alert System**
   - Notify on high-engagement posts or sentiment shifts

5. **Competitor Tracking**
   - Monitor mentions of competitors alongside Ummatics

---

## 9. Estimated Resource Requirements

### Development Effort
- **Backend**: ~8-10 hours
- **Frontend**: ~6-8 hours
- **Testing & Deployment**: ~4-6 hours
- **Total**: ~18-24 hours

### Infrastructure
- **Storage**: ~50MB-100MB per month (average Reddit mention ≈ 2KB)
- **API Calls**: ~1000-2000 calls per day (within Reddit free tier limits)
- **Database**: Minimal (sentiment analysis via existing transformer)

### Ongoing Maintenance
- Monitor Reddit API changes
- Handle potential API deprecations
- Adjust search terms based on engagement trends

---

## 10. Rollback Plan

If issues arise:
1. Set `REDDIT_INGESTION_ENABLED=0` in environment to disable Reddit ingestion
2. Keep existing Twitter infrastructure intact
3. No database schema changes break existing code (tables are separate)
4. Frontend tab can be hidden via feature flag

---

## Next Steps

1. Confirm Reddit API credential setup ✓
2. Start Phase 1 backend implementation
3. Share status updates as each phase completes
