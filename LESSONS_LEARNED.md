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

## Twitter Retweet Handling (Dec 14, 2025)

### Problem: Duplicate Retweet Entries

**Issue**: Dashboard was showing individual retweet entries, creating clutter and inflating mention counts.

Example from dashboard:
```
@diurnalul - RT @islamicize: "And that is how capitalism operates..."
@hamannJacobi - RT @islamicize: "And that is how capitalism operates..."
@Sadik21804847 - RT @islamicize: "And that is how capitalism operates..."
@fifty_almost - RT @islamicize: "And that is how capitalism operates..."
```

**Root Cause**:
- Twitter API and Apify scraper return both original tweets AND retweets
- Each retweet was being saved as a separate social_mentions record
- Original post already includes `retweet_count` metric showing total retweets
- Displaying individual retweets provides no additional value and clutters the UI

**Solution**: Filter Out Retweets During Ingestion

```python
# In ingestion.py - ingest_twitter()
content = tweet.get('text', '')

# Skip retweets - original posts already show retweet counts
if content.startswith('RT @'):
    logger.debug(f"Skipping retweet: {tweet_id}")
    continue
```

**Why This Works**:
- Twitter retweets always start with "RT @username:"
- Simple string prefix check identifies all retweets
- Original posts contain the actual content and include `retweet_count`
- Dashboard shows engagement metrics (likes, retweets, replies) from original post
- Eliminates duplicate entries while preserving retweet counts in metrics

**Benefits**:
- ✅ Cleaner dashboard - only shows original content
- ✅ Accurate mention counts (not inflated by retweets)
- ✅ Preserves retweet engagement data on original posts
- ✅ Easier to identify unique discussions and content
- ✅ Reduces database storage (fewer duplicate text entries)

**Trade-offs**:
- ❌ Can't see WHO retweeted (only count)
- ❌ Can't analyze which users are retweeting
- ✅ Original post engagement metrics already capture retweet value
- ✅ User rarely needs to see individual retweet actions

**Alternative Approaches Considered**:
1. **Filter in API query** - Not possible, Twitter API returns retweets by default
2. **Hide in frontend** - Still clutters database, wastes storage
3. **Separate retweet table** - Overengineering for minimal value
4. **Flag as retweet** - Still shows in UI, adds complexity

**Recommendation**: Current solution (filter during ingestion) is optimal.

---

## Twitter API Quota Management (Dec 14, 2025)

### Problem: Free Tier Quota Exhausted in 2 Days

**Issue**: Twitter Developer console showed 102/100 posts accessed in just 2 days of the billing period (Dec 13-Jan 13, 2025). At this rate, would use ~1,530 API calls/month instead of the 100 allowed on free tier.

**Investigation**:
- Database showed 67 tweets stored in current billing period
- Logs showed: 45 tweets ingested Dec 13 + 7 tweets Dec 14 = 52 total
- Discrepancy: API counted 102 calls, but only 67 in database
- Root cause: ~35 calls returned retweets that were filtered out AFTER API call

**Two Problems Identified**:

1. **Retweets counted against quota before filtering**
   - Twitter API returns both original tweets AND retweets in search results
   - Retweet filter in ingestion.py (`if content.startswith('RT @'): continue`) runs AFTER API call
   - Each retweet counts against quota even though it's discarded
   - ~35% of API calls wasted on retweets

2. **Hourly ingestion too frequent**
   - Scheduler ran ingestion every hour (24x/day)
   - 24 runs/day × 30 days = 720 potential API calls/month
   - Even with perfect filtering, still 7x over quota

**Solution: Two-Part Optimization**

**Part 1: Exclude Retweets at API Level**
```python
# In ingestion.py - Twitter search queries
search_queries = [
    '"ummatics" -is:retweet -from:ummatics',
    '"ummatic" -is:retweet -from:ummatics'
]
```

Adding `-is:retweet` to the Twitter API query prevents retweets from being returned, so they don't count against quota.

**Part 2: Reduce Ingestion Frequency**
```python
# In scheduler.py - Changed from hourly to 3x daily
scheduler.add_job(
    scheduled_ingestion,
    trigger=CronTrigger(hour='8,14,20', minute=0),  # 8 AM, 2 PM, 8 PM UTC
    id='three_daily_ingestion',
    name='3x Daily Data Ingestion',
    replace_existing=True
)
```

**Impact**:
- Before: ~1,530 API calls/month (hourly + retweets)
- After: ~90 API calls/month (3x daily, no retweets)
- **93% reduction** in API usage
- Safely under 100/month free tier limit
- Still provides fresh data 3x per day

**Sentiment Job Updated**:
```python
# Run sentiment update after each ingestion
scheduler.add_job(
    scheduled_sentiment,
    trigger=CronTrigger(hour='8,14,20', minute=30),  # 30 minutes after ingestion
    id='three_daily_sentiment',
    name='3x Daily Sentiment Update',
    replace_existing=True
)
```

