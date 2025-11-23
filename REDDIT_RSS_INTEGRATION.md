# Reddit RSS Integration Guide

## Overview

The Ummatics Impact Monitor now supports Reddit integration via RSS feeds, **without requiring Reddit API access**. This allows you to track Reddit mentions without the complexity of OAuth authentication.

## How It Works

Reddit provides public RSS feeds for:
- **Subreddit feeds**: All posts from a specific subreddit
- **Search feeds**: Posts matching a search query
- **User feeds**: Posts from a specific user

These feeds are publicly accessible and don't require API keys or authentication.

## Configuration

### 1. Environment Variable

Add Reddit RSS URLs to your `.env` file:

```bash
# Reddit RSS Feeds (comma-separated)
REDDIT_RSS_URLS=https://www.reddit.com/search.rss?q=ummatics,https://www.reddit.com/r/islam/search.rss?q=ummatics
```

Multiple feeds can be specified, separated by commas.

### 2. RSS Feed URL Formats

#### Search All of Reddit
```
https://www.reddit.com/search.rss?q=ummatics
https://www.reddit.com/search.rss?q=muslim+education
```

#### Search Within a Subreddit
```
https://www.reddit.com/r/islam/search.rss?q=ummatics
https://www.reddit.com/r/education/search.rss?q=ummatics
```

#### All Posts from a Subreddit
```
https://www.reddit.com/r/islam/.rss
https://www.reddit.com/r/education/.rss
```

#### Posts from a Specific User
```
https://www.reddit.com/user/username/.rss
```

#### Advanced Search Parameters
```
# Sort by new
https://www.reddit.com/search.rss?q=ummatics&sort=new

# Sort by top
https://www.reddit.com/search.rss?q=ummatics&sort=top

# Time filter (day, week, month, year, all)
https://www.reddit.com/search.rss?q=ummatics&t=week
```

## Features

### ✅ Implemented

1. **Automatic Reddit Mention Collection**
   - Fetches posts from configured RSS feeds
   - Stores in `social_mentions` table with platform='Reddit'
   - Runs daily at 9:00 AM (via scheduler)

2. **Sentiment Analysis**
   - Analyzes Reddit post titles and content
   - Uses transformer-based model (same as Twitter)
   - Stores sentiment scores and labels

3. **Daily Metrics Tracking**
   - Tracks mention counts per day
   - Updates `social_media_daily_metrics` table
   - Updates `social_sentiment_metrics` table

4. **API Integration**
   - Reddit mentions appear in `/api/social` endpoint
   - Sentiment data in `/api/sentiment` endpoint
   - No frontend changes needed (automatic)

### ⚠️ Limitations

1. **No Engagement Metrics**
   - RSS feeds don't provide upvotes, comment counts
   - These fields are set to 0 in the database
   - Future: Could be added via web scraping or API

2. **No Follower Count**
   - Reddit doesn't have "followers" in the same way as Twitter
   - Follower count is set to 0

3. **Limited Post History**
   - RSS feeds typically return only the 25 most recent posts
   - For historical data, you'd need the Reddit API

## Database Structure

Reddit mentions use the existing `social_mentions` table:

```sql
INSERT INTO social_mentions
(week_start_date, platform, post_id, author, content, post_url, posted_at,
 likes, retweets, replies, sentiment, sentiment_score, sentiment_analyzed_at)
VALUES (..., 'Reddit', ...)
```

Fields mapping:
- `platform`: 'Reddit'
- `post_id`: Reddit post ID
- `author`: Reddit username
- `content`: Post title + body text (truncated to 1000 chars)
- `post_url`: Direct link to Reddit post
- `likes`: 0 (not available via RSS)
- `retweets`: 0 (N/A for Reddit)
- `replies`: 0 (not available via RSS)
- `sentiment`: Automatically analyzed
- `sentiment_score`: Confidence score

## Usage

### Manual Run

Test Reddit ingestion:

```bash
# Local
cd backend
python -c "from ingestion import ingest_reddit; ingest_reddit()"

# Docker
docker-compose exec api python -c "from ingestion import ingest_reddit; ingest_reddit()"
```

### Automatic Scheduling

Reddit ingestion runs automatically as part of the daily scheduler (9:00 AM):

```python
def run_full_ingestion():
    ingest_google_alerts()
    ingest_reddit()        # <-- Added
    ingest_twitter()
    ingest_google_analytics()
    ingest_openalex()
    update_weekly_snapshot()
```

### View in Dashboard

Reddit mentions will automatically appear:

1. **Social Tab**: Mixed with Twitter mentions
2. **Sentiment Charts**: Reddit sentiment included
3. **Platform Filter**: Can be filtered by platform (if implemented in frontend)

## Testing

### 1. Verify RSS Feed Works

Test a feed URL in your browser:
```
https://www.reddit.com/search.rss?q=ummatics
```

You should see XML output with Reddit posts.

### 2. Run Manual Ingestion

```bash
docker-compose exec api python ingestion.py
```

Check logs for:
```
INFO - Starting Reddit ingestion...
INFO - Fetching Reddit RSS feed: https://www.reddit.com/search.rss?q=ummatics
INFO - Reddit ingestion complete. New mentions: 5
```

### 3. Check Database

