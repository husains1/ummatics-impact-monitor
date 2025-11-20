# Reddit Support - Visual Quick Start Guide

## 🎬 5-Minute Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   REDDIT SUPPORT OVERVIEW                       │
│                                                                  │
│  What: Add Reddit mention tracking and sentiment analysis       │
│  When: Daily at 9:00 AM (existing schedule)                     │
│  How: New Python module + API endpoints + React component       │
│  Why: Expand social listening beyond Twitter                    │
│                                                                  │
│  Timeline: 11-14 hours total                                    │
│  Complexity: Moderate (straightforward integration)             │
│  Risk: Low (new tables, isolated code)                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 What Permissions Do I Need?

```
┌──────────────────────────────────────────────────────────────────┐
│                    PERMISSIONS CHECKLIST                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  🔴 TO GET (15 minutes):                                         │
│  ├─ Reddit API Client ID                                        │
│  ├─ Reddit API Client Secret                                    │
│  ├─ Reddit Username (yours)                                     │
│  └─ Reddit Password (yours)                                     │
│                                                                  │
│  ✅ ALREADY HAVE (no action needed):                            │
│  ├─ Database CREATE/INSERT/UPDATE permissions                  │
│  ├─ Docker access                                               │
│  ├─ AWS EC2 SSH access                                          │
│  ├─ Scheduler (runs daily)                                      │
│  ├─ Sentiment model (transformer deployed)                      │
│  └─ Frontend framework (React + Tailwind)                       │
│                                                                  │
│  ❌ NOT NEEDED:                                                 │
│  ├─ Premium Reddit account                                      │
│  ├─ Paid Reddit API tier                                        │
│  ├─ New database users                                          │
│  ├─ New AWS permissions                                         │
│  └─ New infrastructure                                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ System Architecture (Simple View)

```
DAILY 9:00 AM
    ↓
SCHEDULER (existing)
    ↓
run_full_ingestion() (modified +5 lines)
    ├── ingest_google_alerts()
    ├── ingest_twitter()
    ├── ingest_reddit()  ◄── NEW
    ├── ingest_website_analytics()
    ├── ingest_citations()
    └── update_sentiment_metrics()
    ↓
PostgreSQL Database
    ├── reddit_mentions (NEW)
    ├── reddit_daily_metrics (NEW)
    ├── reddit_subreddit_metrics (NEW)
    └── social_sentiment_metrics (UPDATED)
    ↓
Backend API (modified)
    ├── /api/reddit (NEW)
    ├── /api/reddit/sentiment (NEW)
    ├── /api/reddit/subreddit/:name (NEW)
    ├── /api/reddit/search?q= (NEW)
    ├── /api/social (UPDATED)
    ├── /api/sentiment (UPDATED)
    └── /api/overview (UPDATED)
    ↓
Frontend React Components
    ├── Overview tab (UPDATED - includes Reddit)
    ├── Social tab (UPDATED - includes Reddit)
    ├── Reddit tab (NEW)
    │   ├─ Daily metrics chart
    │   ├─ Subreddit breakdown table
    │   ├─ Recent posts list
    │   └─ Sentiment pie chart
    ├── Website tab
    ├── Citations tab
    └── News tab
```

---

## 🔑 How to Get Reddit Credentials (Step-by-Step)

```
STEP 1: Visit Reddit Apps Page
        https://www.reddit.com/prefs/apps
        └─ Requires Reddit account (create if needed)

STEP 2: Create App
        Click "Create another app..." at bottom
        └─ Fill in:
           Name: "Ummatics Impact Monitor"
           Type: (select) "script"
           Redirect URI: http://localhost:8000
        └─ Click "Create app"

STEP 3: Copy Credentials
        You'll see:
        ┌─────────────────────────────────────────┐
        │ Ummatics Impact Monitor                  │
        │ client_id                               │
        │ XXXXXXXXXXXXXXXXXXX ◄─ Copy this        │
        │ secret                                  │
        │ YYYYYYYYYYYYYYYYYYY ◄─ Copy this        │
        └─────────────────────────────────────────┘