**Key Learnings**:
- ✅ Filter at API level when possible (saves quota)
- ✅ Only filter client-side when API doesn't support it
- ✅ Calculate actual API usage before deploying (don't guess)
- ✅ Monitor developer console during billing period
- ✅ 3x daily is sufficient for social media monitoring (not real-time)
- ✅ Align dependent jobs (sentiment) with ingestion schedule

**Alternative Approaches Considered**:
1. **Paid tier ($100/month)** - Too expensive for this project
2. **Use Twitter's streaming API** - Requires enterprise tier
3. **Reduce to daily** - Less fresh data, but would work (30 calls/month)
4. **Use since_id parameter** - Doesn't reduce API calls, just payload size

**Recommendation**: 3x daily with `-is:retweet` filter is optimal balance of cost and freshness.

---

## Database Backup and Restore (Dec 14, 2025)

### S3 Backup Infrastructure

**Automated weekly backups to AWS S3 using free tier (5GB storage)**

**S3 Configuration:**
- **Bucket**: `ummatics-db-backups` (us-east-1)
- **Versioning**: Enabled (keeps multiple backup versions)
- **Lifecycle Policy**: Delete old versions after 90 days
- **Current Size**: ~0.49 MB compressed (PostgreSQL dump)

**Scripts Created:**
1. **backup_db_to_s3.py** - Python backup script using boto3
   - Creates compressed `pg_dump` from Docker container
   - Uploads to S3 with metadata (database name, timestamp)
   - Creates S3 bucket if needed, enables versioning
   - Cleans up old local backups (keeps 3 most recent)
   - Logs: `/var/log/ummatics_backups/backup_*.log`

2. **restore_db_from_s3.py** - Python restore script
   - Downloads latest (or specified) backup from S3
   - Creates new database (e.g., `ummatics_monitor_restored`)
   - Restores from compressed backup
   - Verifies table counts and row counts
   - Supports `--force` flag to skip confirmation

3. **setup_backup_cron.sh** - Cron job installer
   - Installs weekly backup: Every Sunday at 2 AM UTC
   - Creates wrapper script with logging
   - Crontab entry: `0 2 * * 0 /home/ubuntu/ummatics-impact-monitor/backup_cron_wrapper.sh`

**IAM Permissions Required:**
- EC2 instance role: `ummatics-ssm-role`
- Policy: `S3BackupPolicy` (attached)
  - `s3:ListBucket`, `s3:GetBucketLocation`, `s3:ListBucketVersions`
  - `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`
  - `s3:CreateBucket`, `s3:PutBucketVersioning`, `s3:PutLifecycleConfiguration`

### AWS CLI vs boto3 Solution

**CRITICAL: AWS CLI is broken on this EC2 instance**

**Issue**: AWS CLI has a bug with opsworkscm module:
```bash
$ aws s3 ls
KeyError: 'opsworkscm'
# AWS CLI version issue, causes all aws commands to fail
```

**Solution**: Use boto3 (Python AWS SDK) instead
- ✅ Works with EC2 IAM role credentials
- ✅ No AWS CLI dependency
- ✅ More control over S3 operations
- ✅ Better error handling

**Why boto3 works where AWS CLI fails:**
- Both use the same underlying AWS SDK
- boto3 bypasses the broken CLI layer
- IAM role credentials work seamlessly with boto3
- More reliable for scripting in Python environment

### Common Issues and Troubleshooting

**1. S3 Access Denied**
```python
# Error: AccessDenied when calling ListBuckets
# Solution: Don't call ListBuckets - use head_bucket instead
s3_client.head_bucket(Bucket=bucket_name)  # Only needs bucket-specific permission
```

**2. Lifecycle Policy Validation Error**
```python
# Error: Unknown parameter in LifecycleConfiguration: "Id"
# Solution: Use "ID" (uppercase) not "Id"
'Rules': [{'ID': 'delete-old-versions', ...}]  # Correct

# Error: Missing required key: 'Filter'
# Solution: Add empty Filter even if not filtering
'Filter': {'Prefix': ''}  # Required parameter
```

**3. Database Restore Confirmation**
```bash
# To restore without confirmation prompt
python3 restore_db_from_s3.py --force

# To restore specific backup
python3 restore_db_from_s3.py --backup ummatics_db_backup_20251214_184305.sql.gz
```

### Backup Validation Results

**Production Database (ummatics_monitor):**
- Tables: 12
- Social mentions: 4015 (4011 Twitter, 4 Reddit)
- News mentions: 9
- Date range: 2025-11-13 to 2025-12-14
- Sentiment coverage: 100% (1258 positive, 2523 neutral, 234 negative)
- Sentiment metrics: 1491 daily entries (2009-03-03 to 2025-12-14)

**Restored Database (ummatics_monitor_restored):**
- ✅ All 12 tables restored
- ✅ All 4015 social mentions restored
- ✅ All 9 news mentions restored
- ✅ Date ranges match exactly
- ✅ Platform breakdown matches (4011 Twitter, 4 Reddit)
- ✅ No data loss or corruption detected

**First Backup:**
- File: `ummatics_db_backup_20251214_184305.sql.gz`
- Size: 0.49 MB compressed
- S3 location: `s3://ummatics-db-backups/`
- Status: ✅ Successfully validated via restore test

### Weekly Backup Schedule

**Cron Job Details:**
- Schedule: Every Sunday at 2:00 AM UTC
- Crontab entry: `0 2 * * 0 /home/ubuntu/ummatics-impact-monitor/backup_cron_wrapper.sh`
- User: ubuntu
- Logs: `/var/log/ummatics_backups/backup_YYYYMMDD_HHMMSS.log`

**Manual Operations:**
```bash
# View cron schedule
crontab -l

# Run backup manually
python3 /home/ubuntu/ummatics-impact-monitor/backup_db_to_s3.py

# Restore latest backup to test database
python3 /home/ubuntu/ummatics-impact-monitor/restore_db_from_s3.py --force

# View backup logs
ls -lh /var/log/ummatics_backups/
tail -f /var/log/ummatics_backups/backup_*.log

# List S3 backups
aws s3 ls s3://ummatics-db-backups/  # Won't work - AWS CLI broken
# Use this instead:
python3 -c "import boto3; s3=boto3.client('s3'); [print(obj['Key']) for obj in s3.list_objects_v2(Bucket='ummatics-db-backups')['Contents']]"
```

### Cost and Free Tier Usage

**AWS S3 Free Tier:**
- Storage: 5 GB per month (first 12 months)
- PUT requests: 2,000 per month
- GET requests: 20,000 per month

**Current Usage:**
- Storage: ~0.49 MB per backup × ~52 weeks = ~25 MB per year
- PUT requests: 1 backup per week = 52 per year
- GET requests: Minimal (restore operations only)
- **Well within free tier limits** ✅

**Future Scaling:**
- Database could grow 100× (to ~50 MB) and still fit in 5 GB free tier
- Versioning: 90-day retention means max ~13 versions per file
- Total storage even with growth: < 1 GB (20% of free tier)

---

## Reddit Discovery: Why We Can't Use Google (Dec 8, 2025)

### Problem
Reddit RSS feeds (`/search.rss?q=ummatics`) miss posts where keywords appear only in **comments**, not in post titles or content.

**Example**: https://www.reddit.com/r/Muslim/comments/1nvwzmq/islamic_newsletter/
- Post title: "Islamic Newsletter" (no "ummatics")
- Post content: Newsletter recommendation request (no "ummatics")
- Comment by Mixedblazer: "Muslim Matters, 5Pillars, Yaqeeen institute, **Ummatics**, are good"
- **Manual Google search finds it**: `site:reddit.com "ummatics"` shows this in results
- **Reddit RSS missed it**: RSS only indexes post titles and self-text

### Why We Can't Automate Google Search

**Attempted Solutions That Failed:**

1. **Web Scraping** (`requests` + BeautifulSoup):
   ```python
   response = requests.get("https://www.google.com/search?q=...")
   # Result: CAPTCHA page, JavaScript required, no actual results
   ```
   - ❌ Google detects bot User-Agent
   - ❌ Returns empty/blocked page
   - ❌ Against Google TOS

2. **Headless Browser** (Puppeteer/Playwright):
   ```javascript
   await page.goto("https://www.google.com/search?q=...")
   // Result: Blocked page, "unusual traffic" message
   ```
   - ❌ Google detects automation patterns
   - ❌ Returns 6KB blocked page instead of results
   - ❌ Page title shows URL instead of "Google Search"
   - ❌ `pageContent.includes('unusual traffic')` = true

3. **Google Custom Search API**:
   - ✅ Official API, would work reliably
   - ❌ Requires setup: API key + Custom Search Engine ID
   - ❌ Free tier: only 100 queries/day
   - ✅ See GOOGLE_CSE_SETUP.md for instructions

**Why Google Blocks Automation:**
- Sophisticated bot detection (analyzes browser fingerprints, mouse movements, timing)
- Even with headless browser + realistic User-Agent, still detects automation
- Designed to prevent scraping and protect search infrastructure

### Current Solution: Reddit RSS Only

**What we're using:**
- Reddit RSS feeds: `/r/subreddit/search.rss?q=ummatics`
- Discovers posts with keywords in **title or self-text only**
- Misses comment-level mentions
- No authentication needed, no rate limits

**What we're missing:**
- Posts where "ummatics" only appears in comments
- Example: The "Islamic Newsletter" post that prompted this investigation

### Alternative Approaches (Not Implemented)

1. **Reddit API** (official):
   - Requires OAuth authentication
   - Rate limit: 60 requests/minute
   - Can search comments with `/api/search`
   - **Complexity**: Token management, app approval, rate limiting

2. **Pushshift Reddit API** (archived data):
   - Comprehensive Reddit archive
   - Search comments directly
   - **Status**: Shut down in 2023, no longer available

3. **Manual Google Search** (current workaround):
   - User manually searches: `site:reddit.com "ummatics"`
   - Reviews results, notes any comment-only mentions
   - Periodic check (weekly/monthly)
   - **Time**: 5-10 minutes per check

### Decision: Google CSE is Actually Free and Easy!

**After investigation, Google CSE is the RECOMMENDED approach:**
- ✅ **FREE**: 100 queries/day, no credit card needed
- ✅ **Low usage**: You only use 10 queries/day (10% of free tier)
- ✅ **Quick setup**: 8 minutes total (5 min API key + 3 min CSE setup)
- ✅ **No maintenance**: Set it and forget it
- ✅ **Catches comment mentions**: Solves the original problem

**Cost breakdown:**
- Free tier: 100 queries per day
- Your usage: 10 queries per ingestion run (fetches 100 results via pagination)
- Daily runs: 1 time per day = 10 queries/day total
- **Headroom**: Could run 10x per day and still be free

**Why use it:**
- Finds posts like "Islamic Newsletter" where keywords only appear in comments
- Official API, reliable, no blocking
- Minimal setup time vs. significant benefit

### If You Want Google CSE (Recommended - Only 8 Minutes!)

See `GOOGLE_CSE_SETUP.md` for full instructions:
1. Get Google API key (5 min) - Cloud Console
2. Create Custom Search Engine (3 min) - reddit.com search
3. Add `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` to .env
4. Rebuild and deploy (normal deployment process)
5. Done! Uses only 10% of free tier daily

**Updated ingestion flow:**
```python
def run_full_ingestion():
    # Google CSE: Comment-level discovery (10 queries/day, free)
    google_search_reddit_posts()  
    
    # RSS: Real-time post discovery (unlimited, free)
    ingest_reddit()
```

**Alternative: Don't use Google CSE**
- ✅ System works fine with RSS-only
- ❌ Misses comment-only mentions (rare but exists)
- ✅ Zero setup required
- ❌ Manual periodic Google searches needed to catch outliers

**Updated ingestion flow** (with Google CSE):
```python
def run_full_ingestion():
    # Google CSE: Historical + comment-level discovery (if configured)
    google_search_reddit_posts()  
    
    # RSS: Real-time post title/content discovery
    ingest_reddit()
```

---

### Problem
Reddit RSS feeds (`/search.rss?q=ummatics`) miss posts where keywords appear only in **comments**, not in post titles or content.

**Example**: https://www.reddit.com/r/Muslim/comments/1nvwzmq/islamic_newsletter/
- Post title: "Islamic Newsletter" (no "ummatics")
- Post content: Newsletter recommendation request (no "ummatics")
- Comment by Mixedblazer: "Muslim Matters, 5Pillars, Yaqeeen institute, **Ummatics**, are good"
- **Google found it**: `site:reddit.com "ummatics"` returns this post in results
- **Reddit RSS missed it**: RSS only indexes post titles and self-text

### Root Cause
**Reddit RSS feeds only include post titles and self-text content - NOT comments.**

This is a platform limitation:
- RSS feeds: `/search.rss?q=ummatics` searches post-level content only
- Comments are not indexed in RSS feeds
- Reddit API would require OAuth authentication and has strict rate limits (60/min)
- Google indexes the entire page including all comments

### Solution: Dual Approach with Google Custom Search API
Implemented **both** RSS feeds and Google Custom Search API for comprehensive coverage:

1. **Reddit RSS feeds** (`ingest_reddit()`):
   - Fast, real-time, no authentication needed
   - Searches post titles and self-text only
   - Good for catching new posts quickly
   - Limitation: Misses comment-only mentions

2. **Google Custom Search API** (`google_search_reddit_posts()`):
   - **Official Google API** - reliable, no scraping/blocking issues
   - Comprehensive: Indexes entire pages including comments
   - Query: `site:reddit.com ("ummatics" OR "ummatic")`
   - Returns up to 100 results (10 per request, paginated)
   - For each URL, fetches Reddit's `.json` API to get full post data
   - Scans comments to verify keyword presence and location
   - Adds note: `[Note: Keyword found in comments, not post content]` when applicable
   - Marks source as 'Google Search' in database
   - Tracks where keyword was found: title, content, or comments

### Setup: Google Custom Search API

**Required Environment Variables:**
- `GOOGLE_API_KEY`: Get from https://console.cloud.google.com/apis/credentials
- `GOOGLE_CSE_ID`: Create Custom Search Engine at https://programmablesearchengine.google.com/

**Setup Steps:**
1. **Create API Key:**
   - Go to Google Cloud Console → APIs & Services → Credentials
   - Create API Key
   - Enable "Custom Search API" for your project
   - **Free tier**: 100 queries/day

2. **Create Custom Search Engine:**
   - Go to https://programmablesearchengine.google.com/
   - Click "Add" to create new search engine
   - Set "Sites to search": `reddit.com/*`
   - Get the "Search engine ID" (CSE_ID)

3. **Add to .env:**
   ```bash
   GOOGLE_API_KEY=your_api_key_here
   GOOGLE_CSE_ID=your_cse_id_here
   ```

**Cost:** Free tier = 100 queries/day (sufficient for daily ingestion runs)

### Implementation Details

**Google Custom Search Function** (backend/ingestion.py):
```python
def google_search_reddit_posts():
    """
    Find Reddit posts via Google Custom Search API.
    Catches posts with keywords in comments that RSS misses.
    """
    # 1. Check for API credentials (gracefully skips if not configured)
    # 2. Call Google CSE API: site:reddit.com ("ummatics" OR "ummatic")
    # 3. Paginate through results (up to 100 total)
    # 4. For each Reddit URL, fetch .json API
    # 5. Parse post title, selftext, and comments
    # 6. Verify keyword presence and track location (title/content/comments)
    # 7. Add note if found in comments only
    # 8. Insert with source='Google Search'
```

**Integration** (run_full_ingestion):
```python
# Use Google CSE to find Reddit posts (catches comment mentions)
google_search_reddit_posts()

# Use RSS for real-time post discovery
ingest_reddit()
```

**Graceful Degradation:**
- If `GOOGLE_API_KEY` or `GOOGLE_CSE_ID` not configured → logs warning and skips
- System continues working with RSS-only Reddit ingestion
- No errors or failures

### Why Google Custom Search API Instead of Scraping?
- **Scraping fails**: Google blocks automated requests with CAPTCHA/JS requirements
- **Official API**: Reliable, supported, no blocking
- **Free tier**: 100 queries/day sufficient for daily runs
- **Better data**: Returns clean URLs, no parsing issues
- **Compliant**: Follows Google's terms of service

### Why Not Use Reddit API?
- **OAuth required**: Complex authentication flow
- **Rate limits**: 60 requests per minute (too restrictive for batch processing)
- **App approval**: Requires Reddit developer account and app approval process
- **Maintenance overhead**: Access tokens expire, need refresh logic
- **Google CSE + RSS**: Covers both real-time and historical without Reddit credentials

### Benefits of Google CSE Approach
✅ No Reddit authentication required  
✅ Catches comment-only mentions that RSS misses  
✅ Comprehensive historical coverage  
✅ Uses Reddit's public JSON API (no rate limits for reads)  
✅ Deduplicates via `ON CONFLICT (post_url) DO NOTHING`  
✅ Tracks keyword location (title/content/comments)  
✅ Graceful degradation if API not configured  
✅ Free tier adequate for daily runs  

### Current Coverage
- **RSS Feeds**: Real-time post title/content monitoring (no API key needed)
- **Google Custom Search API**: Historical + comment-level discovery (requires API key)
- **Google Subreddit Discovery**: Weekly scan for new subreddits (web scraping, no API)
- **Combined**: Most comprehensive Reddit coverage possible

### Example Output
```
INFO: Google Custom Search for Reddit posts found 47 URLs
INFO: ✓ Ingested from Google (comments): r/Muslim - Islamic Newsletter...
INFO: ✓ Ingested from Google (title): r/islam - Looking for ummatic resources...
INFO: Google Reddit post ingestion complete. New posts: 12/47
```

---

## Citation Pagination and CSV Download (Dec 8, 2025)

### Problem
Citations page showed only first 20 results with no way to view all 199 citations or download data for analysis.

### Solution - Backend (backend/api.py)
1. **Pagination API**:
   - Added `page` and `limit` query parameters to `/api/citations` endpoint
   - Default: page=1, limit=20
   - Response includes pagination metadata:
     ```json
     {
       "pagination": {
         "page": 1,
         "limit": 20,
         "total": 199,
         "total_pages": 10
       },
       "top_works": [...]
     }
     ```
   - Uses SQL OFFSET/LIMIT: `OFFSET {(page - 1) * limit} LIMIT {limit}`

2. **CSV Download Endpoint** (`/api/citations/download`):
   - Returns all citations as downloadable CSV file
   - Uses Python `csv` and `io` modules:
     ```python
     import csv, io
     from flask import make_response
     
     output = io.StringIO()
     writer = csv.writer(output)
     writer.writerow(['Title', 'Authors', 'Publication Date', ...])
     # ... write all citations
     response = make_response(output.getvalue())
     response.headers['Content-Disposition'] = f'attachment; filename=citations_{timestamp}.csv'
     ```
   - No pagination - returns complete dataset

### Solution - Frontend (frontend/src/App.jsx)
1. **State Management**:
   - Added `citationPage` state variable (default: 1)
   - Updated fetch to include pagination params: `/api/citations?page=${citationPage}&limit=20`

2. **CitationsTab Props**:
   - Pass `token`, `page`, `onPageChange` to component
   - Component receives `data.pagination` with metadata

3. **Pagination UI Controls**:
   - Previous/Next buttons with disabled state at boundaries
   - Smart page number display (up to 7 pages centered on current)
   - Page indicator: "Page X of Y" and total count
   - Buttons use `onPageChange(pageNum)` callback

4. **Download Button**:
   - Green button at top-right of Citations tab
   - Fetches `/api/citations/download` with auth header
   - Creates blob URL, triggers download, cleans up:
     ```javascript
     const blob = await response.blob()
     const url = window.URL.createObjectURL(blob)
     const a = document.createElement('a')
     a.href = url
     a.download = `citations_${date}.csv`
     a.click()
     window.URL.revokeObjectURL(url)
     ```

### Current Status
- 199 total citations across 10 pages
- CSV download includes all 199 citations with columns: Title, Authors, Publication Date, Citations, DOI, Source URL, Citation Type, Last Updated
- Pagination tested and working as of Dec 8, 2025

---

## Reddit RSS Comment Search Limitation (Dec 8, 2025)

### Discovery
Investigating why this post wasn't found: https://www.reddit.com/r/Muslim/comments/1nvwzmq/
- Post title: "Islamic Newsletter"
- Post content: Newsletter recommendation request (no "ummatics" mentioned)
- Comment by user Mixedblazer: "Muslim Matters, 5Pillars, Yaqeeen institute, Ummatics, are good"

### Root Cause
**Reddit RSS feeds ONLY include post titles and self-text content - NOT comments.**

This is a platform limitation, not a bug in our implementation:
- RSS feeds: `/r/subreddit/search.rss?q=ummatics` only searches post titles/content
- Comments are not indexed in RSS feeds
- To search comments would require Reddit API authentication and rate limits

### Impact Assessment
- Missed mentions: Unknown quantity of "ummatics" mentions in Reddit comments
- Current discovery: Only posts with "ummatics" in title or self-text
- Subreddit discovery via Google: Still works (found 24 subreddits, 9 new on Dec 8)

### Decision
**Accepted limitation** - Reddit comment search not feasible with RSS approach:
- RSS feeds don't include comments (platform constraint)
- Reddit API requires OAuth, has strict rate limits
- Comment search would require different architecture (API-based ingestion)
- Current RSS approach is simple, reliable, requires no credentials

### Documentation
- Updated project docs to clarify Reddit ingestion scope: "post titles and content only"
- This limitation should be communicated if asked about Reddit coverage

---

## Citation Type Classification with Icons (Dec 7-8, 2025)

### Problem
Need to distinguish between citations that reference "ummatic" (word/concept usage) vs "ummatics.org" (the organization) in the academic citations display.

### Solution
Implemented a three-part system:

1. **Database**: Added `citation_type` VARCHAR(20) column with values: 'organization', 'word', 'unknown'

2. **Classification Logic** (backend/ingestion.py):
   - Checks title, abstract, and display_name for organization indicators:
     - 'ummatics.org', 'ummatics organization', 'ummatics institute', etc.
   - If "ummatics" appears without "ummatic", likely organization reference
   - Default classification: 'word'

3. **Frontend Icons** (frontend/src/App.jsx):
   - **Organization icon** (building/institution): For ummatics.org citations
   - **Word icon** (document/text): For ummatic concept usage
   - Legend at top of Citations tab explaining icon meanings
   - Icons displayed inline with citation titles

### Implementation Details
```javascript
// Frontend icon components
const OrganizationIcon = () => <svg>...</svg>  // Building icon
const WordIcon = () => <svg>...</svg>           // Document icon

const getCitationIcon = (citationType) => {
  if (citationType === 'organization') return <OrganizationIcon />
  if (citationType === 'word') return <WordIcon />
  return null
}
```

```python
# Backend classification
org_indicators = ['ummatics.org', 'ummatics organization', ...]
full_text = f"{title_lower} {abstract_lower} {display_name_lower}"
citation_type = 'organization' if any indicator found else 'word'
```

### Key Takeaways
- Visual distinction helps users quickly identify citation types
- Classification happens during ingestion, stored in database for fast queries
- Icons use SVG for scalability and consistent appearance
- Legend provides immediate context for new users
- Current distribution: ~194 word citations, 5 unknown (as of Dec 8, 2025)

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
- **CRITICAL: Use browser-like User-Agent header** - some sites return different status codes based on user agent
  - Example: https://jurnalfuf.uinsa.ac.id/... returns 403 with default user agent, 502 with browser user agent
  - Without browser user agent, cleanup might miss URLs that are actually dead for users
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

## Backend Code Deployment Pitfall (Nov 25-Dec 14, 2025)

### Problem (Nov 25)
Made backend code changes locally, built Docker image, pushed to ECR, but the changes didn't take effect on EC2. Falsely reported the fix was deployed when it wasn't.

### Root Cause (Nov 25)
The `docker-compose.yml` originally used `build: ./backend` instead of pulling from ECR. When I ran:
```bash
docker compose build --no-cache api  # Built using LOCAL code on EC2
docker compose up -d api
```

This rebuilt the container using the **old code still on the EC2 instance** (before `git pull`), not the updated code I had pushed to GitHub.

### Updated Problem (Dec 14, 2025) - CURRENT DEPLOYMENT METHOD

**CRITICAL DISCOVERY**: The `docker-compose.yml` was updated to use ECR images:
```yaml
api:
  image: 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest
scheduler:
  image: 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest
frontend:
  image: 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:frontend-latest
```

**This means:**
- ❌ `docker compose build` does NOTHING (no `build:` directive, only `image:`)
- ❌ `docker compose up -d --build` also does NOTHING (no local Dockerfile to build)
- ✅ `docker compose pull` pulls latest images from ECR
- ✅ Must push to ECR first, then pull on EC2

### Correct Deployment Process for Backend Changes (Dec 14, 2025)

**ONLY ONE METHOD WORKS: Build locally → Push to ECR → Pull on EC2**

```bash
# 1. Build backend image locally
cd /home/tahir/ummatics-impact-monitor
docker build -t ummatics-backend:latest -f backend/Dockerfile backend/

# 2. Tag and push to ECR
docker tag ummatics-backend:latest 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 182758038500.dkr.ecr.us-east-1.amazonaws.com
docker push 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest

# 3. Pull and restart on EC2
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'cd /home/ubuntu/ummatics-impact-monitor && docker compose pull api scheduler && docker compose up -d api scheduler'
```

**Frontend Deployment (Same Process)**
```bash
# 1. Build frontend locally
cd /home/tahir/ummatics-impact-monitor/frontend
npm run build
cd ..
docker build -t ummatics-frontend:latest -f frontend/Dockerfile frontend/

# 2. Tag and push to ECR
docker tag ummatics-frontend:latest 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:frontend-latest
docker push 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:frontend-latest

# 3. Pull and restart on EC2
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'cd /home/ubuntu/ummatics-impact-monitor && docker compose pull frontend && docker compose up -d frontend'
```

**Verification**
```bash
# Verify containers are running with new images
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'docker compose ps'

# Check actual code in container
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'docker exec ummatics_scheduler head -70 /app/scheduler.py | tail -25'

# Test the API endpoint
curl "http://3.226.110.16:5000/api/metrics"
```

### Key Takeaways (UPDATED Dec 14, 2025)
- **ALL services use ECR images**: api, scheduler, frontend - NO local builds on EC2
- **`docker compose build` is useless**: It does nothing when using `image:` instead of `build:`
- **MUST push to ECR**: Local changes only appear on EC2 after ECR push + pull
- **git on EC2 is irrelevant**: Code comes from ECR images, not local filesystem
- **Always verify**: Check container contents with `docker exec` to confirm deployment
- **Both containers share backend-latest**: api and scheduler use the same ECR backend image

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
## Deployment & Configuration Lessons (Dec 11, 2025)

### Always Check Database Schema Before Writing Queries
**Problem**: API failed after deployment with "relation 'google_alerts' does not exist" and "column 'scraped_at' does not exist" errors.

**Root Cause**: 
- Referenced non-existent table `google_alerts` (actual table: `news_mentions`)
- Referenced non-existent column `scraped_at` (actual columns: `created_at` for news, `posted_at` for social, `updated_at` for citations)

**Solution**:
1. Always check schema before writing queries:
   ```bash
   psql -c '\dt'  # List tables
   psql -c '\d table_name'  # Describe table structure
   ```
2. Verify column names in schema.sql or live database
3. This project uses:
   - `news_mentions` table (not google_alerts) with `created_at` timestamp
   - `social_mentions` table with `posted_at` timestamp
   - `citations` table with `updated_at` and `created_at` timestamps

**Prevention**: Check schema.sql or query database structure before writing new queries.

### Docker Deployment Requires ECR Push/Pull
**Problem**: Code changes didn't appear on EC2 after editing local files and running `docker-compose build`.

**Root Cause**: docker-compose.yml uses ECR images, not local builds:
```yaml
api:
  image: 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest
```

**Correct Deployment Process**:
1. Local: Login to ECR
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 182758038500.dkr.ecr.us-east-1.amazonaws.com
   ```
2. Local: Build and tag for ECR
   ```bash
   docker build -t 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest -f backend/Dockerfile .
   ```
3. Local: Push to ECR
   ```bash
   docker push 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest
   ```
4. EC2: Login to ECR (credentials expire after 12 hours)
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 182758038500.dkr.ecr.us-east-1.amazonaws.com
   ```
5. EC2: Pull and restart
   ```bash
   cd /home/ubuntu/ummatics-impact-monitor
   docker-compose pull
   docker-compose up -d
   ```

**Why This Matters**: Local `docker-compose build` has no effect when image comes from ECR registry.

### Always Check .env for Actual Credentials
**Problem**: Wasted time trying to authenticate with wrong password (`C0mpl3x!M0n1t0r_P@ssw0rd` from documentation examples).

**Root Cause**: Assumed complex password instead of checking actual .env file.

**Actual Credentials**:
```bash
DB_PASSWORD=abc123
DASHBOARD_PASSWORD=abc1234
```

**Solution**: Always check .env first:
```bash
cat .env | grep PASSWORD
```

**Prevention**: Never assume credentials from documentation or examples. Check the actual .env file.

### Overview Page UX Improvements Deployed (Dec 11, 2025)
**Changes**:
1. ✅ Stats now show total + 7-day new counts (e.g., "3962 total, +4 new (7 days)")
2. ✅ Empty panels hidden instead of showing "No data" messages
3. ✅ Twitter posts on Overview have "View Post →" clickable links
4. ✅ Frontend conditionally renders panels only when data exists

**API Changes**:
- Added `total_news_mentions`, `new_news_mentions_7d` to `current_week` response
- Added `total_social_mentions`, `new_social_mentions_7d` to `current_week` response
- Added `total_citations`, `new_citations_7d` to `current_week` response

**Frontend Changes**:
- MetricCard replaced with inline cards showing both totals and 7-day counts
- Platform breakdown, sentiment summary, trending keywords only render if data exists
- 12-week chart only renders if weekly_trends has data
- Twitter mentions include clickable "View Post →" link when url exists


### Citations Investigation Results (Dec 11, 2025)

**Organization Icon Missing - Expected Behavior**:
- User noticed no citations show organization icon
- Investigation: Queried database for `citation_type='organization'`
- Result: 0 organization citations exist (203 'word' type, 7 'unknown')
- **Reason**: All citations use "ummatic" (adjective), not "ummatics" (organization name)
- Classification logic is working correctly:
  - Checks for: 'ummatics.org', 'ummatics organization', 'ummatics institute', etc.
  - Checks if "ummatics" appears without "ummatic" variants
  - Current citations are academic papers using "ummatic" in titles (e.g., "Ummatic Unity", "Ummatic Concerns")
- **Conclusion**: No bug, just no organization mentions in scholarly literature yet

**Missing DOI Links - Fixed**:
- 44 out of 210 citations (21%) don't have DOI values
- Frontend only showed clickable link when DOI exists
- Solution: Added fallback to `source_url` when DOI is missing
- Now all citations are clickable (DOI link if available, source_url otherwise)

**Files Cleaned Up**:
Removed obsolete files from Google scraping attempts:
- `scripts/google_reddit_search.js` - Puppeteer script (failed attempt)
- `scripts/headless_*.js` - Screenshot testing scripts
- `scripts/*.png` - Test screenshots
- `test_*.py`, `test_website.html` - Old test files
- `*.json` data dumps - Old scraper results
- `process_apify_json.py` (root) - Duplicate file
- `deploy.sh` - Old deployment script (use `deploy-to-aws.sh`)


## UI/UX Fixes Round 2 (Dec 11, 2025 - Part 2)

### HTML Rendering in News Snippets
**Issue**: News tab showing raw HTML tags (e.g., `<b>text</b>`) instead of rendering them.

**Root Cause**: React escapes HTML by default for security (XSS protection).

**Solution**: Use `dangerouslySetInnerHTML` for trusted content:
```jsx
<p dangerouslySetInnerHTML={{ __html: mention.snippet || '' }}></p>
```

**Caution**: Only use for trusted/sanitized content (Google News RSS snippets are safe).

### Citation Chart Dual Y-Axis
**Issue**: "New This Week" metric too small compared to "Total Citations" on same scale.

**Solution**: Added secondary Y-axis in Recharts:
```jsx
<YAxis yAxisId="left" label={{ value: 'Total Citations', angle: -90, position: 'insideLeft' }} />
<YAxis yAxisId="right" orientation="right" label={{ value: 'New This Week', angle: 90, position: 'insideRight' }} />
<Line yAxisId="left" dataKey="total_citations" ... />
<Line yAxisId="right" dataKey="new_citations_this_week" ... />
```

**Result**: Each metric has its own scale, both clearly visible.

### Subreddit Statistics Enhancement
**Issue**: Only showed discovery date, user wanted total post count too.

**Solution**: Updated API query to JOIN with social_mentions:
```sql
SELECT 
    ds.subreddit_name,
    ds.discovered_at,
    COUNT(sm.id) as total_posts
FROM discovered_subreddits ds
LEFT JOIN social_mentions sm ON sm.platform = 'Reddit' 
    AND LOWER(sm.content) LIKE '%' || LOWER(ds.subreddit_name) || '%'
GROUP BY ds.subreddit_name, ds.discovered_at
```

**Frontend**: Display both discovery date and post count.

### Layout Issues with Conditional Rendering
**Problem**: Div structure became misaligned when using conditional rendering with multiple sections.

**Symptom**: Trending keywords appeared inside Recent Mentions container.

**Solution**: Properly close each conditional section:
```jsx
{recent_mentions.length > 0 && (
  <div>...</div>  // Close here
)}

{trending_keywords.length > 0 && (
  <div>...</div>  // Separate section
)}
```

**Prevention**: When using conditional rendering, ensure each condition has complete, self-contained JSX structure.

### Citation Icons Not Showing - User Confusion
**User Report**: "No organization icons on citations page"

**Investigation**: 
- Icons ARE defined and rendering correctly
- Issue: ALL citations have `citation_type='word'`, none have 'organization'
- User expected to see organization icons but none exist in data

**Resolution**: 
- Icons work correctly (WordIcon shows for 'word' type)
- No bug - just no organization citations in database yet
- Classification logic is correct and working as intended

**Lesson**: User perception issue - icons were working but user expected different icon type to appear.

### 12-Week Trend Chart "Empty"
**User Report**: Chart still showing empty

**Investigation**: 
- Data EXISTS in API (11 weeks of data)
- Chart was previously using `scale="log"` which fails with zeros
- Already fixed in previous session (changed to linear scale)
- User may have had cached version

**Resolution**: Hard refresh needed, or wait for deployment to propagate.

**Prevention**: Remind users to hard refresh (Ctrl+F5) after frontend deployments.


## 12-Week Trend Chart Fixes (Dec 11, 2025 - Part 3)

### Weekly Trends: Cumulative vs Delta Confusion
**Issue**: Overview page 12-week trend showed cumulative `total_citations` while news and social showed weekly counts, creating inconsistent visualization.

**Root Cause**: 
- `weekly_snapshots` table stores **cumulative totals** (running sum)
- Chart was displaying these cumulative values directly
- News/social were already showing as weekly increments in their respective tabs

**Investigation**:
```sql
SELECT week_start_date, total_citations FROM weekly_snapshots ORDER BY week_start_date DESC LIMIT 3;
-- Results: 684, 684, 681 (cumulative)
-- User expected: 0, 3, 0 (new per week)
```

**Solution**: Calculate weekly deltas using SQL window function:
```sql
WITH weekly_ordered AS (
    SELECT 
        week_start_date,
        total_citations,
        LAG(total_citations, 1, 0) OVER (ORDER BY week_start_date) as prev_citations
    FROM weekly_snapshots
    ORDER BY week_start_date
)
SELECT 
    week_start_date,
    total_citations - prev_citations as total_citations  -- Delta
FROM weekly_ordered
ORDER BY week_start_date DESC
LIMIT 12
```

**Key Points**:
- `LAG()` window function gets previous week's value
- Must ORDER BY `week_start_date` ASC in OVER clause for correct LAG direction
- Then ORDER BY DESC at end for most recent weeks first
- Subtracting previous from current gives weekly increment

**Result**: Chart now shows consistent "new this week" metrics across all three lines.

**Data Anomalies Found**:
- Some weeks show negative deltas (e.g., social_mentions: -3907)
- Indicates data correction/deletion occurred in that week
- This is expected behavior if bad data was cleaned up

### HTML Rendering in News Snippets - Deployment Issue
**User Report**: Bold tags still showing as `<b>text</b>` instead of rendering

**Investigation**:
- Code fix was already implemented: `dangerouslySetInnerHTML={{ __html: mention.snippet }}`
- Fix was in codebase but not deployed to production
- Docker image was cached, not rebuilt with changes

**Root Cause**: 
- Frontend uses build-time compilation (Vite)
- Changes in source don't appear until new Docker image built
- Previous push used cached layers, skipped rebuild

**Solution**: 
1. Force rebuild: `docker build --no-cache` (or just rebuild after code change)
2. Push to ECR
3. Pull on EC2 and restart containers
4. User must hard refresh browser (Ctrl+F5) to clear cached JS

**Prevention**:
- Always rebuild after frontend code changes (even if Dockerfile unchanged)
- Remind users to hard refresh after frontend deployments
- Docker caches layers but Vite build creates new bundle hashes

**Verification**:
```bash
# Check deployed bundle hash
docker exec ummatics_frontend cat /usr/share/nginx/html/index.html | grep -o 'index-[^.]*\.js'
# Result: index-lMWlhxES.js (new hash means new build)
```


---

## CRITICAL: Deployment Verification Checklist (December 11, 2025)

**Context**: Previous deployment claimed success but website was broken due to lack of verification.

**The Problem**: 
- Deployed backend and frontend changes
- Claimed "both fixes deployed and working"
- Did NOT test if website actually works
- User discovered website broken (502 errors, API unreachable)

**What Was Missed**:
1. API container got new IP after recreation (172.18.0.4)
2. Frontend nginx cached old IP (172.18.0.3) → Connection refused
3. Weekly trends had negative deltas (data quality issue)
4. No verification that frontend actually loads
5. No verification that API endpoints respond

**MANDATORY Verification Checklist Before Claiming Success**:

### After Every Backend Deployment:
```bash
# 1. Verify API container is running
ssh ubuntu@EC2 "docker ps | grep ummatics_api"

# 2. Test API responds from within container
ssh ubuntu@EC2 "docker exec ummatics_api python -c \"import requests; print(requests.get('http://localhost:5000/api/overview', headers={'Authorization': 'Bearer PASSWORD'}).status_code)\""

# 3. Test API through nginx proxy
curl -s 'http://EC2:3000/api/overview' -H 'Authorization: Bearer PASSWORD' | python3 -c "import sys, json; data = json.load(sys.stdin); print('✓ API works' if 'current_week' in data else '✗ API broken')"

# 4. Check for errors in API logs
ssh ubuntu@EC2 "docker logs ummatics_api --tail=50 | grep -i error"
```

### After Every Frontend Deployment:
```bash
# 1. Verify frontend container is running
ssh ubuntu@EC2 "docker ps | grep ummatics_frontend"

# 2. Test homepage loads
curl -s 'http://EC2:3000/' | grep -q '<title>Ummatics' && echo "✓ Frontend loads" || echo "✗ Frontend broken"

# 3. Check frontend can reach API (check nginx logs for 502 errors)
ssh ubuntu@EC2 "docker logs ummatics_frontend --tail=50 | grep -c '502 Bad Gateway'"

# 4. If nginx showing 502:
ssh ubuntu@EC2 "cd ummatics-impact-monitor && docker-compose restart frontend"
```

### Data Quality Checks:
```bash
# 1. Verify no negative numbers in weekly trends
curl -s 'http://EC2:3000/api/overview' -H 'Authorization: Bearer PASSWORD' | python3 -c "
import sys, json
data = json.load(sys.stdin)
wt = data['weekly_trends']
has_negative = any(item['total_citations'] < 0 or item['total_news_mentions'] < 0 or item['total_social_mentions'] < 0 for item in wt)
print('✗ Negative deltas found!' if has_negative else '✓ Data quality OK')
"

# 2. Verify HTML rendering
curl -s 'http://EC2:3000/assets/index-*.js' | grep -q 'dangerouslySetInnerHTML' && echo "✓ HTML rendering enabled" || echo "✗ HTML rendering missing"
```

### Container Network Issues:
**Symptom**: 502 Bad Gateway, "Connection refused" in frontend logs
**Root Cause**: When containers are recreated, they get new IPs. Nginx may cache old IP.
**Solution**: Always restart frontend after recreating backend:
```bash
ssh ubuntu@EC2 "cd ummatics-impact-monitor && docker-compose restart frontend"
```

**Verification Flow**:
1. Deploy changes (backend/frontend)
2. Run verification checklist above
3. If ANY check fails → diagnose and fix
4. Re-run ALL checks
5. Only claim success when ALL checks pass

**Never claim deployment success without running verification tests first.**


---

## AWS Lambda Sentiment Analysis Implementation (December 13, 2025)

**Context**: Replaced in-container transformer sentiment with AWS Lambda to reduce costs and improve scalability.

**UPDATE (December 14, 2025)**: Successfully deployed to production. See "Production Deployment Experience" section below for critical fixes and actual deployment steps.

### Problem Statement
- Running transformer model in EC2 container uses memory 24/7 (~$10-15/month)
- TextBlob sentiment analysis lacks accuracy for nuanced text
- Need cost-effective ML sentiment without constant compute costs

### Solution: AWS Lambda with DistilBERT

**Architecture**:
- Lambda function with containerized DistilBERT model (268MB)
- Invoked on-demand from backend via boto3
- Falls back to TextBlob if Lambda unavailable

**Cost Comparison**:
```
Current (EC2 24/7):     ~$10-15/month
Lambda (pay-per-use):   ~$0.01/month (after free tier)
Savings:                ~99% cost reduction
```

**Free Tier Benefits**:
- 1M Lambda requests/month free
- 400,000 GB-seconds compute free
- For typical usage (10k sentiments/month): FREE

### Implementation Details

**Files Created**:
- `lambda/sentiment_function.py` - Lambda handler with DistilBERT
- `lambda/Dockerfile` - Container with transformers library
- `lambda/template.yaml` - SAM/CloudFormation template
- `lambda/deploy.sh` - Automated deployment script
- `backend/lambda_sentiment.py` - Lambda client for backend

**Key Features**:
1. **Batch Processing**: Handles up to 50 texts per invocation
2. **Model Caching**: Reuses model across warm invocations (~100ms)
3. **Error Handling**: Falls back to TextBlob on Lambda errors
4. **Cost Optimization**: 2GB memory, 60s timeout (minimal cost)

**Configuration**:
```bash
# Enable Lambda sentiment in .env
USE_LAMBDA_SENTIMENT=1
SENTIMENT_LAMBDA_FUNCTION=ummatics-sentiment-analysis
AWS_REGION=us-east-1
```

### Deployment Process

**Step 1: Deploy Lambda**
```bash
cd lambda
./deploy.sh
```

This creates:
- ECR repository for Lambda container
- Lambda function with 2GB memory, 60s timeout
- IAM role with execution permissions
- Function URL for invocation

**Step 2: Grant EC2 Lambda Invocation Permission**

Attach IAM policy to EC2 instance role:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "lambda:InvokeFunction",
    "Resource": "arn:aws:lambda:*:*:function:ummatics-sentiment-analysis"
  }]
}
```

**Step 3: Enable in Backend**

Update `.env`:
```bash
USE_LAMBDA_SENTIMENT=1
```

Rebuild and deploy backend:
```bash
docker-compose build api
docker-compose up -d api
```

### Performance Characteristics

**Cold Start** (first invocation):
- Duration: ~5-10 seconds
- Happens when: Lambda hasn't been invoked recently
- Mitigation: Accept delay or use provisioned concurrency (costs extra)

**Warm Start** (subsequent invocations):
- Duration: ~100-500ms for batch of 50 texts
- Model cached in memory
- Much faster than cold start

**Batch Sizes**:
- Recommended: 50 texts per invocation
- Maximum: Limited by 6MB payload size
- Backend automatically batches large datasets

### Cost Monitoring

**View Lambda Costs**:
```bash
# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=ummatics-sentiment-analysis \
  --start-time 2025-12-01T00:00:00Z \
  --end-time 2025-12-31T23:59:59Z \
  --period 86400 \
  --statistics Sum
