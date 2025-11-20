# Reddit Support - Permissions Checklist & Quick Reference

## ✅ Permissions Verification Checklist

### Reddit API Setup
- [ ] **Create Reddit account** (if needed)
- [ ] **Go to** https://www.reddit.com/prefs/apps
- [ ] **Create new app**
  - [ ] Name: `Ummatics Impact Monitor`
  - [ ] Type: `script`
  - [ ] Redirect URI: `http://localhost:8000`
  - [ ] Click "Create app"
- [ ] **Copy credentials**
  - [ ] Client ID (under app name)
  - [ ] Client Secret (next to "secret" label)
  - [ ] Your Reddit username
  - [ ] Your Reddit password

### Environment Variables Required
Add to `.env` file or docker-compose.yml:
```bash
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
REDDIT_USER_AGENT="UmmaticsMonitor/1.0 by YourUsername"
REDDIT_SEARCH_TERMS="ummatics"
REDDIT_INGESTION_ENABLED=1
USE_TRANSFORMER=1
```

### Database Permissions ✓ VERIFIED
- [x] **CREATE TABLE** - Your PostgreSQL user already has this
- [x] **INSERT/UPDATE/SELECT** - Your user already has these
- [x] **No new roles needed** - Use existing credentials

### AWS/Network Permissions
- [ ] **SSH to EC2** - Verify you can connect
- [ ] **Security Group** - Verify outbound HTTPS allowed:
  ```bash
  # Run this on EC2 to test:
  curl -I https://oauth.reddit.com/
  # Should get HTTP/2 response, not timeout
  ```
- [ ] **Docker access** - Verify docker-compose works:
  ```bash
  docker-compose ps
  ```

### GitHub/Secrets (Optional for CI/CD)
- [ ] **GitHub Secrets** (if using Actions for auto-deploy)
  - [ ] `REDDIT_CLIENT_ID`
  - [ ] `REDDIT_CLIENT_SECRET`
  - [ ] `REDDIT_USERNAME`
  - [ ] `REDDIT_PASSWORD`

---

## 📋 Implementation Checklist

### Phase 1: Backend (3-4 hours)
- [ ] **1.1 Get Reddit Credentials** (15 min)
  - [ ] Create Reddit app
  - [ ] Copy Client ID & Secret
  - [ ] Store in `.env`

- [ ] **1.2 Create Database Tables** (10 min)
  - [ ] SSH to EC2
  - [ ] Run SQL migration from REDDIT_IMPLEMENTATION_PLAN.md
  - [ ] Verify: `\d reddit_mentions`

- [ ] **1.3 Create reddit_ingestion.py** (2-3 hours)
  - [ ] Create `backend/reddit_ingestion.py` (~300 lines)
  - [ ] Add PRAW to `requirements.txt`
  - [ ] Build Docker: `docker-compose build api`
  - [ ] Test import: `docker-compose run --rm api python3 -c "from reddit_ingestion import get_reddit_client"`

- [ ] **1.4 Wire into Main Ingestion** (30 min)
  - [ ] Modify `backend/ingestion.py` (~5 lines)
  - [ ] Add call to `ingest_reddit()`
  - [ ] Test: `docker-compose exec -T api python3 /app/ingestion.py`
  - [ ] Verify DB populated: `SELECT COUNT(*) FROM reddit_mentions`

- [ ] **1.5 Add Environment Variables** (15 min)
  - [ ] Update `docker-compose.yml`
  - [ ] Update `.env`
  - [ ] Restart: `docker-compose restart api`

### Phase 2: API Endpoints (3-4 hours)
- [ ] **2.1 Add Reddit Endpoints** (2-3 hours)
  - [ ] `/api/reddit` → Daily metrics
  - [ ] `/api/reddit/sentiment` → Sentiment analysis
  - [ ] `/api/reddit/subreddit/:name` → Specific subreddit
  - [ ] `/api/reddit/search?q=keyword` → Search
  - [ ] Test each endpoint with curl

- [ ] **2.2 Update Existing Endpoints** (1 hour)
  - [ ] `/api/social` - Include Reddit
  - [ ] `/api/sentiment` - Platform comparison
  - [ ] `/api/overview` - Reddit in totals

### Phase 3: Frontend (3-4 hours)
- [ ] **3.1 Create Reddit Dashboard** (2-3 hours)
  - [ ] `frontend/src/components/RedditDashboard.jsx` (~400 lines)
  - [ ] Line chart for daily metrics
  - [ ] Table for subreddit breakdown
  - [ ] List for recent mentions
  - [ ] Pie chart for sentiment

- [ ] **3.2 Update App.jsx** (30 min)
  - [ ] Add 'reddit' to tabs
  - [ ] Add redditData state
  - [ ] Add fetch calls

- [ ] **3.3 Test Locally** (30 min)
  - [ ] `npm run dev`
  - [ ] Check Reddit tab
  - [ ] Verify data loads
  - [ ] Check mobile view

### Phase 4: Deployment (2 hours)
- [ ] **4.1 Rebuild Images** (10 min)
  - [ ] `docker-compose build api`
  - [ ] `docker-compose build frontend`

- [ ] **4.2 Deploy to AWS** (20 min)
  - [ ] SSH to EC2
  - [ ] `git pull`
  - [ ] `docker-compose up -d`
  - [ ] Verify: `docker-compose ps`

- [ ] **4.3 Verify** (30 min)
  - [ ] Open dashboard
  - [ ] Check Reddit tab
  - [ ] Verify all data displays
  - [ ] No console errors

- [ ] **4.4 Monitor** (30 min + ongoing)
  - [ ] Watch logs: `docker-compose logs -f api`
  - [ ] Check DB: `SELECT COUNT(*) FROM reddit_mentions`
  - [ ] Monitor for 24 hours