STEP 4: Store in .env
        REDDIT_CLIENT_ID=XXXXXXXXXXXXXXXXXXX
        REDDIT_CLIENT_SECRET=YYYYYYYYYYYYYYYYYYY
        REDDIT_USERNAME=your_reddit_username
        REDDIT_PASSWORD=your_reddit_password
        REDDIT_USER_AGENT="UmmaticsMonitor/1.0 by YourUsername"

TOTAL TIME: 15 minutes ✅
```

---

## 📁 What Gets Created/Modified

```
BACKEND:
┌──────────────────────────────────────────┐
│ ✅ backend/reddit_ingestion.py [NEW]     │
│    (~300 lines)                          │
│    - Reddit API integration              │
│    - Data fetching & storage             │
│    - Sentiment analysis wrapper          │
│                                          │
│ ✏️ backend/ingestion.py [MODIFIED]      │
│    (~5 lines added)                      │
│    - Call ingest_reddit()                │
│                                          │
│ ✏️ backend/requirements.txt [MODIFIED]  │
│    - Add praw==7.7.0                     │
│    - Add prawcore==2.4.0                 │
│                                          │
│ ✏️ backend/api.py [MODIFIED]            │
│    (~150 lines added)                    │
│    - 4 new API endpoints                 │
│    - 3 updated endpoints                 │
│                                          │
│ ✏️ docker-compose.yml [MODIFIED]        │
│    - Add Reddit environment vars         │
└──────────────────────────────────────────┘

FRONTEND:
┌──────────────────────────────────────────┐
│ ✅ frontend/src/components/             │
│    RedditDashboard.jsx [NEW]             │
│    (~400 lines)                          │
│    - Charts & tables                     │
│    - Sentiment visualization             │
│                                          │
│ ✏️ frontend/src/App.jsx [MODIFIED]      │
│    (~10 lines added)                     │
│    - Add Reddit tab                      │
│    - Add data fetching                   │
└──────────────────────────────────────────┘

DATABASE:
┌──────────────────────────────────────────┐
│ ✅ reddit_mentions [NEW TABLE]           │
│ ✅ reddit_daily_metrics [NEW TABLE]      │
│ ✅ reddit_subreddit_metrics [NEW TABLE]  │
│ ✏️ social_sentiment_metrics [UPDATED]   │
│    (add platform='Reddit')               │
└──────────────────────────────────────────┘
```

---

## ⏱️ Implementation Timeline

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: BACKEND (3-4 hours)                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 1.1 Get Reddit Credentials           [15 min] ✅      │
│     ├─ Go to reddit.com/prefs/apps                     │
│     ├─ Create app                                      │
│     └─ Copy credentials               DONE             │
│                                                         │
│ 1.2 Create Database Tables            [10 min]         │
│     ├─ SSH to EC2                                      │
│     ├─ Run SQL migration                               │
│     └─ Verify tables created          IN PROGRESS      │
│                                                         │
│ 1.3 Create reddit_ingestion.py        [2-3 hours]      │
│     ├─ Create file with PRAW integration               │
│     ├─ Add search & fetch functions                    │
│     └─ Add sentiment wrapper           READY           │
│                                                         │
│ 1.4 Wire into Main Ingestion          [30 min]         │
│     ├─ Modify ingestion.py                             │
│     ├─ Add call to ingest_reddit()                     │
│     └─ Test end-to-end                 READY           │
│                                                         │
│ 1.5 Add Environment Variables         [15 min]         │
│     ├─ Update docker-compose.yml                       │
│     ├─ Update .env                                     │
│     └─ Restart containers              READY           │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 2: API ENDPOINTS (3-4 hours)                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 2.1 Add Reddit Endpoints              [2-3 hours]      │
│     ├─ /api/reddit                                     │
│     ├─ /api/reddit/sentiment                           │
│     ├─ /api/reddit/subreddit/:name                     │
│     └─ /api/reddit/search?q=          READY            │
│                                                         │
│ 2.2 Update Existing Endpoints         [1 hour]         │
│     ├─ /api/social                                     │
│     ├─ /api/sentiment                                  │
│     └─ /api/overview                  READY            │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 3: FRONTEND (3-4 hours)                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 3.1 Create Dashboard Component        [2-3 hours]      │
│     ├─ Chart library setup (Recharts)                  │
│     ├─ Dashboard layout                                │
│     └─ Sentiment visualization         READY           │
│                                                         │
│ 3.2 Update App.jsx                    [30 min]         │
│     ├─ Add Reddit tab                                  │
│     ├─ Add data fetching                               │
│     └─ Wire components                 READY           │
│                                                         │
│ 3.3 Test Locally                      [30 min]         │
│     ├─ npm run dev                                     │
│     ├─ Check data loads                                │
│     └─ Verify mobile                   READY           │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 4: DEPLOYMENT (2 hours)                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 4.1 Rebuild Docker                    [10 min]         │
│     ├─ docker-compose build api                        │
│     └─ docker-compose build frontend  READY            │
│                                                         │
│ 4.2 Deploy to AWS                     [20 min]         │
│     ├─ SSH to EC2                                      │
│     ├─ git pull                                        │
│     ├─ docker-compose up -d                            │
│     └─ Verify containers              READY            │
│                                                         │
│ 4.3 Verify End-to-End                 [30 min]         │
│     ├─ Open dashboard                                  │
│     ├─ Check Reddit tab                                │
│     └─ Verify data displays            READY           │
│                                                         │
│ 4.4 Monitor                           [30 min+]        │
│     ├─ Watch logs                                      │
│     ├─ Check database                                  │
│     └─ Monitor 24 hours                READY           │
│                                                         │
└─────────────────────────────────────────────────────────┘

TOTAL TIME: ~11-14 hours
```