```

**Set Billing Alerts**:
1. AWS Billing Console → Budgets
2. Create budget: "Lambda Sentiment"
3. Threshold: $1/month (should never hit this)
4. Email alert if exceeded

### Troubleshooting

**Issue**: "Lambda invocation failed"
- **Cause**: Missing IAM permissions on EC2
- **Fix**: Attach Lambda invoke policy to EC2 instance role

**Issue**: "Task timed out after 60 seconds"
- **Cause**: Processing too many texts at once
- **Fix**: Reduce batch size in `lambda_sentiment.py` (default: 50)

**Issue**: "Out of memory"
- **Cause**: Lambda memory too low for model
- **Fix**: Already set to 2048MB (sufficient for DistilBERT)

**Issue**: Cold start too slow
- **Accept**: 5-10s delay on first request is normal
- **Or**: Enable provisioned concurrency (costs ~$10/month)

**Issue**: Backend still using TextBlob
- **Check**: `USE_LAMBDA_SENTIMENT=1` in `.env`
- **Check**: Backend container restarted after `.env` change
- **Check**: Lambda function deployed and accessible

### Lessons Learned

**What Worked Well**:
✅ Lambda free tier covers our usage completely
✅ 99% cost reduction vs EC2 24/7
✅ DistilBERT accuracy >> TextBlob
✅ Automatic scaling (no capacity planning)
✅ Easy to deploy with SAM/CloudFormation

**What to Watch**:
⚠️ Cold starts add 5-10s latency (acceptable for batch jobs)
⚠️ IAM permissions must be configured correctly
⚠️ Lambda has 6MB payload limit (batch accordingly)
⚠️ Transformer model requires 2GB memory (not 512MB)

**Cost Optimization Tips**:
1. Use Lambda (not Fargate/EC2) for infrequent workloads
2. Batch requests to minimize invocations
3. Use CPU-only transformers (no GPU needed for sentiment)
4. Monitor costs monthly (should be $0 in free tier)
5. Set billing alerts to catch unexpected usage

**When to Use Lambda Sentiment**:
- ✅ Batch sentiment analysis (nightly jobs, weekly updates)
- ✅ Low to medium volume (<100k texts/month)
- ✅ Can tolerate occasional cold start delays
- ✅ Want to minimize infrastructure costs

**When NOT to Use**:
- ❌ Real-time, low-latency requirements (<100ms)
- ❌ Very high volume (>1M texts/month, consider Fargate)
- ❌ Need custom fine-tuned models (Lambda has size limits)

### Testing

**Local Test** (before deploying):
```bash
cd lambda
./test-local.sh
```

**AWS Test** (after deployment):
```bash
aws lambda invoke \
  --function-name ummatics-sentiment-analysis \
  --payload '{"texts":["I love this!", "This is bad"]}' \
  response.json

