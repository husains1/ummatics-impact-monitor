# Reddit Support - Architecture & Data Flow

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UMMATICS IMPACT MONITOR                              │
│                       (with Reddit Support Added)                            │
└─────────────────────────────────────────────────────────────────────────────┘

                          INGESTION LAYER (Daily 9:00 AM)
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│  backend/scheduler.py ─────────────────────────────────────────────────────┐ │
│       ↓                                                                      │ │
│  backend/ingestion.py (Main Entry Point)                                   │ │
│       ├─→ ingest_google_alerts()    [NEWS]                                 │ │
│       ├─→ ingest_twitter()          [TWITTER]  ◄── Existing                │ │
│       ├─→ ingest_reddit()           [REDDIT]   ◄── NEW                     │ │
│       ├─→ ingest_website_analytics() [WEBSITE]                             │ │
│       └─→ ingest_citations()        [CITATIONS]                            │ │
│                                                                              │ │
│  backend/reddit_ingestion.py  ◄── NEW MODULE                                │ │
│       ├─→ get_reddit_client()       [Auth with PRAW]                        │ │
│       ├─→ search_reddit_posts()     [API calls]                             │ │
│       ├─→ fetch_subreddit_posts()   [API calls]                             │ │
│       ├─→ store_reddit_mentions()   [DB insert]                             │ │
│       └─→ update_reddit_metrics()   [DB aggregate]                          │ │
│                                                                              │ │
└──────────────────────────────────────────────────────────────────────────────┘
         ↓                            ↓                            ↓
    ┌─────────────┐          ┌──────────────┐          ┌──────────────────┐
    │ Sentiment   │          │  Sentiment   │          │  Sentiment       │
    │ Analysis    │          │  Analysis    │          │  Analysis        │
    │ (Twitter)   │          │  (Reddit)    │          │  (Others)        │
    └─────────────┘          └──────────────┘          └──────────────────┘
         ↓                            ↓                            ↓
    backend/transformer_sentiment.py (shared module - uses HuggingFace)
         ↓                            ↓                            ↓
    ┌────────────────────────────────────────────────────────────────────────┐
    │                          PostgreSQL Database                            │
    │                       (ummatics_monitor)                                │
    ├────────────────────────────────────────────────────────────────────────┤
    │                                                                         │
    │  EXISTING TABLES:          NEW TABLES:            MODIFIED TABLES:     │
    │  ├─ weekly_snapshots       ├─ reddit_mentions     ├─ social_mentions   │
    │  ├─ social_mentions        ├─ reddit_daily_metrics     (platform='    │
    │  ├─ social_media_metrics   └─ reddit_subreddit_metrics   Reddit')      │
    │  ├─ website_metrics                              │                     │
    │  ├─ citations              SENTIMENT TABLES:    └─ sentiment           │
    │  ├─ news_mentions          ├─ social_sentiment_  (per-platform)        │
    │  └─ ...                    │  metrics                                   │
    │                            └─ (updated daily)                           │
    │                                                                         │
    └────────────────────────────────────────────────────────────────────────┘


                          API LAYER (REST Endpoints)
┌────────────────────────────────────────────────────────────────────────────┐
│  backend/api.py                                                             │
│                                                                             │
│  EXISTING ENDPOINTS:      NEW ENDPOINTS:           MODIFIED ENDPOINTS:   │
│  ├─ /api/overview         ├─ /api/reddit          ├─ /api/social         │
│  ├─ /api/social           ├─ /api/reddit/         │  (includes Reddit)    │
│  ├─ /api/website          │  sentiment            ├─ /api/sentiment       │
│  ├─ /api/citations        ├─ /api/reddit/        │  (per-platform       │
│  ├─ /api/news             │  subreddit/:name      │   comparison)         │
│  └─ /api/sentiment        └─ /api/reddit/search  │                       │
│                              ?q=keyword            └─ /api/overview       │
│                                                     (includes Reddit)      │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
         ↓              ↓              ↓              ↓              ↓
         │              │              │              │              │
    ┌────────────────────────────────────────────────────────────────┐
    │              FRONTEND (React/Tailwind CSS)                     │
    │                                                                │
    │  EXISTING TABS:        NEW TAB:        MODIFIED TABS:        │
    │  ├─ Overview           ├─ Reddit       ├─ Overview           │
    │  ├─ Social (Twitter)   │  Dashboard    │  (includes Reddit)   │
    │  ├─ Website            │  ├─ Daily     ├─ Social             │
    │  ├─ Citations          │  │ metrics    │  (includes Reddit)   │
    │  └─ News               │  ├─ Subreddit└─ Sentiment           │
    │                        │  │ breakdown   (per-platform)        │
    │                        │  ├─ Recent    │                      │
    │                        │  │ posts      └─ Overview            │
    │                        │  └─ Sentiment │  (Reddit metrics)    │
    │                        │     analysis  │                      │
    │                        │              │                      │
    │                        └─ Components: └─ Components:         │
    │                          ├─ RedditChart (Added)              │
    │                          ├─ RedditMetrics                    │
    │                          ├─ RedditSentiment                  │
    │                          └─ RedditMentions                   │
    │                                                               │
    └───────────────────────────────────────────────────────────────┘
         ↓              ↓              ↓              ↓
    Browser            Browser        Browser       Browser
    (localhost:5173)   (EC2 :5173)    (EC2:3000)   (AWS ALB)


                       REDDIT API LAYER (External)
┌────────────────────────────────────────────────────────────────────────────┐
│  reddit.com OAuth 2.0 Endpoints                                            │
│  ├─ POST https://oauth.reddit.com/api/v1/access_token  [Auth]            │
│  ├─ GET https://oauth.reddit.com/api/v1/me  [Get user info]              │
│  ├─ GET https://www.reddit.com/r/{subreddit}/search.json  [Search]        │
│  └─ GET https://www.reddit.com/r/{subreddit}/hot.json  [Hot posts]        │
│                                                                             │
│  PRAW Library (Python Reddit API Wrapper) handles all this                 │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Sequence Diagram

### Reddit Ingestion Sequence (Triggered Daily at 9:00 AM)

```
Timeline:
9:00 AM ─→ Scheduler triggers ingestion
    ↓
    ├─→ backend/ingestion.py::run_full_ingestion()
    │       ├─→ ingest_google_alerts()     [completes 9:05]
    │       ├─→ ingest_twitter()           [completes 9:10]
    │       ├─→ ingest_reddit()            [completes 9:25] ◄── NEW
    │       │       ↓
    │       │   reddit_ingestion.py::ingest_reddit()
    │       │       ├─→ get_reddit_client()  [auth with Reddit API]
    │       │       ├─→ search_reddit_posts(search_terms)
    │       │       │       ├─ "ummatics" ─→ ~10-20 posts
    │       │       │       ├─ keyword2    ─→ ~5-10 posts
    │       │       │       └─ keyword3    ─→ ~3-7 posts
    │       │       ├─→ fetch_subreddit_posts(subreddit_list)
    │       │       │       ├─ r/science      ─→ ~5 posts
    │       │       │       ├─ r/health       ─→ ~3 posts
    │       │       │       └─ r/subreddit1   ─→ ~2 posts
    │       │       ├─→ store_reddit_mentions(posts)
    │       │       │   INSERT 40-50 records into reddit_mentions
    │       │       │   ├─ post_id
    │       │       │   ├─ subreddit
    │       │       │   ├─ title, content
    │       │       │   ├─ author, upvotes, comments
    │       │       │   └─ sentiment = NULL (to be analyzed)
    │       │       │
    │       │       └─→ For each post: analyze_sentiment(title + content)
    │       │           ├─ Call transformer_sentiment.py
    │       │           ├─ Get sentiment label & score
    │       │           └─ UPDATE reddit_mentions SET sentiment, sentiment_score
    │       │
    │       ├─→ update_reddit_metrics()
    │       │   ├─ Aggregate daily: SUM(upvotes), AVG(comments), COUNT(*)
    │       │   ├─ Aggregate per-subreddit: GROUP BY subreddit
    │       │   └─ INSERT into reddit_daily_metrics, reddit_subreddit_metrics
    │       │
    │       ├─→ ingest_website_analytics()  [completes 9:30]
    │       ├─→ ingest_citations()          [completes 9:35]
    │       └─→ update_sentiment_metrics()  [completes 9:40]
    │               └─ Recompute social_sentiment_metrics for all platforms
    │
9:40 AM ─→ Ingestion complete
    ↓
    Next scheduled run: Tomorrow 9:00 AM
```

### User Dashboard Load Sequence

```
User navigates to "Reddit" tab
    ↓
    1. Frontend calls GET /api/reddit?token=xyz
    │      ↓
    │  backend/api.py::get_reddit()
    │      ├─ SELECT from reddit_daily_metrics (last 30 days)
    │      ├─ SELECT from reddit_subreddit_metrics (last 7 days)
    │      ├─ SELECT from reddit_mentions (last 20 records, ordered by upvotes)
    │      └─ RETURN JSON
    │      ↓
    │  ~50-100ms database query
    ↓
    2. Frontend calls GET /api/reddit/sentiment?token=xyz
    │      ↓
    │  backend/api.py::get_reddit_sentiment()
    │      ├─ SELECT COUNT(*) WHERE sentiment='positive'
    │      ├─ SELECT COUNT(*) WHERE sentiment='negative'
    │      ├─ SELECT COUNT(*) WHERE sentiment='neutral'
    │      ├─ SELECT AVG(sentiment_score)
    │      └─ RETURN JSON
    │      ↓
    │  ~50-100ms database query
    ↓
    3. Frontend renders dashboard
        ├─ RedditDashboard component
        │   ├─ LineChart: Daily mentions/engagement (from /api/reddit)
        │   ├─ SubredditTable: Top subreddits (from /api/reddit)
        │   ├─ MentionsList: Recent posts with badges (from /api/reddit)
        │   └─ SentimentCard: Sentiment breakdown (from /api/reddit/sentiment)
        ↓
    4. User sees complete Reddit analytics dashboard
```

---

## Database Relationship Diagram

```
┌──────────────────────────────┐
│   reddit_mentions (NEW)      │
├──────────────────────────────┤
│ id                    (PK)   │
│ post_id              (UQ)    │
│ week_start_date      (FK)    │── References weekly_snapshots
│ subreddit                    │── (indexed for filtering)
│ author                       │
│ title, content               │
│ upvotes, downvotes           │
│ comments_count               │
│ is_comment                   │
│ sentiment                    │── NULL → being analyzed, or 'positive'/'negative'/'neutral'
│ sentiment_score         (0.0-1.0)
│ sentiment_analyzed_at   (timestamp)
│ posted_at                    │
│ created_at                   │
└──────────────────────────────┘
         ↓ aggregated by
┌──────────────────────────────┐
│ reddit_daily_metrics (NEW)   │
├──────────────────────────────┤
│ id                    (PK)   │
│ date                  (UQ)   │
│ mentions_count               │
│ posts_count                  │
│ comments_count               │
│ avg_upvotes                  │
│ avg_comments                 │
│ total_engagement             │
│ created_at                   │
└──────────────────────────────┘
         ↓ aggregated by
┌──────────────────────────────────┐
│ reddit_subreddit_metrics (NEW)   │
├──────────────────────────────────┤
│ id                         (PK)  │
│ date, subreddit            (UQ)  │
│ mentions_count                   │
│ avg_upvotes                      │
│ avg_comments                     │
│ created_at                       │
└──────────────────────────────────┘


┌──────────────────────────────────────────┐
│ social_sentiment_metrics (UPDATED)       │
├──────────────────────────────────────────┤
│ id                              (PK)     │
│ date, platform                  (UQ)     │
│ positive_count,                          │
│ negative_count,                          │
│ neutral_count,                           │
│ average_sentiment_score                  │
│                                          │
│ Entries: date='2025-11-15'              │
│   ├─ platform='Twitter'  ─→ sentiment   │
│   ├─ platform='Reddit'   ─→ sentiment   │
│   └─ platform='News'     ─→ sentiment   │
│                                          │
└──────────────────────────────────────────┘

Existing tables remain unchanged, only new platform entries added:
┌──────────────────────────────┐
│   social_mentions            │
├──────────────────────────────┤
│ platform = 'Twitter'  ◄─ existing
│ platform = 'Reddit'   ◄─ new entries
│   ├─ post_id: Reddit post ID
│   ├─ author: subreddit + username
│   ├─ likes: mapped from upvotes
│   ├─ replies: mapped from comments_count
│   └─ sentiment: shared analysis
└──────────────────────────────┘
```

---

## Configuration & Environment Variables

```
.env / docker-compose.yml

REDDIT_INGESTION_ENABLED=1              # Toggle Reddit ingestion on/off
REDDIT_CLIENT_ID=xxxxx                  # From Reddit app settings
REDDIT_CLIENT_SECRET=xxxxx              # From Reddit app settings
REDDIT_USERNAME=your_reddit_username    # Reddit account username
REDDIT_PASSWORD=your_reddit_password    # Reddit account password
REDDIT_USER_AGENT="UmmaticsMonitor/1.0 by YourUsername"

REDDIT_SEARCH_TERMS="ummatics,keyword1,keyword2"    # Search terms (comma-separated)
REDDIT_SUBREDDITS="r/science,r/health"             # Target subreddits (comma-separated)

REDDIT_POSTS_PER_SEARCH=100             # Max posts per search (default: 100)
REDDIT_DAYS_LOOKBACK=7                  # How far back to search (default: 7)

USE_TRANSFORMER=1                        # Use transformer sentiment (existing var)
TRANSFORMER_SENTIMENT_MODEL=cardiffnlp/twitter-roberta-base-sentiment

# Scheduler runs existing ingestion.py::run_full_ingestion()
# which now calls ingest_reddit() on same schedule as Twitter
```

---

## Performance Metrics

### API Calls (Reddit → Backend)
- **Calls per ingestion cycle**: ~50-80
- **Rate limit**: 60 requests/minute (authenticated)
- **Actual usage**: ~1-2 per second during ingestion
- **Headroom**: 95%+ capacity available ✓

### Database Metrics
- **Records inserted per day**: ~40-60 posts, ~1 daily metric, ~3-5 subreddit metrics
- **Total storage per day**: ~500KB-1MB
- **Storage per month**: ~15-30MB ✓

### Processing Time
- **Ingestion duration**: ~15 minutes
- **Sentiment analysis**: ~30-50ms per post (transformer inference)
- **Total sentiment processing**: 20-50 seconds for 40-60 posts
- **Database writes**: ~5-10 seconds
- **Total Reddit ingestion time**: ~5-10 minutes ✓

### Dashboard Load Time
- **API response time**: ~100-200ms (2-3 database queries)
- **Frontend render time**: ~100-200ms (React state update)
- **Total time to dashboard**: ~300-400ms ✓

---

## Error Handling & Monitoring

```
Possible Errors & Recovery:

1. Reddit API Authentication Fails
   ├─ Log: "Failed to authenticate with Reddit API: {error}"
   ├─ Retry: Auto-retry with exponential backoff (max 3 times)
   └─ Fallback: Skip Reddit ingestion, continue with other sources

2. Reddit API Rate Limit Hit (429 error)
   ├─ Log: "Rate limit exceeded. Waiting 60 seconds..."
   ├─ Action: Wait 60 seconds, resume requests
   └─ PRAW handles this automatically

3. Database Connection Fails
   ├─ Log: "Database connection failed: {error}"
   ├─ Retry: Auto-retry after 5 seconds (max 3 times)
   └─ Fallback: Skip database update, alert to logs

4. Transformer Sentiment Unavailable
   ├─ Log: "Transformer unavailable, falling back to neutral"
   ├─ Action: Mark sentiment as 'neutral' with score 0.0
   └─ Retry: Next ingestion cycle will try again

Monitoring Points:
- Docker logs: docker-compose logs -f api
- Database: SELECT * FROM reddit_mentions WHERE sentiment_analyzed_at IS NULL
- Scheduler: Verify daily 9:00 AM execution
- Sentiment: Count sentiment distribution daily
```

---

## Deployment Checklist

- [ ] Create Reddit API app and get credentials
- [ ] Add environment variables to docker-compose.yml
- [ ] Create SQL migration script (new tables)
- [ ] Build new Docker image (with PRAW dependency)
- [ ] Test Reddit ingestion locally
- [ ] Deploy to AWS EC2
- [ ] Run database migration
- [ ] Restart docker-compose
- [ ] Verify ingestion logs
- [ ] Test API endpoints manually
- [ ] Deploy frontend changes
- [ ] Test dashboard in browser
- [ ] Monitor logs for 24 hours
- [ ] Document any issues found
```