---

## 🎯 Quick Start (TL;DR)

```
MINUTE 1-5:
  1. Go to https://www.reddit.com/prefs/apps
  2. Create app (type: "script")
  3. Copy Client ID & Secret

MINUTE 6-10:
  4. Add to .env:
     REDDIT_CLIENT_ID=...
     REDDIT_CLIENT_SECRET=...
     REDDIT_USERNAME=...
     REDDIT_PASSWORD=...

HOUR 1-3: BACKEND
  5. Create backend/reddit_ingestion.py (use template)
  6. Modify backend/ingestion.py (+5 lines)
  7. Add praw to requirements.txt
  8. Rebuild Docker image

HOUR 4-6: API
  9. Add endpoints to backend/api.py (use template)
  10. Test with curl

HOUR 7-10: FRONTEND
  11. Create RedditDashboard component (use template)
  12. Modify App.jsx (+10 lines)
  13. Test locally with npm run dev

HOUR 11-14: DEPLOY
  14. Deploy to AWS EC2
  15. Run database migration
  16. Verify in browser
  17. Monitor logs 24 hours

✅ DONE! Reddit support fully integrated
```

---

## 📊 What You'll See After Implementation

```
BEFORE:
Dashboard Tabs:
├─ Overview
├─ Social (Twitter only)
├─ Website
├─ Citations
└─ News

AFTER:
Dashboard Tabs:
├─ Overview (now includes Reddit totals)
├─ Social (now includes Reddit alongside Twitter)
├─ Reddit  ◄── NEW TAB
│   ├─ 📈 Daily Metrics Chart
│   │  └─ Mentions & engagement over 30 days
│   ├─ 📊 Subreddit Breakdown Table
│   │  └─ Top subreddits by mentions
│   ├─ 💬 Recent Mentions List
│   │  └─ Latest posts with sentiment badges
│   ├─ 📍 Sentiment Distribution Pie Chart
│   │  └─ Positive/Negative/Neutral %
│   └─ 📈 Sentiment Trend Chart
│      └─ 14-day sentiment score trend
├─ Website
├─ Citations
└─ News
```