cat response.json | python3 -m json.tool
```

**Backend Integration Test**:
```python
# In backend container
python -c "
from lambda_sentiment import analyze_sentiment_lambda
results = analyze_sentiment_lambda(['Great product!', 'Terrible service'])
print(results)
# Expected: [('positive', 0.98), ('negative', 0.87)]
"
```

### Migration Path

**Phase 1: Deploy Lambda** (no backend changes)
```bash
cd lambda && ./deploy.sh
```

**Phase 2: Test Lambda Independently**
```bash
aws lambda invoke --function-name ummatics-sentiment-analysis \
  --payload '{"texts":["test"]}' response.json
```

**Phase 3: Enable in Backend**
```bash
# Update .env
echo "USE_LAMBDA_SENTIMENT=1" >> .env

# Rebuild backend
docker-compose build api
docker-compose up -d api
```

**Phase 4: Verify Backend Using Lambda**
```bash
# Check backend logs for "Invoking Lambda for X texts"
docker logs ummatics_api | grep Lambda
```

**Phase 5: Remove Old Transformer Code** (optional)
```bash
# Once Lambda proven stable, remove:
# - backend/transformer_sentiment.py
# - transformer dependencies from requirements.txt
# This saves container size and build time
```

### Cleanup (if needed)

To remove Lambda and revert to TextBlob:
```bash
# 1. Disable Lambda in backend
sed -i 's/USE_LAMBDA_SENTIMENT=1/USE_LAMBDA_SENTIMENT=0/' .env
docker-compose restart api

