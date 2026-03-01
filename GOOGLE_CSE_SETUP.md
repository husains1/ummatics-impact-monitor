# Google Custom Search API Setup

## Why We Need This

Reddit RSS feeds only search post titles and content - they don't include comments. Google Custom Search API solves this by:
- Indexing entire Reddit pages including all comments
- Finding posts where "ummatics" appears only in comments
- Example: https://www.reddit.com/r/Muslim/comments/1nvwzmq/ has "Ummatics" in a comment, not the post itself

**Current Status:** The system works without this (RSS-only), but you'll miss mentions in comments. Setting up Google CSE enables comprehensive Reddit coverage.

## Setup Steps

### 1. Get Google API Key (5 minutes)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Navigate to: **APIs & Services → Credentials**
4. Click **"+ CREATE CREDENTIALS"** → Select **"API key"**
5. Copy the generated API key
6. Click **"Edit API key"** → Under "API restrictions":
   - Select **"Restrict key"**
   - Check **"Custom Search API"**
   - Click **"Save"**

**Free Tier:** 100 queries per day (sufficient for daily ingestion runs)

### 2. Create Custom Search Engine (3 minutes)

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Click **"Add"** to create new search engine
3. Fill in the form:
   - **Search engine name**: "Reddit Ummatics Monitor"
   - **What to search**: Select **"Search specific sites or pages"**
   - **Sites to search**: Enter `reddit.com/*`
   - **Language**: English
4. Click **"Create"**
5. On the next page, click **"Customize"** → **"Setup"**
6. Find **"Search engine ID"** (looks like: `a1b2c3d4e5f6g7h8i`)
7. Copy this ID

### 3. Add Credentials to .env File

Add these two lines to your `.env` file:

```bash
GOOGLE_API_KEY=your_api_key_from_step_1
GOOGLE_CSE_ID=your_search_engine_id_from_step_2
```

Example:
```bash
GOOGLE_API_KEY=AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GOOGLE_CSE_ID=a1b2c3d4e5f6g7h8i
```

### 4. Rebuild and Deploy

```bash
# Local build
docker build -t 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest ./backend

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 182758038500.dkr.ecr.us-east-1.amazonaws.com
docker push 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest

# Deploy on EC2
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'cd ~/ummatics-impact-monitor && docker-compose pull && docker-compose up -d'
```

### 5. Verify It's Working

Check the logs for Google CSE activity:

```bash
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'docker logs --tail 100 ummatics_scheduler | grep -i "google"'
```

Look for:
```
INFO: Starting Google Custom Search for Reddit posts...
INFO: Found X Reddit posts via Google Custom Search
INFO: ✓ Ingested from Google (comments): r/Muslim - Islamic Newsletter...
```

## How It Works

1. **Daily Run**: Scheduler calls `google_search_reddit_posts()` during ingestion
2. **API Query**: Searches Google for `site:reddit.com ("ummatics" OR "ummatic")`
3. **Pagination**: Fetches up to 100 results (10 per page)
4. **Reddit JSON API**: For each URL, fetches post + comments from `URL.json`
5. **Keyword Detection**: Checks title, content, AND comments for keywords
6. **Database Insert**: Saves with note about where keyword was found
7. **Deduplication**: Uses `ON CONFLICT (post_url) DO NOTHING`

## Graceful Degradation

If you **don't** set up Google CSE:
- ✅ System continues working normally
- ✅ RSS feeds still discover new posts
- ✅ No errors or crashes
- ❌ Misses posts where keywords only appear in comments
- Logs show: `WARNING: Google Custom Search not configured (missing GOOGLE_API_KEY or GOOGLE_CSE_ID). Skipping...`

## Cost

**Free Tier (Recommended):**
- **100 queries/day** = FREE forever
- No credit card required
- **Your usage**: ~10 queries/day (one daily ingestion run)
- **Utilization**: Only 10% of free tier
- You could run ingestion 10x per day and still be free

**Math breakdown:**
- 1 search with pagination (100 results) = 10 API queries
- Daily ingestion runs once = 10 queries/day
- Free tier limit = 100 queries/day
- **Plenty of headroom** for future expansion

**Paid Tier (If Needed):**
- After 100 queries/day: $5 per 1,000 queries
- Max: 10,000 queries/day total
- **You won't need this** - your usage is too low

## Troubleshooting

**"API key not valid" error:**
- Make sure you enabled "Custom Search API" in API restrictions
- Check that the API key is copied correctly to .env

**"Search engine not found" error:**
- Verify GOOGLE_CSE_ID is correct (from Programmable Search Engine dashboard)
- Check that search engine is set to search `reddit.com/*`

**No results found:**
- Normal if Google hasn't indexed new posts yet
- RSS feeds will catch them in real-time
- Google CSE handles historical coverage

**Rate limit exceeded:**
- Free tier = 100 queries/day
- Check logs to see how many queries you're using
- Consider reducing search frequency if needed

## Alternative: Manual Search

If you don't want to set up the API, you can manually search Google:
1. Go to https://www.google.com/search?q=site:reddit.com+"ummatics"
2. Review results
3. Manually check any posts with comments

The API automates this process and runs it daily.
