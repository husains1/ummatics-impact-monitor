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