# 2. Delete Lambda resources
aws cloudformation delete-stack --stack-name ummatics-sentiment-stack
aws ecr delete-repository --repository-name ummatics-sentiment --force
```

---

### Production Deployment Experience (December 14, 2025)

**CRITICAL LESSONS from actual deployment - READ THIS before deploying Lambda:**

#### Issue 1: Docker Build Failed - Missing C Compiler

**Problem**: Initial `deploy.sh` failed with:
```
error: metadata-generation-failed
× Encountered error while generating package metadata for numpy
ERROR: Unknown compiler(s): [['cc'], ['gcc'], ['clang']]
```

**Root Cause**: Lambda base image (`public.ecr.aws/lambda/python:3.11`) doesn't include build tools. NumPy tried to compile from source.

**Fix**: Use `--only-binary :all:` flag to force pre-built wheels:
```dockerfile
RUN pip install --no-cache-dir --only-binary :all: -r requirements-transformer.txt
```

**Lesson**: Always use binary wheels in Lambda containers. Never compile from source.

---

#### Issue 2: Read-Only Filesystem - Model Download Failed

**Problem**: Lambda function crashed with:
```
[Errno 30] Read-only file system: '/home/sbx_user1051'
Lambda invocation timed out after 60 seconds
```

**Root Cause**: HuggingFace transformers tried to download model to home directory at runtime. Lambda only allows writes to `/tmp`.

**Attempted Fix #1 (FAILED)**: Set environment variables in Python code:
```python
os.environ['TRANSFORMERS_CACHE'] = '/tmp/transformers_cache'
os.environ['HF_HOME'] = '/tmp/hf_home'
```
❌ Still failed because environment variables were set AFTER imports started downloading.

**Working Fix #2**: Bundle model in container image during build:
```dockerfile
# Set cache location BEFORE pip install
ENV TRANSFORMERS_CACHE=/tmp/transformers_cache
ENV HF_HOME=/tmp/hf_home