---

## ✅ Success Checklist

After implementation, verify:

```
✅ Reddit tab appears in dashboard navigation
✅ Reddit tab loads without errors
✅ Daily metrics chart displays data
✅ Subreddit table shows communities
✅ Recent mentions list shows posts
✅ Sentiment pie chart shows distribution
✅ API returns data:
   GET /api/reddit → 200
   GET /api/reddit/sentiment → 200
   GET /api/reddit/subreddit/science → 200
   GET /api/reddit/search?q=ummatics → 200
✅ Database populated:
   SELECT COUNT(*) FROM reddit_mentions → >0
✅ Scheduler runs daily without errors
✅ No errors in browser console (F12)
✅ Mobile view looks good
```

---

## 🔄 If Something Goes Wrong

```
PROBLEM → SOLUTION

"Authentication failed"
  → Check .env has REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET
  → Verify credentials match reddit.com/prefs/apps

"No data in Reddit tab"
  → Check logs: docker-compose logs api | grep reddit
  → Check DB: SELECT COUNT(*) FROM reddit_mentions
  → Verify scheduler ran at 9:00 AM

"Rate limit exceeded"
  → Unlikely (using <2% of API quota)
  → If happens: wait 60 seconds, PRAW handles retry

"Database table doesn't exist"
  → Run SQL migration from REDDIT_IMPLEMENTATION_PLAN.md
  → Verify with: \d reddit_mentions

"Docker build fails"
  → Check internet connection (downloading PRAW)
  → Try: docker-compose build --no-cache api
```

---

## 📚 Documentation Map

```
Quick Overview (5 min)
    ↓
REDDIT_SUMMARY.md ◄── START HERE

Want credentials? (15 min)
    ↓
REDDIT_PERMISSIONS_SETUP.md

Ready to implement? (11-14 hours)
    ↓
REDDIT_ACTION_PLAN.md
    ├─ Read for timeline
    └─ Follow each phase

Need code? (copy-paste ready)
    ↓
REDDIT_CODE_REFERENCE.md
    ├─ Use templates
    └─ Run SQL

Curious about architecture?
    ↓
REDDIT_ARCHITECTURE.md
    ├─ System design
    ├─ Data flow
    └─ Performance

Troubleshooting?
    ↓
REDDIT_PERMISSIONS_CHECKLIST.md
    ├─ Quick fixes
    ├─ Common issues
    └─ Testing commands

Deep dive needed?
    ↓
REDDIT_IMPLEMENTATION_PLAN.md
    ├─ Full specifications
    ├─ Database schema
    └─ Error handling
```

---

## 🚀 Next Action

**Choose Your Path:**

### 🎬 Start Immediately (15 minutes)
→ Go to https://www.reddit.com/prefs/apps and create app

### 📖 Learn More First (30 minutes)
→ Read REDDIT_PERMISSIONS_SETUP.md

### 🛠️ Ready to Build (11-14 hours)
→ Follow REDDIT_ACTION_PLAN.md Phase 1

### 💻 Show Me Code (2 hours)
→ Use REDDIT_CODE_REFERENCE.md templates

---

## 📞 Questions?

| Question | Answer | Document |
|----------|--------|----------|
| What permissions do I need? | Just Reddit API credentials | REDDIT_PERMISSIONS_SETUP.md |
| How long will this take? | ~11-14 hours | REDDIT_ACTION_PLAN.md |
| Show me the code | Templates provided | REDDIT_CODE_REFERENCE.md |
| How does it work? | System architecture | REDDIT_ARCHITECTURE.md |
| I'm stuck | Troubleshooting guide | REDDIT_PERMISSIONS_CHECKLIST.md |
| Tell me everything | Full specs | REDDIT_IMPLEMENTATION_PLAN.md |

---

**Status**: Ready for Implementation ✅  
**Estimated Timeline**: 11-14 hours  
**Complexity**: Moderate  
**Risk**: Low  

**Let's build it!** 🚀