```bash
docker-compose exec db psql -U ummatics_user -d ummatics_monitor
```

```sql
-- Check Reddit mentions
SELECT COUNT(*) FROM social_mentions WHERE platform = 'Reddit';

-- View recent Reddit mentions
SELECT author, content, posted_at, sentiment
FROM social_mentions
WHERE platform = 'Reddit'
ORDER BY posted_at DESC
LIMIT 5;

-- Check daily metrics
SELECT * FROM social_media_daily_metrics WHERE platform = 'Reddit';

-- Check sentiment metrics
SELECT * FROM social_sentiment_metrics WHERE platform = 'Reddit';
```

### 4. Check API

```bash
# Get social data (includes Reddit)
curl http://localhost:5000/api/social \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get sentiment data (includes Reddit)
curl http://localhost:5000/api/sentiment \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Troubleshooting

### No Reddit Mentions Appearing

1. **Check Environment Variable**
   ```bash
   docker-compose exec api env | grep REDDIT
   ```
   Should show: `REDDIT_RSS_URLS=...`

2. **Verify RSS Feed URLs**
   - Test each URL in browser
   - Make sure they return XML/RSS content
   - Check for typos in URLs

3. **Check Logs**
   ```bash
   docker-compose logs api | grep -i reddit
   ```

4. **Manual Test**
   ```bash
   docker-compose exec api python -c "
   import os
   urls = os.getenv('REDDIT_RSS_URLS', '').split(',')
   print('URLs:', urls)
   "
   ```

### RSS Feed Parsing Errors

1. **Invalid XML**
   - Reddit sometimes returns HTML instead of RSS
   - Add `.rss` extension to URLs
   - Use `old.reddit.com` if needed

2. **Rate Limiting**
   - Reddit may rate limit RSS requests
   - Add delays between feeds (already implemented)
   - Use fewer RSS URLs

### Sentiment Analysis Issues

- Sentiment uses the same transformer model as Twitter
- If sentiment is showing as 'neutral' for all posts, check transformer configuration
- Verify `USE_TRANSFORMER=1` in environment

## Future Enhancements

### Option 1: Add Engagement Metrics via API

If you later get Reddit API access, you can enhance the `ingest_reddit()` function to fetch engagement data:

```python
def fetch_reddit_engagement(post_id):
    """Fetch upvotes and comment count from Reddit API"""
    # Implementation using PRAW or requests
    pass
```

### Option 2: Web Scraping

Add Selenium/BeautifulSoup to scrape engagement metrics:

```python
def scrape_reddit_engagement(post_url):
    """Scrape upvotes and comments from post page"""
    # Implementation using BeautifulSoup
    pass
```

### Option 3: Frontend Filtering

Update the dashboard to filter by platform:

```javascript
// Filter mentions by platform
const redditMentions = mentions.filter(m => m.platform === 'Reddit')
const twitterMentions = mentions.filter(m => m.platform === 'Twitter')
```

## Benefits of RSS Approach

✅ **No API Key Required**: Works without Reddit API credentials
✅ **No Rate Limits**: RSS feeds are less restricted
✅ **Simple Implementation**: Same pattern as Google Alerts
✅ **No Authentication**: No OAuth complexity
✅ **Public Data Only**: Stays within Reddit's ToS

## Comparison: RSS vs API

| Feature | RSS Feed | Reddit API |
|---------|----------|------------|
| Authentication | None | OAuth required |
| Rate Limits | Relaxed | Strict (60 req/min) |
| Historical Data | Last ~25 posts | Full history |
| Engagement Metrics | No | Yes (upvotes, comments) |
| Search | Yes | Yes |
| Implementation | Very simple | Complex |
| Cost | Free | Free (with limits) |

## Example RSS Feed Strategies

### Strategy 1: Keyword Monitoring
```bash
REDDIT_RSS_URLS=https://www.reddit.com/search.rss?q=ummatics,https://www.reddit.com/search.rss?q="muslim education"
```

### Strategy 2: Subreddit Monitoring
```bash
REDDIT_RSS_URLS=https://www.reddit.com/r/islam/.rss,https://www.reddit.com/r/education/.rss,https://www.reddit.com/r/nonprofit/.rss
```

### Strategy 3: Hybrid Approach
```bash
REDDIT_RSS_URLS=https://www.reddit.com/search.rss?q=ummatics,https://www.reddit.com/r/islam/search.rss?q=education,https://www.reddit.com/user/ummatics/.rss
```

## Next Steps

1. **Configure RSS URLs**: Update `.env` with relevant Reddit search feeds
2. **Test Ingestion**: Run manual ingestion to verify it works
3. **Monitor Logs**: Check daily scheduler logs for Reddit activity
4. **View Dashboard**: Check Social tab for Reddit mentions
5. **Adjust Feeds**: Refine RSS URLs based on results

## Support

For issues or questions:
- Check logs: `docker-compose logs api | grep -i reddit`
- Review database: `SELECT * FROM social_mentions WHERE platform = 'Reddit'`
- Test RSS feeds manually in browser
- Verify environment variables are set correctly

---

**Status**: ✅ Implemented and Ready
**Version**: 1.0.0
**Date**: November 23, 2025
**Dependencies**: feedparser (already installed)
**Breaking Changes**: None