# Download model during Docker build (not at runtime)
RUN mkdir -p /opt/ml/model && \
    python -c "from transformers import pipeline; \
    p = pipeline('sentiment-analysis', \
      model='distilbert-base-uncased-finetuned-sst-2-english', \
      model_kwargs={'cache_dir': '/opt/ml/model'})"
```

Then in Lambda function code:
```python
MODEL_CACHE_DIR = "/opt/ml/model"

sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="distilbert-base-uncased-finetuned-sst-2-english",
    model_kwargs={"cache_dir": MODEL_CACHE_DIR},
    device=-1,
    truncation=True,
    max_length=512
)
```

**Lessons**:
1. **NEVER download models at Lambda runtime** - filesystem is read-only except /tmp
2. **Bundle models in container** during Docker build
3. **Set environment variables in Dockerfile** BEFORE any downloads
4. **Use /opt/ml/** for model storage (persistent across invocations)

---

#### Issue 3: Timeout During Cold Start

**Problem**: Lambda timed out at 60 seconds during first invocation (cold start).

**Analysis**: Logs showed:
```
Loading DistilBERT model (cold start)...
Model loaded successfully
END RequestId: xxx Duration: 60000.00 ms Status: timeout
```

Model loaded right at 60s mark, then timed out immediately.

**Fix**: Increase timeout to 120 seconds:
```bash
aws lambda update-function-configuration \
  --function-name ummatics-sentiment-analysis \
  --timeout 120