---

## 📊 Permissions Summary Table

| Permission | Type | Required | Status | Notes |
|-----------|------|----------|--------|-------|
| Reddit OAuth | App credentials | YES | ✅ Free | Create at reddit.com/prefs/apps |
| Reddit Account | Read-only user | YES | ✅ Free | Your personal account works |
| Database CREATE | SQL privilege | NO | ✅ Have | Already in user permissions |
| Database INSERT/UPDATE | SQL privilege | NO | ✅ Have | Already in user permissions |
| AWS Outbound HTTPS | Security group | YES | 🔍 Verify | Should be allowed (needed for API calls) |
| EC2 SSH Access | SSH key | YES | ✅ Have | You have existing access |
| Docker Execution | Local permission | NO | ✅ Have | Already working |
| GitHub Secrets | Optional for CI/CD | NO | ◇ Optional | For auto-deployment only |
| File system `.env` | Read permission | YES | ✅ Have | Docker reads this file |

---

## 🚀 Quick Start (Summary)

**Time to complete everything: ~11-14 hours**

```bash
# Step 1: Get credentials (15 min)
# Go to https://www.reddit.com/prefs/apps and create app

# Step 2: Add to .env (5 min)
echo "REDDIT_CLIENT_ID=your_id" >> .env
echo "REDDIT_CLIENT_SECRET=your_secret" >> .env
echo "REDDIT_USERNAME=your_username" >> .env
echo "REDDIT_PASSWORD=your_password" >> .env

# Step 3: Create database tables (10 min)
# Run SQL from REDDIT_IMPLEMENTATION_PLAN.md

# Step 4: Create backend module (2-3 hours)
# Create backend/reddit_ingestion.py with functions from REDDIT_IMPLEMENTATION_PLAN.md

# Step 5: Wire into ingestion (30 min)
# Update backend/ingestion.py to call ingest_reddit()

# Step 6: Add API endpoints (2-3 hours)
# Update backend/api.py with new endpoints

# Step 7: Build Docker (10 min)
docker-compose build api

# Step 8: Test ingestion (10 min)
docker-compose exec -T api python3 /app/ingestion.py

# Step 9: Create frontend (3-4 hours)
# Create RedditDashboard component and update App.jsx

# Step 10: Deploy (20 min)
git pull
docker-compose up -d

# Step 11: Verify (30 min)
# Open dashboard and check Reddit tab
```

---

## 🔒 Security Notes

- **Never commit** `.env` file to git
- **Store secrets** in `.env` locally, use GitHub Secrets for CI/CD
- **Restrict access** to `.env`: `chmod 600 .env`
- **Rotate credentials** if exposed (create new Reddit app)
- **Monitor logs** for authentication errors
- **Rate limiting** is automatic via PRAW library

---

## ❌ What's NOT Required

- ❌ Premium Reddit API tier (free tier is sufficient)
- ❌ Special AWS permissions (outbound HTTPS is standard)
- ❌ New database user (existing user has all permissions)
- ❌ New secrets manager (use existing .env approach)
- ❌ Load balancer changes (no new ports)
- ❌ SSL certificate changes (existing HTTPS works)
- ❌ VPN or proxy (Reddit API is publicly accessible)

---

## ✅ Everything Already in Place

- ✅ **PostgreSQL database** - Already running
- ✅ **Docker infrastructure** - Already configured
- ✅ **Transformer sentiment model** - Already deployed
- ✅ **Scheduler** - Already running daily at 9:00 AM
- ✅ **API framework** - Already set up
- ✅ **Frontend framework** - Already set up (React + Tailwind)
- ✅ **Charts library** - Already installed (Recharts)

---

## 📞 Need Help?

### If Something Breaks

1. **Check logs first**:
   ```bash
   docker-compose logs api | tail -50
   docker-compose logs db | tail -50
   ```

2. **Verify credentials**:
   ```bash
   docker-compose exec -T api python3 -c "
   import os
   print('Client ID:', os.getenv('REDDIT_CLIENT_ID', 'NOT SET')[:10] + '...')
   print('Username:', os.getenv('REDDIT_USERNAME', 'NOT SET'))
   "
   ```

3. **Test Reddit API directly**:
   ```bash
   docker-compose exec -T api python3 -c "
   import praw
   reddit = praw.Reddit(
     client_id='your_id',
     client_secret='your_secret',
     user_agent='test'
   )
   print(reddit.auth.authorized)
   "
   ```

4. **Check database**:
   ```bash
   docker-compose exec -T db psql -U postgres -d ummatics_monitor -c \
     "SELECT COUNT(*) FROM reddit_mentions"
   ```

### Reference Documents

- **REDDIT_PERMISSIONS_SETUP.md** - Detailed permissions guide
- **REDDIT_IMPLEMENTATION_PLAN.md** - Full technical specifications  
- **REDDIT_ARCHITECTURE.md** - System design and data flow
- **REDDIT_ACTION_PLAN.md** - Step-by-step implementation guide

---

## 📈 Success Indicators

After deployment, you should see:

✅ Reddit tab appears in dashboard  
✅ Dashboard shows "Last updated: [today]"  
✅ Daily metrics chart has data points  
✅ Subreddit table shows top subreddits  
✅ Recent mentions list shows posts with upvote counts  
✅ Sentiment pie chart shows distribution  
✅ No errors in browser console (F12)  
✅ No errors in Docker logs  
✅ Database has 40-60+ reddit_mentions records  

---

**Ready to start? Begin with Phase 1, Step 1.1 (15 minutes)** ✅
