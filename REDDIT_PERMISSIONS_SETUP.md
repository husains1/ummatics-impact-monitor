# Reddit Support - Permissions & Setup Quick Reference

## What Permissions Are Required?

### 1. Reddit Developer Account
**Prerequisite**: Reddit user account (free)

**Steps to Get Credentials**:
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create another app..." at bottom
3. Fill in app details:
   - **Name**: "Ummatics Impact Monitor" (or any name)
   - **App type**: Select "script"
   - **Redirect URI**: `http://localhost:8000` (required but unused for script type)
4. Click "Create app"
5. You'll see the credentials:
   - **Client ID**: Below the app name (long alphanumeric string)
   - **Client Secret**: Next to "secret"

### 2. Environment Variables Needed
```bash
# Reddit API Credentials (set in .env or docker-compose environment)
REDDIT_CLIENT_ID=xxxxxxxxxxxx              # Your app's client ID
REDDIT_CLIENT_SECRET=xxxxxxxxxxxx          # Your app's client secret
REDDIT_USERNAME=your_reddit_username       # Your Reddit account username
REDDIT_PASSWORD=your_reddit_password       # Your Reddit account password
REDDIT_USER_AGENT="UmmaticsMonitor/1.0 by YourRedditUsername"

# Search configuration
REDDIT_SEARCH_TERMS="ummatics"             # What to search for (comma-separated)
REDDIT_SUBREDDITS="r/science,r/health"    # Optional: specific subreddits (comma-separated)

# Feature flag
REDDIT_INGESTION_ENABLED=1                 # Enable/disable Reddit ingestion (0 or 1)
USE_TRANSFORMER=1                          # Use transformer sentiment (existing)
```

### 3. Database Permissions
**Existing permissions are sufficient** because:
- Your database user already has:
  - `CREATE TABLE` - ✓ Creates reddit_mentions, reddit_daily_metrics, etc.
  - `INSERT` - ✓ Stores fetched Reddit posts
  - `UPDATE` - ✓ Updates sentiment scores
  - `SELECT` - ✓ Queries aggregations
  - `DELETE` - ✓ Cleanup/archival (optional)

**No new database user roles needed** ✓

### 4. API Rate Limits (Reddit API)
- **Authenticated Request Limit**: 60 requests per minute per user
- **Current Usage**: ~60-100 requests per day with our ingestion
- **Status**: ✓ **Well within limits** (less than 2% of capacity)

### 5. File System Permissions
```bash
# Required for Docker mounts (likely already set)
-rw-r--r--  .env                          # Read by docker-compose
drwxr-xr-x  backend/                      # Read by Docker build
drwxr-xr-x  frontend/                     # Read by Docker build

# Suggested (for local testing)
chmod 600 .env  # Restrict access to credentials
```

### 6. AWS Permissions (if deploying to EC2)
**Already have these (existing infrastructure)**:
- ✓ EC2 instance access
- ✓ RDS database access (PostgreSQL)
- ✓ Security group egress (allows outbound HTTPS to Reddit API)

**Verify Security Group**:
```bash
# Should allow outbound on port 443 (HTTPS)
# Command to verify on EC2:
curl https://oauth.reddit.com/api/v1/access_token  # Should get a response
```

### 7. Docker Permissions
```bash
# Already configured
docker ps                    # Can list containers
docker-compose logs          # Can view logs
docker-compose exec api ...  # Can exec into containers
```

### 8. GitHub/CI-CD Permissions (optional)
If using GitHub Actions for auto-deployment:
- Store Reddit credentials as GitHub Secrets
- Don't commit `.env` file (already in `.gitignore`?)

## Permissions Summary Table

| Component | Permission Type | Required | Status |
|-----------|-----------------|----------|--------|
| Reddit API | OAuth 2.0 Client | YES | Create via Reddit Settings |
| Reddit Account | Read-only access | YES | Your personal account works |
| Database | INSERT/UPDATE/SELECT | NO NEW | Already have from PostgreSQL user |
| AWS EC2 | Outbound HTTPS (port 443) | YES | Verify security group |
| Docker | Image building & execution | NO NEW | Already working |
| File system | `.env` file access | YES | Set `chmod 600 .env` |
| GitHub | Secrets storage (optional) | OPTIONAL | For CI/CD only |

## Implementation Checklist

- [ ] **Step 1**: Create Reddit app at https://www.reddit.com/prefs/apps
- [ ] **Step 2**: Add credentials to `.env` file
- [ ] **Step 3**: Verify AWS security group allows outbound HTTPS (port 443)
- [ ] **Step 4**: Deploy backend changes (Docker image rebuild)
- [ ] **Step 5**: Run migration to create new database tables
- [ ] **Step 6**: Test Reddit ingestion manually
- [ ] **Step 7**: Deploy frontend changes
- [ ] **Step 8**: Monitor logs for errors

## Common Issues & Solutions

### Issue: "Authentication failed" when ingesting Reddit
**Solution**: Verify credentials in `.env`:
```bash
docker-compose exec -T api python3 -c "
import os
print(f'Client ID: {os.getenv(\"REDDIT_CLIENT_ID\")[:10]}...')
print(f'Username: {os.getenv(\"REDDIT_USERNAME\")}')
"
```

### Issue: "Rate limit exceeded"
**Solution**: This is unlikely but if it happens:
- Wait 60 seconds before retrying
- Consider adjusting search terms to reduce API calls
- Add backoff logic to ingestion (already implemented in PRAW)

### Issue: "Outbound HTTPS blocked" on EC2
**Solution**: Check security group rules:
```bash
# On EC2, try to reach Reddit API
curl -I https://oauth.reddit.com/
# Should return HTTP/2 200 or similar, not timeout
```

### Issue: Database table creation fails
**Solution**: Ensure your DB user has permissions:
```sql
-- Run as postgres user to grant explicitly:
GRANT CREATE ON DATABASE ummatics_monitor TO postgres;
```

## Next: What to Do After Setup

1. **Backend Development** (after getting credentials):
   - Create `backend/reddit_ingestion.py`
   - Add Reddit search/ingestion functions
   - Wire into `backend/ingestion.py`

2. **Database Migration**:
   - Run SQL from REDDIT_IMPLEMENTATION_PLAN.md to create tables

3. **Testing**:
   ```bash
   # After deployment, test with:
   docker-compose exec -T api python3 -c "from reddit_ingestion import ingest_reddit; ingest_reddit()"
   ```

4. **Frontend Development**:
   - Create React components for Reddit tab
   - Add API calls to fetch Reddit data
   - Style with Tailwind CSS

---

**Questions?** Refer to REDDIT_IMPLEMENTATION_PLAN.md for detailed technical specifications.