```

**Lessons**:
1. **Cold starts for ML models** take 60-120 seconds (DistilBERT is 268MB)
2. **Default 60s timeout is insufficient** for transformer cold starts
3. **Warm starts** are fast (~100-500ms) after first invocation
4. **Accept cold start delay** or use provisioned concurrency ($$)

---

#### Issue 4: SAM CLI Not Installed

**Problem**: `deploy.sh` failed with:
```
./deploy.sh: line 44: sam: command not found
```

**Fix**: Deploy using AWS CloudFormation directly instead of SAM:
```bash
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name ummatics-sentiment-lambda \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ImageUri=<ECR_URI>
```

**Lesson**: SAM CLI is just a wrapper around CloudFormation. Can use CloudFormation directly if SAM not installed.

---

#### Issue 5: EC2 IAM Role Missing Lambda Permissions

**Problem**: Backend container on EC2 failed to invoke Lambda:
```
AccessDeniedException: User: arn:aws:sts::xxx:assumed-role/ummatics-ssm-role/i-xxx 
is not authorized to perform: lambda:InvokeFunction on resource: 
arn:aws:lambda:us-east-1:xxx:function:ummatics-sentiment-analysis
```

**Root Cause**: EC2 instance role (`ummatics-ssm-role`) had SSM and ECR permissions but not Lambda.

**Fix**: Add inline IAM policy to EC2 role:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "lambda:InvokeFunction",
    "Resource": "arn:aws:lambda:us-east-1:182758038500:function:ummatics-sentiment-analysis"
  }]
}
```

Apply with:
```bash
aws iam put-role-policy \
  --role-name ummatics-ssm-role \
  --policy-name LambdaInvokePolicy \
  --policy-document file:///tmp/lambda-invoke-policy.json
```

**Lesson**: EC2 instances using IAM roles to invoke Lambda MUST have `lambda:InvokeFunction` permission on the target function.

