# Lessons Learned - Ummatics Impact Monitor

## Critical Deployment Facts (Dec 7, 2025)

### THIS PROJECT'S DEPLOYMENT ARCHITECTURE
**Read this FIRST before making any statements about the deployment:**

- **EC2 Instance IP**: 3.226.110.16
- **Frontend/Dashboard URL**: http://3.226.110.16:3000 (port 3000, NOT 5000)
- **Backend API URL**: http://3.226.110.16:5000 (internal use only, typically not accessed directly by users)
- **Primary User Access**: Port 3000 frontend, which internally calls the backend API

**NEVER say "localhost" when referring to the public deployment URLs.**
- localhost only works from INSIDE the EC2 instance
- External access uses the public IP: 3.226.110.16
- Frontend serves the dashboard on port 3000
- Backend API on port 5000 is for the frontend to call, not for direct user access

---

## Citation Cleanup Implementation (Dec 7, 2025)

### Problem
Duplicate citations and dead URLs appearing in the UI. Example duplicates:
- "Editorial Note David H. Warren..." appeared twice
- "From Ummatic Muslims to State-centered Bosniacs" appeared twice
- Some URLs returned 404 errors (e.g., https://jkk.jurnal.unej.ac.id/index.php/JKK/article/view/53703)

### Solution
Implemented `cleanup_citations()` function that runs before each citation ingestion:

1. **Added `is_dead` column** to citations table (BOOLEAN DEFAULT FALSE)
2. **URL validation**: Uses `requests.head()` to check if each citation URL is accessible
   - HTTP 4xx/5xx status codes → mark as dead
   - Connection errors/timeouts → mark as dead
3. **Duplicate detection**: Tracks citations by title
   - Prefers citations with working URLs over dead ones
   - If both working or both dead, keeps newer publication date
   - If same pub date, keeps more recently created entry
4. **Filtering**: API queries now include `WHERE is_dead = FALSE`

### Implementation Details
```python
# Check URL with HEAD request (faster than GET)
response = requests.head(source_url, timeout=10, allow_redirects=True)
if response.status_code >= 400:
    is_url_dead = True

# Duplicate resolution logic
if title in seen_titles:
    # Keep the one with working URL, or newer pub_date, or newer created_at
    keep_current = decide_which_to_keep(...)
```

### Key Takeaways
- Use `requests.head()` instead of `GET` for URL validation (much faster)
- Track duplicates by title, not by work_id (work_id might differ for same paper)
- Run cleanup BEFORE ingestion to prevent re-inserting dead citations
- Always check schema column names before adding new columns (verified `is_dead` added correctly)
- **Limitation**: URL validation is point-in-time - a URL working during cleanup might fail later (502 errors can be intermittent)
- **Similar but different papers**: Citations with similar titles/authors but different work_ids are NOT duplicates
  - Example: "Democracy in the Framework of Shura" vs "Islam and Democracy" - both by same authors, different papers
  - Duplicate detection only marks citations with EXACTLY the same title as duplicates

---

## Schema Column Name Verification (Dec 7, 2025)

### Problem
After fixing `posted_at`/`content`/`post_url` column names, encountered another 500 error: "column 'sentiment_score' does not exist" when querying `social_sentiment_metrics` table.

### Root Cause
The sentiment summary query was looking at the **wrong table**:
- Query used: `social_sentiment_metrics` table with columns `sentiment_score` and `sentiment_label`
- Actual schema: 
  - `social_sentiment_metrics` has `average_sentiment_score` (not `sentiment_score`) and no `sentiment_label`
  - `social_mentions` has `sentiment` (VARCHAR) and `sentiment_score` (DECIMAL)

### Solution
Changed query to use the correct table and column names:
```python
# WRONG - querying aggregated metrics table
FROM social_sentiment_metrics
WHERE date >= %s AND date <= %s

# CORRECT - querying individual mentions table
FROM social_mentions
WHERE week_start_date = %s
```

Also fixed column references:
- `sentiment_label` → `sentiment` (the actual column name)
- Changed from date range (`date >= %s AND date <= %s`) to single week match (`week_start_date = %s`)

### Key Takeaways
- **Always verify which table contains the columns you need** - don't assume based on table names
- Use `grep_search` on `schema.sql` to confirm exact column names AND which table they belong to
- Aggregated tables (`social_sentiment_metrics`) vs raw data tables (`social_mentions`) have different structures
- Test queries after ANY schema-related fix to catch cascading column name errors
- **PostgreSQL set-returning functions (like `unnest()`) cannot be used in `HAVING` clauses**
  - Wrong: `HAVING LENGTH(unnest(string_to_array(...))) > 4`
  - Correct: Use subquery to unnest first, then filter in outer `WHERE` clause
- **CRITICAL: Pull from the frontend and check using Chrome DevTools after EACH and EVERY deployment**
  - Open http://3.226.110.16:3000 in Chrome
  - **Login first** - the dashboard requires authentication with DASHBOARD_PASSWORD from .env
  - Open DevTools (F12) → Network tab
  - Hard refresh (Ctrl+Shift+R) to bypass cache
  - Check for 500 errors or failed API calls
  - Verify all data loads correctly before considering deployment complete
  - **Note**: Testing API endpoints directly (curl/wget) will fail with "Unauthorized" - must test through the authenticated frontend
- **When stuck in a loop repeating same actions**: User is likely canceling commands for a reason
  - Don't retry the exact same approach - user is blocking it intentionally
  - Switch to alternative methods (e.g., check logs instead of testing endpoint directly)
  - Pay attention to user feedback and adapt approach immediately
- **Deployment verification limitations**: 
  - ~~The dashboard requires authentication - cannot be tested programmatically without exposing password~~
  - **CAN use .env file to get DASHBOARD_PASSWORD for testing** - it's in .gitignore so won't be committed
  - Test script:
    ```bash
    TOKEN=$(curl -s -X POST http://3.226.110.16:3000/api/auth -H "Content-Type: application/json" -d '{"password":"'$(grep DASHBOARD_PASSWORD .env | cut -d'=' -f2)'"}' | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))")
    curl -s -H "Authorization: Bearer $TOKEN" http://3.226.110.16:3000/api/overview | python3 -c "import sys, json; data = json.load(sys.stdin); print('✓ Success!' if 'current_week' in data else '✗ Error: ' + str(data.get('error')))"
    ```
  - **ALWAYS verify .env is in .gitignore before reading it**: `cat .gitignore | grep "\.env"`
  - After deployment, authenticate with the API and test all endpoints to confirm no 500 errors

---

## Date Serialization Issues (Nov 24-25, 2025)

### Problem
PostgreSQL DATE columns were being serialized as HTTP date format strings ("Wed, 31 May 2023 00:00:00 GMT") instead of ISO format, causing incorrect chronological sorting in the frontend.

### Root Cause
- `psycopg2` with `RealDictCursor` automatically converts Python date objects to strings
- Flask's middleware applies additional formatting, converting to HTTP date format
- JavaScript's string sorting treats "Wed, 31 Jul 2022" as coming AFTER "Mon, 25 Nov 2025" alphabetically

### Solution
```python
# Force PostgreSQL to return strings, bypassing psycopg2 date parsing
cur.execute("""
    SELECT TO_CHAR(date, 'YYYY-MM-DD')::TEXT as date
    FROM social_sentiment_metrics
""")

# Custom JSON encoder for remaining date objects and Decimal types
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Bypass Flask's jsonify() to use custom encoder
response_data = {'data': [dict(row) for row in rows]}
return Response(
    json.dumps(response_data, cls=DateTimeEncoder),
    mimetype='application/json'
)
```

### Key Takeaways
- Always cast PostgreSQL dates to TEXT when you need exact string format: `TO_CHAR(date, 'YYYY-MM-DD')::TEXT`
- Flask 3.0+ deprecated `app.json_encoder`; use `Response(json.dumps(...))` instead
- Don't forget to handle `Decimal` types in custom JSON encoders
- Docker build cache can prevent deployments; use `--no-cache` when in doubt

---

## Query Parameter Cache-Busting Bug (Nov 25, 2025)

### Problem
Frontend showed only 100 tweets despite backend having 3,941 tweets in database. The `historic=1` query parameter was being ignored.

### Root Cause
Cache-busting logic appended `?t=...` to ALL endpoints, creating malformed URLs:
```javascript
// WRONG - creates /api/social?historic=1?t=1732550000000
fetch(`${API_BASE_URL}${endpoint}?t=${Date.now()}`)
```

Backend saw invalid query string and defaulted to `historic=0`, which has `LIMIT 100`.

### Solution
```javascript
// Detect if endpoint already has query params and use appropriate separator
const separator = endpoint.includes('?') ? '&' : '?'
const response = await fetch(`${API_BASE_URL}${endpoint}${separator}t=${Date.now()}`, ...)
```

### Key Takeaways
- Always check for existing query parameters before appending new ones
- Test actual network requests, not just code logic
- When debugging "missing data" issues, verify the actual HTTP requests being made
- Browser DevTools Network tab is your friend

---

## Docker Image Tag Confusion (Nov 25, 2025)

### Problem
Updated Docker image wasn't deploying despite successful push to ECR. Container kept serving old JavaScript bundle.

### Root Cause
- `docker-compose.yml` used `:frontend-latest` tag
- Initial pushes used `:frontend` tag
- Container kept using old `:frontend-latest` image from cache

### Solution
1. Always verify what tag `docker-compose.yml` expects
2. Tag the new image with the EXACT tag name from docker-compose:
```bash
docker tag ummatics-frontend:latest 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:frontend-latest
```
3. Remove old images to force pull:
```bash
docker rmi <old-image-id>
docker compose down frontend
docker compose up -d frontend
```

### Key Takeaways
- Check `docker-compose.yml` for exact image tags before deploying
- Docker won't re-pull if an image with the same tag exists locally
- Use `docker exec <container> ls /path` to verify container contents
- Vite generates different bundle hashes for different builds; use this to verify deployment

---

## Frontend Data Flow Debugging

### Effective Techniques Used

1. **API Testing**
```bash
# Verify API returns expected data
curl -s -H "Authorization: Bearer <token>" "http://host/api/endpoint" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Count: {len(data.get(\"key\", []))}')
"
```

2. **Bundle Inspection**
```bash
# Check if specific code is in deployed bundle
curl -s http://host/assets/index-<hash>.js | grep -o 'pattern'
```

3. **Container File Verification**
```bash
# Verify files inside running container
docker exec <container> ls -la /usr/share/nginx/html/assets/
docker exec <container> cat /usr/share/nginx/html/index.html
```

4. **Simulated Browser Requests**
```python
# Test what frontend actually receives
session = requests.Session()
auth = session.post('http://host/api/auth', json={'password': 'xxx'})
token = auth.json()['token']
response = session.get('http://host/api/endpoint', headers={'Authorization': f'Bearer {token}'})
print(len(response.json()['data']))
```

### Key Takeaways
- Don't assume the frontend receives what the API returns; test the full flow
- Browser cache is sneaky; always verify with curl/network tab
- Minified code can still be searched for patterns
- When debugging, work backwards from the symptom to the source

---

## Database Query Optimization

### Historic vs Real-time Data Pattern
```python
historic = request.args.get('historic', '0') in ('1', 'true', 'True')

if historic:
    # No LIMIT - return ALL data
    cur.execute("SELECT * FROM table ORDER BY date DESC")
else:
    # Limited recent data for performance
    cur.execute("SELECT * FROM table WHERE date >= %s ORDER BY date DESC LIMIT 100", 
                (cutoff_date,))
```

### Key Takeaways
- Provide both full historical and recent-only endpoints
- Use query parameters to control data volume
- Always have reasonable LIMIT defaults for unbounded queries
- Document the difference between endpoints clearly

---

## General Debugging Principles

1. **Trust but Verify**
   - Code looks correct ≠ deployment is correct
   - API returns data ≠ frontend receives it
   - Build succeeded ≠ container is updated

2. **Check the Full Pipeline**
   - Source code → Build → Docker image → ECR → Container → Browser cache
   - Each step can fail silently

3. **Use Timestamps and Hashes**
   - Vite bundle hashes change with content
   - Use these to verify deployment success
   - Add cache busters to development requests

4. **Test at Each Layer**
   - Database query results
   - API HTTP responses
   - Frontend network requests
   - Rendered DOM content

5. **When Stuck, Start Fresh**
   - Clear browser cache (Ctrl+Shift+R)
   - Remove Docker images and rebuild
   - Check logs at each layer
   - Verify assumptions with curl/direct tests

---

## Backend Code Deployment Pitfall (Nov 25, 2025)

### Problem
Made backend code changes locally, built Docker image, pushed to ECR, but the changes didn't take effect on EC2. Falsely reported the fix was deployed when it wasn't.

### Root Cause
The `docker-compose.yml` on EC2 uses `build: ./backend` instead of pulling from ECR. When I ran:
```bash
docker compose build --no-cache api  # Built using LOCAL code on EC2
docker compose up -d api
```

This rebuilt the container using the **old code still on the EC2 instance** (before `git pull`), not the updated code I had pushed to GitHub.

### What I Missed
1. **Forgot to sync code to EC2 first**: Made changes locally, committed to git, but EC2 still had old code
2. **Docker Compose Build Behavior**: `docker compose build` uses the local filesystem, NOT ECR images
3. **Premature Success Declaration**: Pushed to ECR but that image was never used
4. **Failed to Verify**: Didn't check if the actual code changes were present in the running container

### Correct Deployment Process for Backend Changes

**CRITICAL: NO GIT OPERATIONS ON EC2 - Credentials must stay local**

**Method 1: Copy Files via SSH (Recommended for Quick Fixes)**
```bash
# Copy changed backend files from local to EC2
scp -i ~/.ssh/ummatics-monitor-key.pem backend/api.py ubuntu@3.226.110.16:/home/ubuntu/ummatics-impact-monitor/backend/
scp -i ~/.ssh/ummatics-monitor-key.pem backend/ingestion.py ubuntu@3.226.110.16:/home/ubuntu/ummatics-impact-monitor/backend/

# Rebuild and restart container on EC2
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'cd /home/ubuntu/ummatics-impact-monitor && docker compose build --no-cache api && docker compose up -d api'
```

**Method 2: Use ECR for Backend (Recommended for Production)**
```bash
# Build backend locally
cd /home/tahir/ummatics-impact-monitor
docker build -t ummatics-backend:latest -f backend/Dockerfile backend/

# Tag and push to ECR
docker tag ummatics-backend:latest 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 182758038500.dkr.ecr.us-east-1.amazonaws.com
docker push 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest

# Pull and restart on EC2
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'cd /home/ubuntu/ummatics-impact-monitor && docker compose pull api && docker compose up -d api'
```

**Verification**
```bash
# Verify container is running with new code
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'docker compose ps api'

# Test the API endpoint to confirm behavior changed
curl -s -H "Authorization: Bearer token" "http://3.226.110.16:5000/api/endpoint" | python3 -c "verification script"
```

### Key Takeaways
- **NEVER use git on EC2**: No git pull, git clone, git commit, or git push - keep credentials local
- **Two deployment methods**: Copy files via SCP, OR build locally + push to ECR
- **Frontend always uses ECR**: Build locally → Push to ECR → Pull on EC2
- **Backend can use either**: SCP for quick fixes, ECR for production deployments
- **Always verify**: Test API endpoints after deployment to confirm changes took effect
- **Check container contents**: Use `docker exec` or SSH to verify files if unsure

---

## User Guidelines

### Frontend Deployment
1. Build frontend locally with `npm run build`
2. Build Docker image locally
3. Tag and push to ECR
4. Pull from ECR on EC2 and restart container
5. Always verify deployment by checking the website URL

### Backend Deployment  
1. **Method 1 (SCP)**: Copy changed files via SCP, rebuild container on EC2
2. **Method 2 (ECR)**: Build Docker image locally, push to ECR, pull on EC2
3. Rebuild with `--no-cache` flag to ensure fresh build
4. **ALWAYS VERIFY**: Test API endpoints to confirm changes took effect
5. Never use git operations on EC2 - keep credentials local

### Security and Resource Guidelines
1. **NEVER run ANY git operations on EC2**: Your credentials should NOT be stored on EC2
   - No git pull, git clone, git commit, git push, or git checkout
   - EC2 should only receive code via SCP or Docker images from ECR
   - Keep ALL git credentials on your local development machine only
   - Use SSH/SCP for file transfer, ECR for container images
2. **NEVER run ingestion.py locally**: Data ingestion consumes rate-limited API resources
   - Twitter API, Reddit API, etc. have daily/hourly limits
   - Running locally wastes quota and may exhaust limits needed for production
   - Always run ingestion from the scheduled production environment (EC2)
   - Exception: Testing with small dataset or mock data is acceptable

---

## Chart Data Gaps for Unavailable Historical Data (Nov 25, 2025)

### Problem
Follower counts and engagement rates before November 2025 are not real historical data - they are backfilled using current values. Displaying them on charts is misleading, but we still want to show the full historical range for mentions data.

### Challenge
How to hide follower/engagement data before Nov 2025 while maintaining the full date range on charts (2009-2025)?

### Solution
Set unavailable data to `null` instead of `0`, and configure chart library to NOT connect across null values:

```javascript
// In data processing - check if before Nov 2025
const isBeforeNov2025 = date < new Date('2025-11-01')

// Set to null instead of 0
monthlyData[monthKey] = {
  follower_count: isBeforeNov2025 ? null : metric.follower_count,
  engagement_rate: isBeforeNov2025 ? null : 0,
  mentions_count: 0  // Always include mentions
}

// In Recharts configuration - prevent connecting across gaps
<Line dataKey="follower_count" connectNulls={false} />
<Line dataKey="engagement_rate" connectNulls={false} />
```

### Result
- X-axis shows full date range (2009 to present)
- Follower count line only appears from Nov 2025 onwards (gap before)
- Engagement rate line only appears from Nov 2025 onwards (gap before)
- Mentions line shows continuously for all historical data
- No misleading "fake" historical follower/engagement data

### Key Takeaways
- **Use `null` for unavailable data, not `0`**: `0` is a valid data point, `null` means "no data"
- **Chart library behavior**: Most libraries (Recharts, Chart.js) treat `null` as gaps when `connectNulls={false}`
- **Maintain full range**: X-axis range is determined by data array length, not by presence of Y values
- **Data integrity**: Only show data you actually have; don't extrapolate or backfill misleadingly

---

## Reddit Data Quality Issues (Nov 25, 2025)

### Problem 1: Followers Shown for Reddit (Not Relevant)
Reddit doesn't have a "follower count" concept like Twitter. The database had follower_count set to 0 for Reddit, but the frontend was still displaying the "Followers" card and follower line in charts.

### Solution
- Removed follower count card display from Reddit tab
- Removed follower count and engagement rate lines from Reddit metrics chart
- Reddit tab now only shows mentions count (the relevant metric)

### Problem 2: Sentiment Datapoints with Zero Values
Charts showed sentiment data for dates with no actual sentiment scores (average_sentiment_score = 0), creating misleading baseline at zero.

### Root Cause
Backend creates sentiment metric rows even when there are no tweets for that day, resulting in 0 values. Frontend was not filtering these out.

### Solution
Filter out zero sentiment values when displaying charts:
```javascript
.filter(s => s._date && (s.avg_sentiment !== undefined && s.avg_sentiment !== null) && s.avg_sentiment !== 0)
```

### Problem 3: HTML Tags Showing in Reddit Content
Reddit RSS feeds contain HTML-encoded entities (`&lt;`, `&gt;`, `&amp;`) and HTML tags (`<a>`, `<p>`, etc.) that were being stored and displayed as raw text.

### Root Cause
Reddit RSS feed content includes HTML formatting that wasn't being decoded or stripped before storage.

### Solution
Backend (ingestion.py):
```python
import html

# Decode HTML entities like &lt; &gt; &amp;
decoded_summary = html.unescape(full_summary)
# Remove HTML tags
clean_summary = re.sub(r'<[^>]+>', '', decoded_summary)
content = clean_summary[:1000]
```

Frontend (App.jsx) - fallback for existing data:
```javascript
<p dangerouslySetInnerHTML={{ 
  __html: mention.content
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&').replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'").replace(/<[^>]+>/g, '') 
}}></p>
```

### Key Takeaways
- **Platform-specific metrics**: Don't show metrics that don't apply to a platform (Reddit has no followers)
- **Filter zero vs null**: `0` can be a real value OR placeholder; context matters
- **RSS feeds often contain HTML**: Always decode entities and strip tags from RSS content
- **Clean data at ingestion**: Better to clean data when storing than when displaying
- **Dual cleanup approach**: Clean at ingestion for new data, handle legacy data in frontend

### Problem 4: Reddit Showing Twitter Sentiment Data
Reddit sentiment chart was showing incorrect or zero sentiment values because the API was returning ALL platforms' sentiment data, and Reddit was using metrics from Twitter or empty placeholder rows.

### Root Cause
- `/api/sentiment` endpoint returned sentiment data for ALL platforms without filtering
- Reddit tab received the same sentiment data as Twitter tab
- `categorized_mentions` only contained Twitter data, but `sentiment_metrics` included both platforms
- Reddit sentiment chart showed database rows with zero values (placeholder data)

### Solution
Backend (api.py):
```python
# Add platform parameter to sentiment endpoint
platform = request.args.get('platform', 'Twitter')

# Filter sentiment metrics by platform
cur.execute("""
    SELECT ... FROM social_sentiment_metrics
    WHERE platform = %s
    ORDER BY date DESC
""", (platform,))

# Filter categorized mentions by platform
cur.execute("""
    SELECT ... FROM social_mentions 
    WHERE platform = %s AND sentiment IS NOT NULL
    ORDER BY posted_at DESC LIMIT 50
""", (platform,))
```

Frontend (App.jsx):
```javascript
// Twitter tab requests Twitter sentiment
fetchData('/sentiment?platform=Twitter', setSentimentData)

// Reddit tab requests Reddit sentiment  
fetchData('/sentiment?platform=Reddit', setRedditSentimentData)
```

### Key Takeaways
- **Platform-specific API calls**: Each platform's tab should request its own filtered data
- **Don't share cross-platform data**: Twitter and Reddit have separate data streams
- **Filter at the source**: Backend should filter by platform, not frontend
- **Test with actual data**: Verify each platform shows only its own sentiment metrics
- **Database can have placeholder rows**: Empty sentiment rows created by scheduler need filtering

---

## Chart Data Granularity - Monthly vs Daily (Nov 26, 2025)

### Context
Initially used monthly aggregation to display Twitter metrics from 2009 to present. After filtering chart display to only show data from October 2025 onwards for relevance, the reduced time range made daily datapoints more appropriate than monthly aggregation.

### Decision Process
1. **Full history (2009-2025)**: Monthly aggregation was necessary
   - 16+ years of data = ~190 months
   - Daily would be ~5,800+ datapoints (too cluttered)
   - Monthly provided cleaner visualization

2. **Recent data only (Oct 2025+)**: Daily datapoints became better
   - ~2 months of data = ~60 days
   - Daily provides more granular insights
   - No need for aggregation with smaller dataset

### Implementation
Before (monthly aggregation):
```javascript
// Aggregate metrics by month
const monthlyData = {}
twitterMetrics.forEach(metric => {
  const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
  if (!monthlyData[monthKey]) {
    monthlyData[monthKey] = { month: monthKey, mentions_count: 0, count: 0 }
  }
  monthlyData[monthKey].mentions_count += metric.mentions_count || 0
  monthlyData[monthKey].count += 1
})
```

After (daily datapoints with filtering):
```javascript
// Use daily data, filtered to Oct 2025+
const dailyMetrics = twitterMetrics
  .map(metricRaw => ({
    ...metricRaw,
    _date: metricRaw.date || metricRaw.week_start_date || metricRaw.week_start
  }))
  .filter(metric => new Date(metric._date) >= new Date('2025-10-01'))
  .map(metric => ({
    date: metric._date,
    follower_count: metric.follower_count,
    mentions_count: metric.mentions_count || 0,
    engagement_rate: metric.engagement_rate || 0
  }))
  .sort((a, b) => new Date(a.date) - new Date(b.date))
```

Chart display updated:
```javascript
// Before: Monthly labels
<XAxis dataKey="month" tickFormatter={(month) => ...} />

// After: Daily labels
<XAxis dataKey="date" tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} />
```

### Key Takeaways
- **Match granularity to time range**: Use daily for short periods (weeks/months), monthly for long periods (years)
- **Filter before display, not data**: Keep full historical data in database, filter only for visualization
- **Table vs Chart**: Table can show all entries; charts should show relevant timeframe
- **When filtering reduces scope significantly**: Reconsider aggregation level - you may not need it anymore
- **UX improvement**: Don't clutter charts with irrelevant old data; show what's actionable
- **Data completeness**: ~2 months is small enough for daily granularity without overwhelming the chart

---

## Discovering New Subreddits via Google Search (Dec 7, 2025)

### Problem
Finding relevant subreddits or Reddit posts for monitoring Ummatics-related content can be challenging, especially when relying solely on Reddit's search RSS.

### Solution
Use Google search to complement Reddit's search capabilities. Google often indexes Reddit posts and subreddits more comprehensively than Reddit's own search engine.

#### Implementation
Created `google_search_subreddits()` function in `backend/ingestion.py`:
- Uses `requests` and `BeautifulSoup` to parse Google search results
- Searches for `site:reddit.com "ummatics" OR "ummatic"`
- Extracts subreddit names from Reddit URLs using regex
- Stores discovered subreddits in `discovered_subreddits` table
- Prevents duplicates by checking against existing database entries and monitored subreddits
- Scheduled to run weekly (Sundays at 10:00 AM) via `scheduler.py`

#### Example Google Search Queries
- `site:reddit.com "ummatics"`
- `site:reddit.com/r/ "ummatic"`
- `site:reddit.com "ummatics" OR "ummatic"`
- `site:reddit.com "ummatics" after:2025-01-01`

### Key Takeaways
- Google search can be a powerful tool for discovering new subreddits and posts
- Use advanced search operators like `site:` and `after:` to refine results
- Weekly automated discovery helps maintain comprehensive monitoring coverage
- BeautifulSoup dependency added to `requirements.txt` for HTML parsing

---

## Overview Page Enhancement (Dec 7, 2025)

### Problem
The overview page was empty with only basic metrics (news mentions, social mentions, citations) and a trends chart. Users needed more actionable insights at a glance.

### Solution
Enhanced the overview page with 5 new data-rich sections:

1. **Platform Breakdown** - Pie chart showing distribution of mentions across Twitter, Reddit, etc. for the current week
2. **Sentiment Summary** - Visual breakdown of positive/neutral/negative sentiment percentages by platform with progress bars
3. **Recent Mentions** - Last 10 social mentions with text preview, author, date, and engagement scores
4. **Trending Keywords** - Top 15 most frequently used words from current week's mentions (filtered to words >4 characters)
5. **Recently Discovered Subreddits** - Grid showing latest 10 subreddits discovered via automated monitoring

### Implementation
**Backend (`/api/overview`):**
- Added 5 new SQL queries to fetch enriched data
- Used PostgreSQL's `string_to_array` and `unnest` for keyword extraction
- Filtered trending keywords by length to avoid common stop words
- Added sentiment percentage calculations using `AVG(CASE WHEN...)` pattern

**Frontend (`OverviewTab` component):**
- Added responsive grid layouts with `grid-cols-1 lg:grid-cols-2`
- Implemented PieChart for platform breakdown using Recharts
- Created custom sentiment progress bars with color coding (green/gray/red)
- Added scrollable mention feed with text truncation
- Styled trending keywords as pill badges with frequency counts
- Created subreddit grid cards with discovery dates

### Key Takeaways
- Overview pages should provide actionable insights, not just metrics
- Combining multiple data visualizations (pie charts, progress bars, lists) creates engaging dashboards
- Always include fallback UI for empty states (`No data available` messages)
- Limit trending keywords by character length to filter noise
- Grid layouts work well for responsive design across device sizes
- **CRITICAL: Always verify column names match the actual database schema before deploying**
- Use Chrome DevTools Network tab to diagnose 500 errors, then check backend logs immediately
- Common SQL errors: wrong column names (`date` vs `posted_at`, `text` vs `content`, `url` vs `post_url`)

---

## Local Container Usage Policy (Dec 7, 2025)

### Policy
**DO NOT start local Docker containers unless explicitly requested by the user.**

### Rationale
- All production deployments run on AWS EC2
- Local containers are only for development/testing when specifically needed
- Prevents accidental local resource consumption
- Ensures consistency by testing/deploying only to AWS environment

### Key Takeaways
- Always deploy and test on AWS, not locally
- Local containers should only be used when user explicitly requests local development
- This prevents confusion between local and production environments

---

## AWS EC2 Deployment Policy (Dec 7, 2025)

### Policy
**NEVER use `git pull` on AWS EC2 instances. Always deploy via Docker images pushed to ECR.**

### Rationale
- Direct git pulls on EC2 bypass the Docker build process
- Can lead to inconsistent environments (missing dependencies, wrong Python versions, etc.)
- Doesn't leverage Docker caching or image versioning
- Makes rollbacks difficult
- Can cause permission issues with git credentials on EC2

### Correct Deployment Process
1. Make changes locally
2. Commit and push to GitHub (for version control)
3. Build Docker images locally: `docker build -t ummatics-backend:latest ./backend`
4. Tag images with ECR repository URLs
5. Push images to AWS ECR
6. Copy updated `docker-compose.yml` to EC2 via `scp`
7. SSH to EC2 and restart: `docker-compose down && docker-compose up -d`

### Critical Docker Compose Configuration
**NEVER mount source code directories as volumes in production:**
```yaml
# WRONG - overwrites image code with local files
volumes:
  - ./backend:/app
  
# CORRECT - only mount credentials, use code from image
volumes:
  - ./credentials:/app/credentials
```

### Key Takeaways
- EC2 should pull images from ECR, never clone/pull from GitHub
- Remove `./backend:/app` volume mounts in production docker-compose.yml
- Volume mounts override the Docker image contents with local files
- Always use ECR images for deployments to ensure consistency
- Git operations should only happen on local development machines

### Deployment Commands Reference
```bash
# Local: Build and push
docker build -t ummatics-backend:latest ./backend
docker tag ummatics-backend:latest 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 182758038500.dkr.ecr.us-east-1.amazonaws.com
docker push 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest

# Copy docker-compose.yml to EC2
scp -i ~/.ssh/ummatics-monitor-key.pem docker-compose.yml ubuntu@3.226.110.16:/home/ubuntu/ummatics-impact-monitor/

# EC2: Authenticate and deploy
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 182758038500.dkr.ecr.us-east-1.amazonaws.com
cd /home/ubuntu/ummatics-impact-monitor
docker-compose down && docker-compose up -d
```