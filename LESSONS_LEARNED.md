# Lessons Learned - Ummatics Impact Monitor

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

**Step 1: Sync Code to EC2**
```bash
# On EC2, pull latest code from GitHub
ssh ... 'cd /home/ubuntu/ummatics-impact-monitor && git pull origin main'
```

**Step 2: Handle Local Changes**
```bash
# If there are local modifications on EC2, stash them first
ssh ... 'cd /home/ubuntu/ummatics-impact-monitor && git stash && git pull origin main'
```

**Step 3: Rebuild Container with Fresh Code**
```bash
# Now rebuild using the updated code
ssh ... 'cd /home/ubuntu/ummatics-impact-monitor && docker compose build --no-cache api && docker compose up -d api'
```

**Step 4: Verify the Fix**
```bash
# Check that the code change is actually in the running container
ssh ... 'grep -A 5 "specific code pattern" /home/ubuntu/ummatics-impact-monitor/backend/api.py'

# Test the API endpoint to confirm behavior changed
curl -s -H "Authorization: Bearer token" "http://host/api/endpoint" | python3 -c "verification script"
```

### Alternative: Use ECR Images for Backend Too

To make backend deployments consistent with frontend:

1. **Update docker-compose.yml on EC2** to use ECR image instead of build
2. **Push backend changes**: Build locally → Tag → Push to ECR → Pull on EC2
3. **Advantage**: No need to sync code to EC2, just pull new image

### Key Takeaways
- **Code must be on EC2 before building**: `docker compose build` uses local files, not ECR
- **Git pull BEFORE rebuild**: Always sync code first when using `build:` in docker-compose
- **Test what you deploy**: Don't assume it worked; verify the actual behavior changed
- **Two deployment methods**: Either sync code + rebuild, OR push image + pull
- **Never trust "it should work"**: Always verify with actual API tests
- **Check container contents**: Use `docker exec` or SSH to verify files if unsure

---

## User Guidelines

### Frontend Deployment
1. Always re-deploy the frontend on AWS after making any frontend code changes
2. Use full npm rebuild without cache locally and then push to ECR
3. Use ECR to deploy the frontend on AWS
4. Ensure previous versions of the frontend are cleaned up and no longer available on the EC2 node
5. Always confirm the deployment by connecting to the website URL

### Backend Deployment
1. **CRITICAL**: Pull latest code to EC2 BEFORE rebuilding containers (`git pull origin main`)
2. Handle any local changes on EC2 with `git stash` if needed
3. Rebuild with `--no-cache` flag to ensure fresh build
4. **ALWAYS VERIFY**: Test the API endpoint to confirm changes took effect
5. Don't trust the build success message - verify actual behavior

### Security and Resource Guidelines
1. **NEVER run git checkout/commit/push from EC2**: Your credentials should NOT be stored on EC2
   - EC2 should only pull code, never push changes
   - Keep git credentials local to your development machine
   - Use SSH to EC2 for deployment only, not for development workflow
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