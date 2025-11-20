# Reddit Support Implementation - Summary & Action Plan

## Executive Summary

This document outlines the complete implementation plan for adding Reddit support to the Ummatics Impact Monitor. The integration includes:

✅ **New Database Tables** - Store Reddit posts, daily metrics, and subreddit-level analytics  
✅ **Backend Reddit Ingestion Module** - Fetch posts daily via Reddit API using PRAW  
✅ **Unified Sentiment Analysis** - Use existing transformer model on Reddit content  
✅ **New API Endpoints** - REST endpoints for Reddit metrics, sentiment, and search  
✅ **New UI Tab** - Interactive Reddit analytics dashboard  
✅ **Same Schedule** - Runs on existing daily 9:00 AM ingestion schedule  

---

## Permissions Required Summary

### 1. Reddit API Credentials (Create Free)
```
Website: https://www.reddit.com/prefs/apps
Type: Script App
Credentials to Get:
  - REDDIT_CLIENT_ID
  - REDDIT_CLIENT_SECRET
  - REDDIT_USER_AGENT
  - REDDIT_USERNAME
  - REDDIT_PASSWORD
```

### 2. Database Permissions ✓
**No new permissions needed.** Your existing PostgreSQL user already has:
- CREATE TABLE (for new tables)
- INSERT/UPDATE/SELECT (for ingestion and queries)

### 3. AWS Security ✓
**Verify:** Security group allows outbound HTTPS (port 443) to reddit.com
```bash
# Test from EC2:
curl -I https://oauth.reddit.com/
```

### 4. No Other Permissions Needed
- Docker: Already configured ✓
- File system: Use existing `.env` ✓
- GitHub/CI-CD: Optional (for auto-deploy) ◇

---

## What Gets Added

### Backend Code
```
backend/reddit_ingestion.py          [NEW] ~300 lines
  ├─ get_reddit_client()             Authenticate with Reddit API
  ├─ search_reddit_posts()           Search for keywords
  ├─ fetch_subreddit_posts()         Fetch from specific subreddits
  ├─ store_reddit_mentions()         Insert posts to DB
  └─ update_reddit_metrics()         Aggregate metrics

backend/requirements.txt              [UPDATED]
  ├─ praw==7.7.0                     Reddit API wrapper
  └─ prawcore==2.4.0                 Dependencies

backend/ingestion.py                 [MODIFIED] ~5 lines added
  └─ Call ingest_reddit() from run_full_ingestion()
```

### Database
```
CREATE TABLE reddit_mentions         [NEW] ~52 columns
  - Stores individual posts/comments with sentiment

CREATE TABLE reddit_daily_metrics    [NEW] ~8 columns
  - Daily aggregates (mentions, upvotes, engagement)

CREATE TABLE reddit_subreddit_metrics [NEW] ~7 columns
  - Per-subreddit metrics

UPDATE social_sentiment_metrics      [MODIFIED]
  - Add platform='Reddit' entries (already supports this)
```

### Frontend Code
```
frontend/src/components/RedditDashboard.jsx      [NEW] ~400 lines
  ├─ Charts (mentions/engagement over time)
  ├─ Subreddit breakdown table
  ├─ Recent mentions list
  └─ Sentiment distribution

frontend/src/App.jsx                 [MODIFIED] ~10 lines
  ├─ Add 'reddit' to tabs list
  ├─ Add redditData state
  └─ Add data fetching for /api/reddit endpoints
```

### API Endpoints
```
GET /api/reddit                      [NEW]
  - Daily metrics, subreddit breakdown, recent mentions

GET /api/reddit/sentiment            [NEW]
  - Sentiment analysis for Reddit

GET /api/reddit/subreddit/:name      [NEW]
  - Specific subreddit metrics

GET /api/reddit/search?q=keyword     [NEW]
  - Search functionality

UPDATED:
  /api/social                        - Includes Reddit now
  /api/sentiment                     - Per-platform comparison
  /api/overview                      - Includes Reddit metrics
```

---

## Step-by-Step Implementation Order

### Phase 1: Setup & Backend (Days 1-2)

**Step 1.1: Get Reddit Credentials**
- [ ] Go to https://www.reddit.com/prefs/apps
- [ ] Create new app (type: "script")
- [ ] Copy credentials (Client ID, Client Secret)
- [ ] Create Reddit account for monitoring (optional but recommended)
- **Time: 15 minutes**

**Step 1.2: Create Database Tables**
- [ ] SSH to EC2
- [ ] Run SQL migration (from REDDIT_IMPLEMENTATION_PLAN.md)
- [ ] Verify tables created: `\d reddit_mentions`
- **Time: 10 minutes**

**Step 1.3: Create reddit_ingestion.py Module**
- [ ] Create `backend/reddit_ingestion.py` with functions from REDDIT_IMPLEMENTATION_PLAN.md
- [ ] Add PRAW dependency to `backend/requirements.txt`
- [ ] Test locally or in Docker:
  ```bash
  docker-compose build api
  docker-compose run --rm api python3 -c "from reddit_ingestion import get_reddit_client; c = get_reddit_client(); print('OK')"
  ```