---

#### Issue 6: Backend Image Deployment

**Problem**: EC2 couldn't pull updated backend image from ECR:
```
403 Forbidden: failed to resolve reference
```

**Root Cause**: EC2 instance wasn't logged into ECR.

**Fix**: Login to ECR from EC2 before pulling:
```bash
ssh ubuntu@EC2_IP 'aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 182758038500.dkr.ecr.us-east-1.amazonaws.com'

ssh ubuntu@EC2_IP 'cd /home/ubuntu/ummatics-impact-monitor && \
  docker compose pull api && docker compose up -d api'
```

**Lesson**: ECR authentication expires. Must re-login before pulling images.

---

### Actual Deployment Steps (TESTED AND WORKING)

**These are the exact steps that successfully deployed Lambda to production:**

#### Step 1: Build and Deploy Lambda Function

```bash
cd /home/tahir/ummatics-impact-monitor/lambda

# Build Docker image with bundled model
docker build -t ummatics-sentiment:latest .

# Tag for ECR
docker tag ummatics-sentiment:latest \
  182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-sentiment:latest

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  182758038500.dkr.ecr.us-east-1.amazonaws.com

# Push to ECR
docker push 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-sentiment:latest

# Deploy Lambda via CloudFormation
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name ummatics-sentiment-lambda \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ImageUri=182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-sentiment:latest

# Increase timeout to 120s for cold starts
aws lambda update-function-configuration \
  --function-name ummatics-sentiment-analysis \
  --timeout 120
```

#### Step 2: Test Lambda Independently

```bash
aws lambda invoke \
  --function-name ummatics-sentiment-analysis \
  --cli-binary-format raw-in-base64-out \
  --payload '{"texts": ["I love this product!", "This is terrible"]}' \
  /tmp/lambda-response.json

cat /tmp/lambda-response.json
# Expected output:
# {"statusCode": 200, "body": "{\"results\": [{\"sentiment\": \"positive\", \"score\": 1.0}, ...]}"}
```

#### Step 3: Add Lambda Invoke Permission to EC2 Role

```bash
cat > /tmp/lambda-invoke-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "lambda:InvokeFunction",
    "Resource": "arn:aws:lambda:us-east-1:182758038500:function:ummatics-sentiment-analysis"
  }]
}
EOF

aws iam put-role-policy \
  --role-name ummatics-ssm-role \
  --policy-name LambdaInvokePolicy \
  --policy-document file:///tmp/lambda-invoke-policy.json
```

#### Step 4: Update Backend with Lambda Support

```bash
# Upload Lambda client code
scp -i ~/.ssh/ummatics-monitor-key.pem \
  backend/lambda_sentiment.py \
  ubuntu@3.226.110.16:/home/ubuntu/ummatics-impact-monitor/backend/

scp -i ~/.ssh/ummatics-monitor-key.pem \
  backend/ingestion.py \
  ubuntu@3.226.110.16:/home/ubuntu/ummatics-impact-monitor/backend/

scp -i ~/.ssh/ummatics-monitor-key.pem \
  backend/requirements.txt \
  ubuntu@3.226.110.16:/home/ubuntu/ummatics-impact-monitor/backend/

# Add Lambda configuration to .env
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 '
cd /home/ubuntu/ummatics-impact-monitor
echo "USE_LAMBDA_SENTIMENT=1" >> .env
echo "AWS_ACCESS_KEY_ID=YOUR_KEY" >> .env
echo "AWS_SECRET_ACCESS_KEY=YOUR_SECRET" >> .env
echo "AWS_DEFAULT_REGION=us-east-1" >> .env
'
```

#### Step 5: Build and Push Updated Backend Image

```bash
cd /home/tahir/ummatics-impact-monitor/backend

# Build backend with Lambda support
docker build -t 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest .

# Push to ECR
docker push 182758038500.dkr.ecr.us-east-1.amazonaws.com/ummatics-impact-monitor:backend-latest
```

#### Step 6: Deploy to EC2

```bash
# Login to ECR on EC2
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 \
  'aws ecr get-login-password --region us-east-1 | \
   docker login --username AWS --password-stdin \
   182758038500.dkr.ecr.us-east-1.amazonaws.com'

# Pull and restart API
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 \
  'cd /home/ubuntu/ummatics-impact-monitor && \
   docker compose pull api && \
   docker compose up -d api'

# CRITICAL: Restart frontend (per lessons learned)
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 \
  'cd /home/ubuntu/ummatics-impact-monitor && \
   docker compose restart frontend'
```

#### Step 7: Verify Deployment

```bash
# 1. Check API container running
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 "docker ps | grep ummatics_api"

# 2. Test API responds
curl -s 'http://3.226.110.16:3000/api/overview' -H 'Authorization: Bearer abc1234'

# 3. Test Lambda from EC2
ssh -i ~/.ssh/ummatics-monitor-key.pem ubuntu@3.226.110.16 'python3 << "EOF"
import boto3, json
lambda_client = boto3.client("lambda", region_name="us-east-1")
response = lambda_client.invoke(
    FunctionName="ummatics-sentiment-analysis",
    Payload=json.dumps({"texts": ["I love this!", "This is terrible"]})
)
result = json.loads(response["Payload"].read())
print(json.dumps(result, indent=2))
EOF
'

# Expected: {"statusCode": 200, "body": "{\"results\": [{\"sentiment\": \"positive\", ...}]}"}
```

---

### Cost Monitoring (December 14, 2025)

**Current Lambda Usage**:
- Function name: `ummatics-sentiment-analysis`
- Memory: 2048 MB
- Timeout: 120 seconds
- Cold start: ~60-90 seconds
- Warm start: ~100-500ms

**Expected Costs**:
```
Estimated monthly usage:
- Ingestion runs: ~4-8 times/month
- Records per run: ~100-500 social mentions
- Lambda invocations: ~10-100/month (batched 50 texts each)

Free tier: 1M requests, 400,000 GB-seconds
Our usage: ~100 requests, ~20,000 GB-seconds
Cost: $0.00 (well within free tier)
```

**Actual cost will be $0** unless we exceed:
- 1 million invocations/month (we do ~100)
- 400,000 GB-seconds compute (we use ~20,000)

**Cost Alert** (recommended):
```bash
# Set billing alert at $1/month (should never hit)
aws cloudwatch put-metric-alarm \
  --alarm-name lambda-sentiment-cost-alert \
  --alarm-description "Alert if Lambda sentiment costs exceed $1" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 1.0 \
  --comparison-operator GreaterThanThreshold
```

---

### Final Deployment Status

**✅ Successfully Deployed Components**:
1. Lambda function with DistilBERT (2GB memory, 120s timeout)
2. ECR repository with Lambda container image
3. Backend integration with boto3 Lambda client
4. EC2 IAM permissions for Lambda invocation
5. Environment variables configured on EC2

**✅ Verification Checklist PASSED**:
- [x] API container running on EC2
- [x] API responds through nginx (HTTP 200)
- [x] No errors in API logs
- [x] Lambda invokes successfully from EC2
- [x] Frontend accessible (HTTP 200)

**📊 Performance Metrics**:
- Cold start: 60-90 seconds (acceptable for batch jobs)
- Warm start: 100-500ms (fast for real-time)
- Batch size: 50 texts per invocation
- Cost: $0.00/month (within free tier)

**🎯 Cost Savings Achieved**:
- Previous: ~$10-15/month (EC2 transformer 24/7)
- Current: ~$0.00/month (Lambda pay-per-use)
- **Savings: 99%+ reduction**

---

### Key Takeaways for Future Lambda ML Deployments

**DO**:
✅ Bundle ML models in container during Docker build
✅ Use pre-built binary wheels (--only-binary :all:)
✅ Set timeout to 120s+ for transformer models
✅ Test Lambda independently before backend integration
✅ Add Lambda invoke permissions to EC2 IAM role
✅ Login to ECR before pulling images
✅ Restart frontend after backend changes

**DON'T**:
❌ Download models at runtime (filesystem is read-only)
❌ Use default 60s timeout for ML models
❌ Assume IAM permissions exist (verify with test invocation)
❌ Forget to set environment variables in Dockerfile
❌ Skip verification steps (always test end-to-end)

**CRITICAL**:
⚠️ **Always bundle models in container** - runtime downloads will fail
⚠️ **Always test Lambda independently** - before backend integration
⚠️ **Always verify IAM permissions** - EC2 needs lambda:InvokeFunction
⚠️ **Always restart frontend** - after backend container changes