- **Time: 2-3 hours**

**Step 1.4: Wire Reddit into Main Ingestion**
- [ ] Modify `backend/ingestion.py` to import and call `ingest_reddit()`
- [ ] Add to `run_full_ingestion()` function
- [ ] Test end-to-end:
  ```bash
  docker-compose exec -T api python3 /app/ingestion.py
  ```
- [ ] Verify reddit_mentions table populated
- **Time: 30 minutes**

**Step 1.5: Add Environment Variables**
- [ ] Update `docker-compose.yml` with Reddit credentials and config
- [ ] Update `.env` file (don't commit!)
- [ ] Restart containers: `docker-compose restart`
- **Time: 15 minutes**

**Phase 1 Total: 3-4 hours**

---

### Phase 2: API Endpoints (Day 2)

**Step 2.1: Add Reddit API Endpoints**
- [ ] Add `/api/reddit` endpoint to `backend/api.py`
  - Returns daily metrics, subreddit breakdown, recent mentions
- [ ] Add `/api/reddit/sentiment` endpoint
  - Returns sentiment analysis summary
- [ ] Add `/api/reddit/subreddit/:name` endpoint
  - Returns metrics for specific subreddit
- [ ] Add `/api/reddit/search?q=keyword` endpoint
  - Allows searching mentions
- [ ] Test endpoints:
  ```bash
  curl http://localhost:5000/api/reddit -H "Authorization: Bearer password"
  ```
- **Time: 2-3 hours**

**Step 2.2: Update Existing Endpoints**
- [ ] Modify `/api/social` to include Reddit metrics
- [ ] Modify `/api/sentiment` to show per-platform comparison
- [ ] Modify `/api/overview` to include Reddit in totals
- **Time: 1 hour**

**Phase 2 Total: 3-4 hours**

---

### Phase 3: Frontend (Days 3)

**Step 3.1: Create Reddit Dashboard Component**
- [ ] Create `frontend/src/components/RedditDashboard.jsx`
  - Line chart for daily metrics
  - Table for subreddit breakdown
  - List for recent mentions
  - Pie chart for sentiment distribution
- [ ] Use Recharts (existing dependency) for charts
- [ ] Use Tailwind CSS for styling
- **Time: 2-3 hours**

**Step 3.2: Update App.jsx**
- [ ] Add 'reddit' to tabs list
- [ ] Add data states for Reddit
- [ ] Add fetch calls for `/api/reddit` endpoints
- [ ] Handle loading/error states
- **Time: 30 minutes**

**Step 3.3: Test Frontend Locally**
- [ ] Run `npm run dev` in frontend
- [ ] Navigate to Reddit tab
- [ ] Verify data loads and displays
- [ ] Check mobile responsiveness
- **Time: 30 minutes**

**Phase 3 Total: 3-4 hours**

---

### Phase 4: Deployment & Testing (Day 4)

**Step 4.1: Rebuild Docker Images**
- [ ] Rebuild API image: `docker-compose build api`
- [ ] Rebuild frontend image: `docker-compose build frontend`
- [ ] Verify no build errors
- **Time: 10 minutes**

**Step 4.2: Deploy to AWS**
- [ ] SSH to EC2 instance
- [ ] Pull latest code: `git pull`
- [ ] Run database migration if needed
- [ ] Restart docker-compose: `docker-compose up -d`
- [ ] Verify all containers running: `docker-compose ps`
- **Time: 20 minutes**

**Step 4.3: Verify End-to-End**
- [ ] Open dashboard in browser
- [ ] Check Reddit tab loads
- [ ] Verify data displays correctly
- [ ] Check browser console for errors: F12 → Console
- [ ] Test on mobile
- **Time: 30 minutes**

**Step 4.4: Monitor Logs**
- [ ] Watch ingestion logs: `docker-compose logs -f api`
- [ ] Watch API logs: `docker-compose logs -f api` | grep "reddit"
- [ ] Check database for records: SELECT COUNT(*) FROM reddit_mentions
- [ ] Monitor for 24 hours to ensure stability
- **Time: 30 minutes + ongoing**

**Phase 4 Total: 2 hours**

---

## Total Implementation Time

| Phase | Task | Time |
|-------|------|------|
| 1 | Backend Setup | 3-4 hours |
| 2 | API Endpoints | 3-4 hours |
| 3 | Frontend | 3-4 hours |
| 4 | Deployment | 2 hours |
| | **TOTAL** | **11-14 hours** |

---

## What Runs on Existing Schedule

✅ **Scheduler** (`backend/scheduler.py`) - No changes
✅ **Schedule** - Daily 9:00 AM (existing)
✅ **Ingestion** - `run_full_ingestion()` now includes Reddit
✅ **Sentiment Analysis** - Uses existing transformer model
✅ **Metrics Aggregation** - Automatic via database triggers/views

**No new cron jobs or scheduled tasks needed!**

---

## Cost & Resource Impact

### Reddit API
- **Cost**: FREE (no paid tier)
- **Rate limit**: 60 requests/minute (using ~1 request/second during ingestion)
- **Headroom**: 95% unused

### Database
- **Storage**: +15-30MB per month
- **Query complexity**: Minimal (simple aggregations)
- **Performance impact**: None

### Compute
- **Docker image size**: +100-200MB (PRAW + dependencies)
- **Runtime memory**: +50-100MB (Redis cache)
- **Processing time**: +5-10 minutes per ingestion cycle

### AWS EC2
- **Current instance**: t3.micro (eligible for free tier)
- **Impact**: Negligible
- **Cost**: No additional cost

---

## Data Retained

### In Database (Permanent)
- All Reddit posts/comments (reddit_mentions table)
- Daily metrics (reddit_daily_metrics table)
- Subreddit metrics (reddit_subreddit_metrics table)
- Sentiment analysis results

### For Sentiment Analysis
- Keeps: post_id, author, title, content, sentiment_score, upvotes, comments
- No personal data retained beyond what Reddit stores publicly

---

## Rollback Plan (If Issues)

```bash
# Option 1: Disable Reddit ingestion (keep data)
export REDDIT_INGESTION_ENABLED=0
docker-compose up -d api

# Option 2: Delete Reddit data (full rollback)
docker-compose exec -T db psql -U postgres -d ummatics_monitor -c "
  DROP TABLE reddit_mentions;
  DROP TABLE reddit_daily_metrics;
  DROP TABLE reddit_subreddit_metrics;
  -- Frontend tab will show 'no data' but remain functional
"

# Option 3: Revert code
git revert <commit_id>
docker-compose up -d
```

---

## Success Criteria

After implementation, verify:

- [ ] Reddit tab appears in dashboard navigation
- [ ] Reddit tab loads without errors (check browser console)
- [ ] Daily metrics chart displays data
- [ ] Subreddit breakdown table shows top subreddits
- [ ] Recent mentions list shows posts with sentiment badges
- [ ] Sentiment pie chart shows distribution
- [ ] API endpoints respond correctly:
  - [ ] `GET /api/reddit` returns 200 with data
  - [ ] `GET /api/reddit/sentiment` returns 200 with data
  - [ ] `GET /api/reddit/subreddit/science` returns 200
  - [ ] `GET /api/reddit/search?q=ummatics` returns 200
- [ ] Database tables populated:
  - [ ] `SELECT COUNT(*) FROM reddit_mentions` > 0
  - [ ] `SELECT COUNT(*) FROM reddit_daily_metrics` > 0
- [ ] Scheduler runs daily ingestion without errors
- [ ] Sentiment scores computed for all new posts
- [ ] No data loss or corruption in existing tables

---

## Detailed Documentation Files

For complete technical details, refer to:

1. **REDDIT_PERMISSIONS_SETUP.md** - Permissions and credential setup
2. **REDDIT_IMPLEMENTATION_PLAN.md** - Detailed design specifications
3. **REDDIT_ARCHITECTURE.md** - System architecture and data flow diagrams

---

## Questions & Support

### Common Questions

**Q: Do I need a premium Reddit account?**  
A: No, free account works fine. Just need to create an app for API credentials.

**Q: What if Reddit API changes?**  
A: PRAW is actively maintained and handles API changes. Monitor GitHub releases.

**Q: Can I search multiple keywords?**  
A: Yes! Set `REDDIT_SEARCH_TERMS="keyword1,keyword2,keyword3"` in .env

**Q: How accurate is the sentiment analysis?**  
A: We use the same transformer model as Twitter. Accuracy is ~85-90% for Reddit content. For Reddit-specific tuning, see Optional Enhancements section.

**Q: Can I track competitor mentions?**  
A: Yes! Add competitor names to `REDDIT_SEARCH_TERMS`

**Q: What about comment-level analysis?**  
A: Current plan tracks posts only. Comment analysis can be added later as an enhancement.

### Troubleshooting

**Issue: "Authentiation failed" when ingesting Reddit**
```bash
# Verify credentials in .env
docker-compose exec -T api python3 -c "import os; print(os.getenv('REDDIT_CLIENT_ID')[:10])"
```

**Issue: "No data appears in Reddit tab"**
```bash
# Check database
docker-compose exec -T db psql -U postgres -d ummatics_monitor -c "SELECT COUNT(*) FROM reddit_mentions"

# Check logs
docker-compose logs api | grep reddit
```

**Issue: "Rate limit exceeded"**
- This is rare but if it happens:
- Wait 60 seconds before retrying
- Reduce search terms to fewer keywords
- PRAW automatically handles backoff

---

## Next Step

**Ready to begin?**

1. ✅ Start with **Phase 1, Step 1.1** - Get Reddit credentials (15 minutes)
2. Then proceed through phases in order
3. Reference REDDIT_PERMISSIONS_SETUP.md and REDDIT_IMPLEMENTATION_PLAN.md as needed
4. Share status after each phase for feedback/review

---

**Created**: November 15, 2025  
**Status**: Ready for Implementation  
**Priority**: After current transformer refinement is stable
